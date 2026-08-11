"""Document discovery and upload service."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import uuid
import zipfile
from typing import Any, BinaryIO, Callable

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.security.access import RequestAccessContext, list_accessible_documents
from backend.app.schemas.documents import DocumentMetadata, DocumentType, UploadResponse
from cial_knowledge_os.file_formats import validate_ingestion_file

logger = logging.getLogger(__name__)


class DocumentUploadError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code

_TYPE_BY_SUFFIX: dict[str, DocumentType] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".csv": "csv",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
}


class DocumentService:
    """Work with files under the configured enterprise repository root."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.corpus_root_path

    def list_documents(
        self,
        *,
        access_context: RequestAccessContext | None = None,
    ) -> list[DocumentMetadata]:
        if SessionLocal is not None and access_context is not None:
            try:
                return self._list_documents_from_database(access_context)
            except Exception:  # noqa: BLE001
                logger.exception("document_list_db_filter_failed")
        indexed_paths = self._indexed_paths()
        if not self.root.exists():
            return []
        documents: list[DocumentMetadata] = []
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            documents.append(self._metadata_for(path, indexed_paths=indexed_paths))
        return documents

    def save_upload(self, filename: str, stream: BinaryIO) -> DocumentMetadata:
        if not self.root.is_dir():
            raise FileNotFoundError(f"Configured corpus directory does not exist: {self.root}")
        safe_name = self._safe_filename(filename)
        if not validate_ingestion_file(safe_name)["valid_for_ingestion"]:
            raise ValueError("This file type is not supported for indexing.")
        destination = self._reserve_destination(self.root / safe_name)
        try:
            with destination.open("wb") as handle:
                self._copy_bounded(stream, handle)
            self._validate_upload_content(destination)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return self._metadata_for(destination, indexed_paths=self._indexed_paths())

    def save_upload_with_indexing(
        self,
        filename: str,
        stream: BinaryIO,
        *,
        corpus_sync: Any | None = None,
        metadata_enqueue: Callable[[Path], dict[str, str]] | None = None,
        access_context: RequestAccessContext | None = None,
    ) -> UploadResponse:
        """Save an upload and durably enqueue it without API-process indexing."""
        if not self.root.is_dir():
            raise FileNotFoundError(f"Configured corpus directory does not exist: {self.root}")
        safe_name = self._safe_filename(filename)
        if not validate_ingestion_file(safe_name)["valid_for_ingestion"]:
            raise ValueError("This file type is not supported for indexing.")

        # Save to a temp file first for hashing
        temp_path = self.root / f".upload_{uuid.uuid4().hex}_{safe_name}.tmp"
        try:
            with temp_path.open("wb") as handle:
                self._copy_bounded(stream, handle)
            self._validate_upload_content(temp_path, expected_suffix=Path(safe_name).suffix)

            content_hash = self._hash_file(temp_path)
            duplicate_doc = self._find_duplicate_by_hash(
                content_hash,
                access_context=access_context,
            )

            if duplicate_doc is not None:
                temp_path.unlink(missing_ok=True)
                return UploadResponse(
                    id=str(duplicate_doc.get("id") or ""),
                    name=Path(str(duplicate_doc.get("relative_path") or safe_name)).name,
                    path=str(duplicate_doc.get("relative_path") or ""),
                    type=_TYPE_BY_SUFFIX.get(Path(safe_name).suffix.casefold(), "unknown"),
                    size_bytes=0,
                    modified_at=datetime.now(timezone.utc).isoformat(),
                    indexed=True,
                    indexing_status="skipped",
                    content_hash=content_hash,
                    duplicate_detected=True,
                    message="Duplicate content already exists; no new file or indexing job was created.",
                )

            destination = self._reserve_destination(self.root / safe_name)
            os.replace(temp_path, destination)

        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

        stat = destination.stat()
        relative = destination.relative_to(self.root).as_posix()
        file_type = _TYPE_BY_SUFFIX.get(destination.suffix.casefold(), "unknown")
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        # Determine if this is a duplicate
        if duplicate_doc is not None:
            logger.info(
                "upload_duplicate_detected",
                extra={
                    "event": "upload",
                    "document_filename": safe_name,
                    "content_hash": content_hash,
                    "existing_document_id": str(duplicate_doc.get("id", "")),
                },
            )
            _ = UploadResponse(
                id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
                name=destination.name,
                path=relative,
                type=file_type,
                size_bytes=stat.st_size,
                modified_at=modified_at,
                indexed=True,
                indexing_status="skipped",
                content_hash=content_hash,
                duplicate_detected=True,
                message="Duplicate content detected. File saved but indexing skipped — content already indexed.",
            )

        # Register the exact upload transactionally. The full sync callback is
        # retained only as a compatibility fallback for older explicit tools.
        indexing_job_id: str | None = None
        document_id: str | None = None
        document_version_id: str | None = None
        if metadata_enqueue is not None or corpus_sync is not None:
            try:
                if metadata_enqueue is not None:
                    registered = metadata_enqueue(destination)
                    document_id = registered.get("document_id")
                    document_version_id = registered.get("document_version_id")
                    indexing_job_id = registered.get("indexing_job_id")
                else:
                    summary = corpus_sync()
                    logger.info(
                        "upload_corpus_sync_completed",
                        extra={
                            "event": "upload",
                            "document_filename": safe_name,
                            "files_added": summary.files_added if hasattr(summary, "files_added") else 0,
                            "indexing_jobs_created": summary.indexing_jobs_created if hasattr(summary, "indexing_jobs_created") else 0,
                        },
                    )
                    indexing_job_id = self._find_latest_job_for_hash(content_hash)
            except Exception as exc:
                logger.exception("upload_corpus_sync_failed")
                destination.unlink(missing_ok=True)
                raise DocumentUploadError(
                    "Upload registration failed; no document was published.",
                    status_code=503,
                ) from exc

        logger.info(
            "upload_accepted",
            extra={
                "event": "upload",
                "document_filename": safe_name,
                "content_hash": content_hash,
                "indexing_job_id": indexing_job_id,
            },
        )

        return UploadResponse(
            id=document_id or hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
            name=destination.name,
            path=relative,
            type=file_type,
            size_bytes=stat.st_size,
            modified_at=modified_at,
            indexed=False,
            indexing_status="pending",
            indexing_job_id=indexing_job_id,
            document_version_id=document_version_id,
            content_hash=content_hash,
            message="Upload accepted. Background indexing queued.",
        )

    def _metadata_for(
        self,
        path: Path,
        *,
        indexed_paths: set[str],
    ) -> DocumentMetadata:
        stat = path.stat()
        relative = path.relative_to(self.root).as_posix()
        return DocumentMetadata(
            id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
            name=path.name,
            path=relative,
            type=_TYPE_BY_SUFFIX.get(path.suffix.casefold(), "unknown"),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
            indexed=str(path.resolve()) in indexed_paths or relative in indexed_paths,
        )

    def _indexed_paths(self) -> set[str]:
        manifest_path = settings.indexes_path / "document_manifest.json"
        if not manifest_path.is_file():
            return set()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        candidates: set[str] = set()
        documents = payload.get("documents")
        if isinstance(documents, dict):
            for key, value in documents.items():
                candidates.add(str(key))
                if isinstance(value, dict):
                    for field in ("path", "source", "source_path", "relative_path"):
                        if value.get(field):
                            candidates.add(str(value[field]))
        return candidates

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename.replace("\\", "/")).name.strip().rstrip(". ")
        name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)[:180].rstrip(". ")
        if not name:
            raise DocumentUploadError("A valid filename is required.")
        stem = Path(name).stem.casefold()
        reserved = {"con", "prn", "aux", "nul", "clock$"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
        if stem in reserved:
            raise DocumentUploadError("This filename is reserved by the operating system.")
        return name

    @staticmethod
    def _available_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 2
        while True:
            candidate = parent / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    @classmethod
    def _reserve_destination(cls, path: Path) -> Path:
        candidate = path
        for counter in range(1, 10_000):
            try:
                descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                return candidate
            except FileExistsError:
                candidate = path.with_name(f"{path.stem}-{counter + 1}{path.suffix}")
        raise DocumentUploadError("A unique storage name could not be allocated.", status_code=409)

    @staticmethod
    def _copy_bounded(source: BinaryIO, destination: BinaryIO) -> int:
        total = 0
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > settings.upload_max_bytes:
                raise DocumentUploadError("The uploaded file exceeds the configured size limit.", status_code=413)
            destination.write(block)
        if total == 0:
            raise DocumentUploadError("Empty files are not accepted.")
        return total

    @staticmethod
    def _validate_upload_content(path: Path, *, expected_suffix: str | None = None) -> None:
        suffix = (expected_suffix or path.suffix).casefold()
        with path.open("rb") as handle:
            head = handle.read(16)
        signatures = {
            ".pdf": (b"%PDF-",),
            ".png": (b"\x89PNG\r\n\x1a\n",),
            ".jpg": (b"\xff\xd8\xff",),
            ".jpeg": (b"\xff\xd8\xff",),
            ".tif": (b"II*\x00", b"MM\x00*"),
            ".tiff": (b"II*\x00", b"MM\x00*"),
            ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
            ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
            ".ppt": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        }
        expected = signatures.get(suffix)
        if expected and not any(head.startswith(signature) for signature in expected):
            raise DocumentUploadError("File content does not match its filename extension.")
        if suffix in {".docx", ".xlsx", ".pptx"}:
            if not head.startswith(b"PK"):
                raise DocumentUploadError("File content does not match its filename extension.")
            try:
                with zipfile.ZipFile(path) as archive:
                    entries = archive.infolist()
                    if len(entries) > 10_000:
                        raise DocumentUploadError("The Office archive contains too many entries.")
                    if sum(entry.file_size for entry in entries) > 500 * 1024 * 1024:
                        raise DocumentUploadError("The Office archive expands beyond the safe limit.")
                    if any(entry.file_size > max(entry.compress_size, 1) * 100 for entry in entries):
                        raise DocumentUploadError("The Office archive compression ratio is unsafe.")
                    if "[Content_Types].xml" not in {entry.filename for entry in entries}:
                        raise DocumentUploadError("The Office archive structure is invalid.")
            except zipfile.BadZipFile as exc:
                raise DocumentUploadError("The Office archive is invalid.") from exc
        if suffix in {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".xml", ".yaml", ".yml", ".csv"} and b"\x00" in head:
            raise DocumentUploadError("Text document contains binary content.")

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA256 hash of a file."""
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(block)
        return hasher.hexdigest()

    @staticmethod
    def _find_duplicate_by_hash(
        content_hash: str,
        *,
        access_context: RequestAccessContext | None = None,
    ) -> dict[str, Any] | None:
        """Check the database for an existing non-deleted document with the same hash."""
        if SessionLocal is None:
            return None
        try:
            from sqlalchemy import select
            from backend.app.models.knowledge import Document
            with SessionLocal() as session:
                statement = select(Document).where(
                    Document.repository_id == settings.corpus_repository_id,
                    Document.content_hash == content_hash,
                    Document.indexing_status != "deleted",
                    Document.indexed == True,  # noqa: E712
                )
                if access_context is not None:
                    accessible_ids = {
                        document.id
                        for document in list_accessible_documents(session, access_context)
                    }
                    if not accessible_ids:
                        return None
                    statement = statement.where(Document.id.in_(sorted(accessible_ids)))
                document = session.scalar(statement)
                if document is not None:
                    return {
                        "id": str(document.id),
                        "relative_path": document.relative_path,
                        "content_hash": document.content_hash,
                    }
        except Exception:  # noqa: BLE001
            logger.exception("duplicate_hash_check_failed")
        return None

    def _list_documents_from_database(
        self,
        access_context: RequestAccessContext,
    ) -> list[DocumentMetadata]:
        indexed_paths = self._indexed_paths()
        if not self.root.exists():
            return []
        documents: list[DocumentMetadata] = []
        with SessionLocal() as session:
            for document in list_accessible_documents(session, access_context):
                relative_path = str(document.relative_path or "").replace("\\", "/").strip("/")
                path = self.root / relative_path
                if not path.is_file():
                    continue
                stat = path.stat()
                documents.append(
                    DocumentMetadata(
                        id=str(document.id),
                        name=document.name,
                        path=relative_path,
                        type=_TYPE_BY_SUFFIX.get(path.suffix.casefold(), "unknown"),
                        size_bytes=stat.st_size,
                        modified_at=(
                            document.modified_at.isoformat()
                            if document.modified_at is not None
                            else datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        ),
                        indexed=bool(
                            document.indexed
                            or str(path.resolve()) in indexed_paths
                            or relative_path in indexed_paths
                        ),
                    )
                )
        return documents

    @staticmethod
    def _find_latest_job_for_hash(content_hash: str) -> str | None:
        """Find the most recent pending indexing job for a content hash."""
        if SessionLocal is None or not content_hash:
            return None
        try:
            from sqlalchemy import select
            from backend.app.models.operations import IndexingJob
            with SessionLocal() as session:
                job = session.scalar(
                    select(IndexingJob)
                    .where(
                        IndexingJob.repository_id == settings.corpus_repository_id,
                        IndexingJob.content_hash == content_hash,
                        IndexingJob.status == "pending",
                    )
                    .order_by(IndexingJob.started_at.desc())
                )
                if job is not None:
                    return str(job.id)
        except Exception:  # noqa: BLE001
            logger.exception("find_job_for_hash_failed")
        return None

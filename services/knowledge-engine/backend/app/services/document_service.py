"""Document discovery and upload service."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
import uuid
from typing import Any, BinaryIO

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.security.access import RequestAccessContext, list_accessible_documents
from backend.app.schemas.documents import DocumentMetadata, DocumentType, UploadResponse
from cial_knowledge_os.file_formats import validate_ingestion_file

logger = logging.getLogger(__name__)

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
        destination = self._available_path(self.root / safe_name)
        with destination.open("wb") as handle:
            shutil.copyfileobj(stream, handle)
        return self._metadata_for(destination, indexed_paths=self._indexed_paths())

    def save_upload_with_indexing(
        self,
        filename: str,
        stream: BinaryIO,
        *,
        corpus_sync: Any | None = None,
        indexing_worker: Any | None = None,
        access_context: RequestAccessContext | None = None,
    ) -> UploadResponse:
        """Save an uploaded file, create metadata + indexing job, trigger background indexing.

        Pipeline: Upload → Save → Hash → Dedup check → Corpus Sync → Indexing Job → Background Index
        """
        if not self.root.is_dir():
            raise FileNotFoundError(f"Configured corpus directory does not exist: {self.root}")
        safe_name = self._safe_filename(filename)
        if not validate_ingestion_file(safe_name)["valid_for_ingestion"]:
            raise ValueError("This file type is not supported for indexing.")

        # Save to a temp file first for hashing
        temp_path = self.root / f".upload_{uuid.uuid4().hex}_{safe_name}.tmp"
        try:
            with temp_path.open("wb") as handle:
                shutil.copyfileobj(stream, handle)

            content_hash = self._hash_file(temp_path)
            duplicate_doc = self._find_duplicate_by_hash(
                content_hash,
                access_context=access_context,
            )

            # Move to final location
            destination = self._available_path(self.root / safe_name)
            temp_path.replace(destination)

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

        # Run corpus sync to create metadata + version + indexing job
        indexing_job_id: str | None = None
        if corpus_sync is not None:
            try:
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
                # Get the job id from the newly created job
                indexing_job_id = self._find_latest_job_for_hash(content_hash)
            except Exception as exc:
                logger.exception("upload_corpus_sync_failed")
                return UploadResponse(
                    id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
                    name=destination.name,
                    path=relative,
                    type=file_type,
                    size_bytes=stat.st_size,
                    modified_at=modified_at,
                    indexed=False,
                    indexing_status="failed",
                    content_hash=content_hash,
                    message=f"File saved but metadata sync failed: {exc}",
                )

        # Trigger background indexing
        if indexing_worker is not None:
            try:
                import uuid as _uuid
                job_uuid = _uuid.UUID(indexing_job_id) if indexing_job_id else None
                indexing_worker.enqueue(job_uuid)
            except Exception:
                logger.exception("upload_indexing_enqueue_failed")

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
            id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
            name=destination.name,
            path=relative,
            type=file_type,
            size_bytes=stat.st_size,
            modified_at=modified_at,
            indexed=False,
            indexing_status="pending",
            indexing_job_id=indexing_job_id,
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
        name = Path(filename).name.strip() or "upload"
        return re.sub(r"[^A-Za-z0-9._ -]+", "_", name)

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

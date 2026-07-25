"""Reconcile approved managed personal storage with durable metadata/jobs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
import mimetypes
from pathlib import Path
import uuid

from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.models.identity import User
from backend.app.models.knowledge import Document, DocumentVersion, Folder, Workspace
from backend.app.models.operations import IndexingJob
from cial_knowledge_os.file_formats import is_supported_file
from cial_knowledge_os.corpus.scanner import is_ignored_managed_path

logger = logging.getLogger(__name__)


class ManagedWorkspaceIngestionService:
    """Out-of-band fallback for files under the configured personal root.

    API writes still create metadata and jobs directly. This reconciler uses the
    same rows and dedupe key, so a watcher event after an API write is harmless.
    """

    def __init__(self, *, root: Path, session_factory) -> None:
        self.root = root.resolve()
        self.session_factory = session_factory

    def sync(self, force_hash_paths: list[Path] | None = None) -> int:
        if self.session_factory is None or not self.root.exists():
            return 0
        files = {
            path.relative_to(self.root).as_posix(): path
            for path in self.root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not is_ignored_managed_path(path, self.root)
            and is_supported_file(path.name)
        }
        forced: set[str] = set()
        for path in force_hash_paths or ():
            try:
                forced.add(
                    path.resolve(strict=False).relative_to(self.root).as_posix()
                )
            except (OSError, ValueError):
                continue
        created = 0
        with self.session_factory() as session, session.begin():
            existing = {
                row.relative_path: row
                for row in session.scalars(select(Document).where(Document.storage_scope == "personal"))
            }
            for relative, path in sorted(files.items()):
                row = existing.get(relative)
                stat = path.stat()
                modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                if (
                    row is not None
                    and row.lifecycle_status != "deleted"
                    and int(row.size_bytes or 0) == stat.st_size
                    and row.modified_at is not None
                    and int(row.modified_at.timestamp() * 1_000_000)
                    == int(modified_at.timestamp() * 1_000_000)
                    and relative not in forced
                ):
                    continue
                digest = self._hash(path)
                if row is not None and row.content_hash == digest and row.lifecycle_status != "deleted":
                    row.size_bytes = stat.st_size
                    row.modified_at = modified_at
                    continue
                context = self._context(session, relative)
                if context is None:
                    logger.warning("personal_file_context_rejected", extra={"event": "file_detected", "relative_path": relative})
                    continue
                organization_id, user, workspace, folder = context
                now = datetime.now(timezone.utc)
                if row is None:
                    row = Document(
                        organization_id=organization_id, department_id=user.department_id,
                        workspace_id=workspace.id, folder_id=folder.id,
                        repository_id=f"personal:{user.id}", storage_scope="personal",
                        owner_user_id=user.id, name=path.name, relative_path=relative,
                        file_type=path.suffix.lstrip(".").casefold(), extension=path.suffix.casefold(),
                        mime_type=mimetypes.guess_type(path.name)[0], visibility="private",
                        size_bytes=stat.st_size, content_hash=digest,
                        modified_at=modified_at,
                        indexed=False, indexing_status="pending", lifecycle_status="pending",
                        source_type="backup_sync", created_by_user_id=user.id, updated_by_user_id=user.id,
                        metadata_={"out_of_band": True},
                    )
                    session.add(row); session.flush()
                else:
                    row.size_bytes = stat.st_size; row.content_hash = digest
                    row.modified_at = modified_at
                    row.deleted_at = None; row.indexed = False
                    row.indexing_status = row.lifecycle_status = "pending"
                number = int(session.scalar(select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == row.id)) or 0) + 1
                version = DocumentVersion(
                    document_id=row.id, repository_id=row.repository_id, version_number=number,
                    storage_key=relative, content_hash=digest, size_bytes=stat.st_size,
                    mime_type=row.mime_type, modified_at=row.modified_at, status="pending",
                    created_by_user_id=user.id,
                )
                session.add(version); session.flush(); row.current_version_id = version.id
                if self._enqueue(session, row, version, "modified" if relative in existing else "added"):
                    created += 1
            for relative, row in existing.items():
                if relative in files or row.lifecycle_status == "deleted":
                    continue
                row.indexed = False; row.indexing_status = row.lifecycle_status = "deleted"
                row.deleted_at = datetime.now(timezone.utc)
                version = session.get(DocumentVersion, row.current_version_id) if row.current_version_id else None
                if self._enqueue(session, row, version, "deleted"):
                    created += 1
        return created

    def _context(self, session, relative: str):
        parts = Path(relative).parts
        if len(parts) < 4:
            return None
        try:
            organization_id, user_id = uuid.UUID(parts[0]), uuid.UUID(parts[1])
        except ValueError:
            return None
        user = session.get(User, user_id)
        if user is None or user.organization_id != organization_id or user.department_id is None:
            return None
        workspace = session.scalar(select(Workspace).where(
            Workspace.organization_id == organization_id, Workspace.owner_user_id == user_id,
            Workspace.workspace_type == "personal", Workspace.deleted_at.is_(None),
        ))
        if workspace is None:
            return None
        folder_key = parts[2]
        clauses = [Folder.workspace_id == workspace.id]
        try:
            folder_id = uuid.UUID(folder_key)
        except ValueError:
            clauses.append(Folder.system_key == folder_key)
        else:
            clauses.append(Folder.id == folder_id)
        folder = session.scalar(select(Folder).where(*clauses))
        return (organization_id, user, workspace, folder) if folder is not None else None

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _enqueue(session, document: Document, version: DocumentVersion | None, action: str) -> bool:
        version_id = version.id if version is not None else None
        existing = session.scalar(select(IndexingJob).where(
            IndexingJob.document_version_id == version_id,
            IndexingJob.status.in_(("pending","claimed","extracting","chunked","embedding","writing","verifying","retry_wait")),
        )) if version_id else None
        if existing is not None:
            if action == "deleted":
                existing.operation = "delete_asset"
                existing.priority = 120
                existing.metadata_ = {
                    **(existing.metadata_ or {}),
                    "action": "deleted",
                }
            logger.info("index_job_deduplicated", extra={"event": "index_job_deduplicated", "job_id": str(existing.id)})
            return False
        is_ocr = Path(str(document.relative_path or "")).suffix.casefold() in {
            ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"
        }
        job = IndexingJob(
            document_id=document.id, document_version_id=version_id,
            asset_type="document",
            operation="delete_asset" if action == "deleted" else "upsert_version",
            content_hash=document.content_hash, repository_id=document.repository_id,
            status="pending", priority=120 if action == "deleted" else 55 if is_ocr else 60,
            max_attempts=settings.indexer_max_attempts, force_rebuild=False, attempts=0,
            message=f"Managed personal document {action}.",
            metadata_={"source": "workspace_watcher", "action": action,
                       "document_id": str(document.id), "document_version_id": str(version_id) if version_id else None,
                       "relative_path": document.relative_path, "workspace_id": str(document.workspace_id),
                       "owner_user_id": str(document.owner_user_id), "storage_scope": "personal",
                       "visibility": "private", "repository_id": document.repository_id,
                       "workload_queue": "ocr" if is_ocr else "normal"},
        )
        session.add(job)
        logger.info("index_job_enqueued", extra={"event": "index_job_enqueued", "job_id": str(job.id), "document_id": str(document.id)})
        return True

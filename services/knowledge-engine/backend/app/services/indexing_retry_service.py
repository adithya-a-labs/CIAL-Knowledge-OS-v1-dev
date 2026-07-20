"""Safe, durable manual retry orchestration for failed document indexing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.operations import AuditEvent, IndexingJob
from backend.app.security.access import RequestAccessContext, apply_document_access_filter, can_upload_enterprise_documents
from cial_knowledge_os.file_formats import inspect_ingestion_candidate

logger = logging.getLogger(__name__)


class IndexingRetryError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class IndexingRetryResult:
    document: Document
    job: IndexingJob
    deduplicated: bool = False


class IndexingRetryService:
    """Requeue the current managed artifact through the normal production worker."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def retry(self, document_id: uuid.UUID, access: RequestAccessContext) -> IndexingRetryResult:
        statement = apply_document_access_filter(
            select(Document).where(Document.id == document_id), access, action="edit",
        ).with_for_update()
        document = self.session.scalar(statement)
        if document is None or (
            document.storage_scope == "enterprise" and not can_upload_enterprise_documents(access)
        ):
            raise IndexingRetryError("document_not_found", "Document not found.", 404)

        active = self._active_job(document.current_version_id)
        if document.indexing_status in {"pending", "indexing"} and active is not None:
            logger.info("index_retry_deduplicated", extra=self._log_fields(document, active, access))
            return IndexingRetryResult(document=document, job=active, deduplicated=True)
        if document.indexing_status != "failed" or document.lifecycle_status != "failed":
            raise IndexingRetryError("indexing_not_failed", "Only failed files can be retried.")
        if document.deleted_at is not None or document.current_version_id is None:
            raise IndexingRetryError("indexing_retry_not_allowed", "This file cannot be retried.", 422)

        version = self.session.get(DocumentVersion, document.current_version_id)
        if version is None or version.status != "failed":
            raise IndexingRetryError("indexing_retry_not_allowed", "The current failed file version is unavailable.", 422)

        artifact = self._artifact(document, version)
        inspection = inspect_ingestion_candidate(artifact, corpus_root=self._root(document))
        if inspection.get("skip_reason"):
            raise IndexingRetryError(
                "indexing_retry_not_allowed",
                "The stored file is empty, unreadable, or no longer supported for indexing.",
                422,
            )
        content_hash = self._hash(artifact)
        stat = artifact.stat()
        now = datetime.now(timezone.utc)

        if content_hash != version.content_hash:
            version = self._new_version(document, version, artifact, content_hash, now)
            job = self._new_job(document, version, action="modified", message="Changed file queued for indexing retry.")
        else:
            job = self.session.scalar(
                select(IndexingJob).where(
                    IndexingJob.document_version_id == version.id,
                    IndexingJob.status == "failed",
                ).order_by(IndexingJob.updated_at.desc(), IndexingJob.created_at.desc()).with_for_update().limit(1)
            )
            if job is None:
                raise IndexingRetryError("indexing_retry_not_allowed", "No failed indexing attempt is available.", 422)
            history = list((job.metadata_ or {}).get("failure_history") or [])
            history.append({
                "attempts": int(job.attempts or 0), "error_code": job.error_detail,
                "safe_message": job.message, "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            })
            job.metadata_ = {
                **(job.metadata_ or {}), "action": "modified", "manual_retry": True,
                "manual_retry_count": int((job.metadata_ or {}).get("manual_retry_count") or 0) + 1,
                "failure_history": history[-20:], "stage": "queued",
            }
            job.status = "pending"
            job.attempts = 0
            job.started_at = job.updated_at = now
            job.completed_at = None
            job.error_detail = None
            job.message = "Manual indexing retry queued."

        document.content_hash = content_hash
        document.size_bytes = stat.st_size
        document.modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        document.indexed = False
        document.indexing_status = document.lifecycle_status = "pending"
        document.metadata_ = {
            **(document.metadata_ or {}), "indexing_error_code": None,
            "indexing_safe_message": "Queued for preparation.", "indexing_retry_allowed": False,
        }
        version.status = "pending"
        actor_id = access.principal.user_id
        self.session.add(AuditEvent(
            user_id=actor_id, actor_user_id=actor_id, action="indexing_retry_requested",
            entity_type="document", entity_id=document.id, status="succeeded",
            metadata_={"document_version_id": str(version.id), "indexing_job_id": str(job.id)},
        ))
        self.session.commit()
        logger.info("index_retry_requested", extra=self._log_fields(document, job, access))
        logger.info("index_retry_enqueued", extra=self._log_fields(document, job, access))
        return IndexingRetryResult(document=document, job=job)

    def _artifact(self, document: Document, version: DocumentVersion) -> Path:
        root = self._root(document)
        storage_key = str(version.storage_key or document.relative_path or "").strip()
        if not storage_key:
            raise IndexingRetryError("indexing_artifact_missing", "The stored file is unavailable.", 422)
        candidate = root / storage_key
        if candidate.is_symlink():
            raise IndexingRetryError("indexing_retry_not_allowed", "The stored file cannot be accessed safely.", 422)
        try:
            artifact = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            raise IndexingRetryError("indexing_artifact_missing", "The stored file is unavailable.", 422) from None
        if root not in artifact.parents or not artifact.is_file():
            raise IndexingRetryError("indexing_retry_not_allowed", "The stored file cannot be accessed safely.", 422)
        return artifact

    @staticmethod
    def _root(document: Document) -> Path:
        root = settings.workspace_root_path if document.storage_scope == "personal" else settings.corpus_root_path
        return root.resolve()

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _active_job(self, version_id: uuid.UUID | None) -> IndexingJob | None:
        if version_id is None:
            return None
        return self.session.scalar(select(IndexingJob).where(
            IndexingJob.document_version_id == version_id,
            IndexingJob.status.in_(("pending", "running")),
        ).with_for_update().limit(1))

    def _new_version(self, document: Document, previous: DocumentVersion, artifact: Path, content_hash: str, now: datetime) -> DocumentVersion:
        number = int(self.session.scalar(select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document.id)) or 0) + 1
        previous.status = "archived"
        version = DocumentVersion(
            document_id=document.id, repository_id=document.repository_id, version_number=number,
            storage_key=previous.storage_key or document.relative_path, content_hash=content_hash, size_bytes=artifact.stat().st_size,
            mime_type=document.mime_type, created_by_user_id=document.updated_by_user_id,
            modified_at=datetime.fromtimestamp(artifact.stat().st_mtime, timezone.utc), status="pending",
        )
        self.session.add(version)
        self.session.flush()
        document.current_version_id = version.id
        return version

    def _new_job(self, document: Document, version: DocumentVersion, *, action: str, message: str) -> IndexingJob:
        job = IndexingJob(
            document_id=document.id, document_version_id=version.id, content_hash=version.content_hash,
            repository_id=document.repository_id, status="pending", force_rebuild=False, attempts=0,
            message=message, metadata_={
                "source": "manual_retry", "action": action, "manual_retry": True, "stage": "queued",
                "document_id": str(document.id), "document_version_id": str(version.id),
                "relative_path": document.relative_path, "content_hash": version.content_hash,
                "repository_id": document.repository_id, "storage_scope": document.storage_scope,
                "workspace_id": str(document.workspace_id),
                "owner_user_id": str(document.owner_user_id) if document.owner_user_id else None,
                "department_id": str(document.department_id),
                "folder_id": str(document.folder_id) if document.folder_id else None,
                "visibility": document.visibility, "lifecycle_status": "pending",
            },
        )
        self.session.add(job)
        self.session.flush()
        return job

    @staticmethod
    def _log_fields(document: Document, job: IndexingJob, access: RequestAccessContext) -> dict[str, object]:
        return {
            "event": "index_retry", "document_id": str(document.id),
            "version_id": str(job.document_version_id), "job_id": str(job.id),
            "actor_id": str(access.principal.user_id), "attempt": int(job.attempts or 0),
        }

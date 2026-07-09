"""PostgreSQL metadata access for the Corpus layer."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import logging
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.app.models.knowledge import Document, Folder
from backend.app.models.operations import IndexingJob, IngestionRun


logger = logging.getLogger(__name__)

DELETED_STATUS = "deleted"

_ACTIVE_JOB_STATUSES = ("pending", "running")
_VALID_JOB_STATUSES = ("pending", "running", "succeeded", "failed", "skipped")


@dataclass(frozen=True)
class MetadataSnapshot:
    folders_by_path: dict[str, Folder]
    documents_by_path: dict[str, Document]
    active_documents: list[Document]


class CorpusMetadataStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(self) -> MetadataSnapshot:
        folders = list(self.session.scalars(select(Folder)))
        documents = list(self.session.scalars(select(Document)))
        return MetadataSnapshot(
            folders_by_path={folder.relative_path: folder for folder in folders},
            documents_by_path={document.relative_path: document for document in documents},
            active_documents=[
                document for document in documents if document.indexing_status != DELETED_STATUS
            ],
        )

    def next_document_version(self, document_id: uuid.UUID) -> int:
        current = self.session.scalar(
            select(func.max(DocumentVersion.version_number)).where(  # type: ignore[name-defined]
                DocumentVersion.document_id == document_id  # type: ignore[name-defined]
            )
        )
        return int(current or 0) + 1

    def add_indexing_job(self, *, action: str, document: Document, message: str) -> IndexingJob:
        """Create a pending indexing job, or return an existing active one."""
        existing = self._find_active_job(document.id, document.content_hash)
        if existing is not None:
            logger.info(
                "indexing_job_duplicate_skipped",
                extra={
                    "event": "indexing",
                    "document_id": str(document.id),
                    "content_hash": document.content_hash,
                    "existing_job_id": str(existing.id),
                    "existing_status": existing.status,
                },
            )
            return existing

        job = IndexingJob(
            document_id=document.id,
            content_hash=document.content_hash,
            status="pending",
            force_rebuild=False,
            message=message,
            metadata_={
                "source": "corpus_sync",
                "action": action,
                "document_id": str(document.id),
                "relative_path": document.relative_path,
                "content_hash": document.content_hash,
            },
        )
        self.session.add(job)
        return job

    def _find_active_job(
        self, document_id: uuid.UUID | None, content_hash: str | None,
    ) -> IndexingJob | None:
        """Return an existing pending/running job for this document+hash."""
        if document_id is None:
            return None
        conditions = [
            IndexingJob.document_id == document_id,
            IndexingJob.status.in_(_ACTIVE_JOB_STATUSES),
        ]
        if content_hash is not None:
            conditions.append(IndexingJob.content_hash == content_hash)
        return self.session.scalar(select(IndexingJob).where(and_(*conditions)))

    # ------------------------------------------------------------------
    # Job state transitions
    # ------------------------------------------------------------------

    def mark_job_running(self, job_id: uuid.UUID) -> bool:
        return self._transition_job(job_id, from_status="pending", to_status="running")

    def mark_job_succeeded(self, job_id: uuid.UUID, *, message: str = "") -> bool:
        return self._transition_job(
            job_id, from_status="running", to_status="succeeded", message=message,
        )

    def mark_job_failed(self, job_id: uuid.UUID, *, error: str) -> bool:
        return self._transition_job(
            job_id, from_status="running", to_status="failed",
            message=f"Indexing failed: {error}", error_detail=error,
        )

    def mark_job_skipped(self, job_id: uuid.UUID, *, reason: str) -> bool:
        return self._transition_job(
            job_id, from_status="pending", to_status="skipped", message=reason,
        )

    def _transition_job(
        self,
        job_id: uuid.UUID,
        *,
        from_status: str,
        to_status: str,
        message: str = "",
        error_detail: str | None = None,
    ) -> bool:
        job = self.session.get(IndexingJob, job_id)
        if job is None:
            logger.warning("indexing_job_not_found", extra={"job_id": str(job_id)})
            return False
        if job.status != from_status:
            logger.warning(
                "indexing_job_transition_rejected",
                extra={
                    "job_id": str(job_id),
                    "current_status": job.status,
                    "expected_status": from_status,
                    "target_status": to_status,
                },
            )
            return False
        job.status = to_status
        if message:
            job.message = message
        if error_detail is not None:
            job.error_detail = error_detail
        if to_status in ("succeeded", "failed", "skipped"):
            job.completed_at = datetime.now(timezone.utc)
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def has_pending_jobs(self) -> bool:
        """Return True if any pending indexing jobs exist."""
        count = self.session.scalar(
            select(func.count()).select_from(IndexingJob).where(
                IndexingJob.status == "pending"
            )
        )
        return (count or 0) > 0

    def pending_jobs(self) -> list[IndexingJob]:
        """Return all pending indexing jobs ordered by creation time."""
        return list(
            self.session.scalars(
                select(IndexingJob)
                .where(IndexingJob.status == "pending")
                .order_by(IndexingJob.started_at)
            )
        )

    @staticmethod
    def folder_signatures(documents: list[Document]) -> dict[str, tuple[str, ...]]:
        signatures: dict[str, list[str]] = defaultdict(list)
        for document in documents:
            if not document.content_hash:
                continue
            path = document.relative_path
            parts = path.split("/")[:-1]
            signatures[""].append(document.content_hash)
            for index in range(len(parts)):
                folder_path = "/".join(parts[: index + 1])
                signatures[folder_path].append(document.content_hash)
        return {path: tuple(sorted(values)) for path, values in signatures.items()}


from backend.app.models.knowledge import DocumentVersion  # noqa: E402


def folder_to_dict(folder: Folder) -> dict[str, Any]:
    return {
        "id": str(folder.id),
        "parent_id": str(folder.parent_id) if folder.parent_id else None,
        "name": folder.name,
        "relative_path": folder.relative_path,
        "depth": folder.depth,
        "document_count": folder.document_count,
        "subfolder_count": folder.subfolder_count,
        "last_scanned_at": folder.last_scanned_at.isoformat() if folder.last_scanned_at else None,
        "created_at": folder.created_at.isoformat(),
        "updated_at": folder.updated_at.isoformat(),
    }


def document_to_dict(document: Document) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "folder_id": str(document.folder_id) if document.folder_id else None,
        "name": document.name,
        "relative_path": document.relative_path,
        "extension": document.extension,
        "mime_type": document.mime_type,
        "file_type": document.file_type,
        "size_bytes": document.size_bytes,
        "content_hash": document.content_hash,
        "modified_at": document.modified_at.isoformat() if document.modified_at else None,
        "indexed": document.indexed,
        "indexing_status": document.indexing_status,
        "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
        "page_count": document.page_count,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


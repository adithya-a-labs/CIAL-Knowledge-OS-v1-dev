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

from backend.app.models.identity import Department, Organization
from backend.app.models.knowledge import Document, Folder, Workspace
from backend.app.models.operations import IndexingJob, IngestionRun


logger = logging.getLogger(__name__)

DELETED_STATUS = "deleted"

_ACTIVE_JOB_STATUSES = ("pending", "running")
_VALID_JOB_STATUSES = ("pending", "running", "succeeded", "failed", "skipped")
_DEFAULT_SHARED_DEPARTMENT_CODE = "shared-knowledge"
_DEFAULT_SHARED_DEPARTMENT_NAME = "Shared Knowledge"
_DEFAULT_ENTERPRISE_WORKSPACE_SLUG = "enterprise"
_DEFAULT_ENTERPRISE_WORKSPACE_NAME = "Enterprise Workspace"


@dataclass(frozen=True)
class MetadataSnapshot:
    folders_by_path: dict[str, Folder]
    documents_by_path: dict[str, Document]
    active_documents: list[Document]


class CorpusMetadataStore:
    def __init__(self, session: Session, *, repository_id: str | None = None) -> None:
        self.session = session
        self.repository_id = repository_id

    def snapshot(self) -> MetadataSnapshot:
        folders_statement = select(Folder)
        documents_statement = select(Document)
        if self.repository_id is not None:
            folders_statement = folders_statement.where(Folder.repository_id == self.repository_id)
            documents_statement = documents_statement.where(Document.repository_id == self.repository_id)
        folders = list(self.session.scalars(folders_statement))
        documents = list(self.session.scalars(documents_statement))
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

    def ensure_enterprise_document_context(self) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        organization = self.session.scalar(select(Organization).order_by(Organization.created_at, Organization.name))
        if organization is None:
            raise RuntimeError("An organization must exist before synchronizing corpus metadata.")
        department = self.session.scalar(
            select(Department).where(
                Department.organization_id == organization.id,
                Department.code == _DEFAULT_SHARED_DEPARTMENT_CODE,
            )
        )
        if department is None:
            department = Department(
                organization_id=organization.id,
                name=_DEFAULT_SHARED_DEPARTMENT_NAME,
                code=_DEFAULT_SHARED_DEPARTMENT_CODE,
                description="Default department for enterprise corpus documents without an explicit owner department.",
            )
            self.session.add(department)
            self.session.flush()
        workspace = self.session.scalar(
            select(Workspace).where(
                Workspace.organization_id == organization.id,
                Workspace.slug == _DEFAULT_ENTERPRISE_WORKSPACE_SLUG,
            )
        )
        if workspace is None:
            workspace = Workspace(
                organization_id=organization.id,
                name=_DEFAULT_ENTERPRISE_WORKSPACE_NAME,
                slug=_DEFAULT_ENTERPRISE_WORKSPACE_SLUG,
                workspace_type="enterprise",
                department_id=department.id,
                visibility="enterprise",
                description="Default enterprise workspace for corpus-synchronized documents and folders.",
                is_active=True,
            )
            self.session.add(workspace)
            self.session.flush()
        return organization.id, department.id, workspace.id

    def add_indexing_job(
        self,
        *,
        action: str,
        document: Document,
        document_version: DocumentVersion | None,
        message: str,
    ) -> IndexingJob:
        """Create a pending indexing job, or return an existing active one."""
        existing = self._find_active_job(
            document_version.id if document_version is not None else None,
            document.id,
            document.content_hash,
        )
        if existing is not None:
            if action in {"deleted", "moved"}:
                existing.metadata_ = {**(existing.metadata_ or {}), "action": action,
                                      "relative_path": document.relative_path}
                existing.message = message
            logger.info(
                "index_job_deduplicated",
                extra={
                    "event": "index_job_deduplicated",
                    "document_id": str(document.id),
                    "content_hash": document.content_hash,
                    "existing_job_id": str(existing.id),
                    "existing_status": existing.status,
                },
            )
            return existing

        job = IndexingJob(
            document_id=document.id,
            document_version_id=document_version.id if document_version is not None else None,
            content_hash=document.content_hash,
            repository_id=self.repository_id,
            status="pending",
            force_rebuild=False,
            attempts=0,
            message=message,
            metadata_={
                "source": "corpus_sync",
                "repository_id": self.repository_id,
                "action": action,
                "document_id": str(document.id),
                "document_version_id": str(document_version.id) if document_version is not None else None,
                "relative_path": document.relative_path,
                "content_hash": document.content_hash,
                "storage_scope": document.storage_scope,
                "owner_user_id": str(document.owner_user_id) if document.owner_user_id else None,
                "department_id": str(document.department_id),
                "workspace_id": str(document.workspace_id),
                "folder_id": str(document.folder_id) if document.folder_id else None,
                "visibility": document.visibility,
                "lifecycle_status": document.lifecycle_status,
            },
        )
        self.session.add(job)
        logger.info("index_job_enqueued", extra={"event": "index_job_enqueued",
            "job_id": str(job.id), "document_id": str(document.id)})
        return job

    def _find_active_job(
        self,
        document_version_id: uuid.UUID | None,
        document_id: uuid.UUID | None,
        content_hash: str | None,
    ) -> IndexingJob | None:
        """Return an existing pending/running job for this document+hash."""
        if document_version_id is None and document_id is None:
            return None
        conditions = [IndexingJob.status.in_(_ACTIVE_JOB_STATUSES)]
        if self.repository_id is not None:
            conditions.append(IndexingJob.repository_id == self.repository_id)
        if document_version_id is not None:
            conditions.append(IndexingJob.document_version_id == document_version_id)
        elif document_id is not None:
            conditions.append(IndexingJob.document_id == document_id)
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
        if to_status == "running":
            job.attempts = int(job.attempts or 0) + 1
            job.started_at = datetime.now(timezone.utc)
        if message:
            job.message = message
        if error_detail is not None:
            job.error_detail = error_detail
        if job.document_version_id is not None:
            version = self.session.get(DocumentVersion, job.document_version_id)
            if version is not None:
                if to_status == "running":
                    version.status = "indexing"
                elif to_status == "succeeded":
                    version.status = "indexed"
                elif to_status == "failed":
                    version.status = "failed"
                elif to_status == "skipped":
                    version.status = "archived"
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
        "workspace_id": str(folder.workspace_id),
        "repository_id": folder.repository_id,
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
    payload = {
        "id": str(document.id),
        "organization_id": str(document.organization_id),
        "department_id": str(document.department_id),
        "workspace_id": str(document.workspace_id),
        "repository_id": document.repository_id,
        "folder_id": str(document.folder_id) if document.folder_id else None,
        "storage_scope": document.storage_scope,
        "owner_user_id": str(document.owner_user_id) if document.owner_user_id else None,
        "name": document.name,
        "relative_path": document.relative_path,
        "extension": document.extension,
        "mime_type": document.mime_type,
        "file_type": document.file_type,
        "visibility": document.visibility,
        "size_bytes": document.size_bytes,
        "content_hash": document.content_hash,
        "modified_at": document.modified_at.isoformat() if document.modified_at else None,
        "indexed": document.indexed,
        "indexing_status": document.indexing_status,
        "lifecycle_status": document.lifecycle_status,
        "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
        "page_count": document.page_count,
        "source_type": document.source_type,
        "current_version_id": str(document.current_version_id) if document.current_version_id else None,
        "deleted_at": document.deleted_at.isoformat() if document.deleted_at else None,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
    indexing_metadata = document.metadata_ or {}
    payload.update({
        "indexing_stage": indexing_metadata.get("indexing_stage"),
        "indexing_safe_message": indexing_metadata.get("indexing_safe_message"),
        "indexing_error_code": indexing_metadata.get("indexing_error_code"),
        "retry_allowed": document.indexing_status == "failed" and indexing_metadata.get("indexing_retry_allowed", True) is not False,
        "indexing_updated_at": document.updated_at.isoformat(),
    })
    return payload

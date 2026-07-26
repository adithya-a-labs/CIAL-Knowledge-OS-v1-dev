"""PostgreSQL-backed indexing queue, leases, heartbeats, and generations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import random
import uuid
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.operations import IndexGeneration, IndexerWorker, IndexingJob


ACTIVE_JOB_STATUSES = frozenset(
    {
        "pending",
        "claimed",
        "extracting",
        "chunked",
        "embedding",
        "writing",
        "verifying",
        "retry_wait",
    }
)
IN_PROGRESS_STATUSES = frozenset(
    {"claimed", "extracting", "chunked", "embedding", "writing", "verifying"}
)
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "superseded", "cancelled"})
STAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    "claimed": frozenset({"extracting", "writing", "completed", "retry_wait", "failed", "superseded", "cancelled"}),
    "extracting": frozenset({"chunked", "retry_wait", "failed", "superseded", "cancelled"}),
    "chunked": frozenset({"embedding", "retry_wait", "failed", "superseded", "cancelled"}),
    "embedding": frozenset({"writing", "retry_wait", "failed", "superseded", "cancelled"}),
    "writing": frozenset({"verifying", "retry_wait", "failed", "cancelled"}),
    "verifying": frozenset({"completed", "retry_wait", "failed", "cancelled"}),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvalidJobTransition(RuntimeError):
    pass


class DurableIndexQueue:
    """Small transactions around the existing ``indexing_jobs`` queue."""

    def __init__(
        self,
        session_factory: Callable[[], Session] | None = SessionLocal,
        *,
        lease_seconds: int | None = None,
        max_attempts: int | None = None,
        retry_backoff_seconds: float | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.lease_seconds = lease_seconds or settings.indexer_lease_seconds
        self.max_attempts = max_attempts or settings.indexer_max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds or settings.indexer_retry_backoff_seconds

    def enqueue_control(
        self,
        *,
        request_kind: str,
        scope: dict[str, Any] | None = None,
        requested_by: uuid.UUID | None = None,
        force: bool = False,
        priority: int = 100,
    ) -> IndexingJob:
        if self.session_factory is None:
            raise RuntimeError("PostgreSQL is required for durable indexing requests.")
        with self.session_factory() as session, session.begin():
            job = IndexingJob(
                asset_type="document",
                operation="rebuild_scope",
                status="pending",
                priority=priority,
                max_attempts=self.max_attempts,
                force_rebuild=force,
                repository_id=settings.corpus_repository_id,
                metadata_={
                    "request_kind": request_kind,
                    "scope": scope or {"repository_id": settings.corpus_repository_id},
                    "requested_by": str(requested_by) if requested_by else None,
                    "force": force,
                    "priority": priority,
                },
                message=f"{request_kind.replace('_', ' ').title()} queued for the standalone indexer.",
            )
            session.add(job)
            session.flush()
            return job

    def claim(self, worker_id: str, *, preferred_id: uuid.UUID | None = None) -> uuid.UUID | None:
        if self.session_factory is None:
            return None
        now = utc_now()
        with self.session_factory() as session, session.begin():
            statement = select(IndexingJob).where(
                IndexingJob.status.in_(("pending", "retry_wait")),
                IndexingJob.available_at <= now,
            )
            if preferred_id is not None:
                statement = statement.where(IndexingJob.id == preferred_id)
            job = session.scalar(
                statement.order_by(
                    IndexingJob.priority.desc(),
                    IndexingJob.available_at,
                    IndexingJob.created_at,
                    IndexingJob.id,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            job.status = "claimed"
            job.claimed_by = worker_id
            job.attempts = int(job.attempts or 0) + 1
            job.started_at = job.started_at or now
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            job.updated_at = now
            job.completed_at = None
            self._set_target_processing(session, job)
            return job.id

    def transition(self, job_id: uuid.UUID, worker_id: str, status: str) -> None:
        if self.session_factory is None:
            raise RuntimeError("PostgreSQL is required for indexing transitions.")
        now = utc_now()
        with self.session_factory() as session, session.begin():
            job = session.scalar(select(IndexingJob).where(IndexingJob.id == job_id).with_for_update())
            if job is None:
                raise InvalidJobTransition("Indexing job does not exist.")
            if job.claimed_by != worker_id:
                raise InvalidJobTransition("Indexing job is not leased by this worker.")
            allowed = STAGE_TRANSITIONS.get(job.status, frozenset())
            if status not in allowed:
                raise InvalidJobTransition(f"Cannot transition indexing job from {job.status} to {status}.")
            job.status = status
            job.updated_at = now
            job.heartbeat_at = now
            job.lease_expires_at = (
                now + timedelta(seconds=self.lease_seconds)
                if status in IN_PROGRESS_STATUSES
                else None
            )
            if status in TERMINAL_JOB_STATUSES:
                job.completed_at = now
                job.claimed_by = None
            if job.document_id is not None:
                from backend.app.models.knowledge import Document

                document = session.get(Document, job.document_id)
                if document is not None and document.lifecycle_status != "deleted":
                    document.indexing_status = "indexing"
                    document.lifecycle_status = "indexing"
                    document.metadata_ = {
                        **(document.metadata_ or {}),
                        "indexing_stage": status,
                    }
            if job.note_id is not None:
                from backend.app.models.workspace_content import NoteIndexState

                state = session.get(NoteIndexState, job.note_id)
                if state is not None:
                    state.status = "indexing"
                    state.updated_at = now

    def renew(self, job_id: uuid.UUID, worker_id: str) -> bool:
        if self.session_factory is None:
            return False
        now = utc_now()
        with self.session_factory() as session, session.begin():
            job = session.scalar(
                select(IndexingJob)
                .where(
                    IndexingJob.id == job_id,
                    IndexingJob.claimed_by == worker_id,
                    IndexingJob.status.in_(IN_PROGRESS_STATUSES),
                )
                .with_for_update()
            )
            if job is None:
                return False
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            job.updated_at = now
            return True

    def complete(self, job_id: uuid.UUID, worker_id: str, *, message: str = "Indexing completed.") -> None:
        self._finish(job_id, worker_id, status="completed", message=message)

    def supersede(self, job_id: uuid.UUID, worker_id: str, *, message: str) -> None:
        self._finish(job_id, worker_id, status="superseded", message=message)

    def fail(
        self,
        job_id: uuid.UUID,
        worker_id: str,
        *,
        error_code: str,
        safe_detail: str,
        transient: bool,
    ) -> str:
        if self.session_factory is None:
            return "failed"
        now = utc_now()
        with self.session_factory() as session, session.begin():
            job = session.scalar(select(IndexingJob).where(IndexingJob.id == job_id).with_for_update())
            if job is None or job.claimed_by != worker_id:
                return "failed"
            attempts = int(job.attempts or 0)
            limit = int(job.max_attempts or self.max_attempts)
            retry = transient and attempts < limit
            job.status = "retry_wait" if retry else "failed"
            job.error_code = error_code
            job.error_detail = safe_detail
            job.message = "Retry scheduled after a transient indexing failure." if retry else "Indexing failed."
            job.claimed_by = None
            job.lease_expires_at = None
            job.heartbeat_at = now
            job.updated_at = now
            if retry:
                delay = self.retry_backoff_seconds * (2 ** max(0, attempts - 1))
                job.available_at = now + timedelta(seconds=delay * random.uniform(0.8, 1.2))
                job.completed_at = None
            else:
                job.completed_at = now
            if job.document_id is not None:
                from backend.app.models.knowledge import Document

                document = session.get(Document, job.document_id)
                if document is not None and document.lifecycle_status != "deleted":
                    document.indexing_status = "pending" if retry else "failed"
                    document.lifecycle_status = "pending" if retry else "failed"
                    document.metadata_ = {
                        **(document.metadata_ or {}),
                        "indexing_stage": job.status,
                        "indexing_error_code": error_code,
                        "indexing_safe_message": safe_detail,
                        "indexing_retry_allowed": retry or not transient,
                    }
            if job.note_id is not None:
                from backend.app.models.workspace_content import NoteIndexState

                state = session.get(NoteIndexState, job.note_id)
                if state is not None:
                    state.status = "pending" if retry else "failed"
                    state.last_error = error_code
                    state.updated_at = now
            return job.status

    def _finish(self, job_id: uuid.UUID, worker_id: str, *, status: str, message: str) -> None:
        if self.session_factory is None:
            raise RuntimeError("PostgreSQL is required for indexing completion.")
        now = utc_now()
        with self.session_factory() as session, session.begin():
            job = session.scalar(select(IndexingJob).where(IndexingJob.id == job_id).with_for_update())
            if job is None or job.claimed_by != worker_id:
                raise InvalidJobTransition("Indexing job lease was lost before completion.")
            job.status = status
            job.message = message
            job.completed_at = now
            job.updated_at = now
            job.heartbeat_at = now
            job.lease_expires_at = None
            job.claimed_by = None
            job.error_code = None
            job.error_detail = None

    def recover_expired(self) -> dict[str, int]:
        if self.session_factory is None:
            return {"recovered": 0, "failed": 0}
        now = utc_now()
        recovered = failed = 0
        with self.session_factory() as session, session.begin():
            jobs = list(
                session.scalars(
                    select(IndexingJob)
                    .where(
                        IndexingJob.status.in_(IN_PROGRESS_STATUSES),
                        IndexingJob.lease_expires_at < now,
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            for job in jobs:
                if int(job.attempts or 0) >= int(job.max_attempts or self.max_attempts):
                    job.status = "failed"
                    job.completed_at = now
                    job.error_code = "lease_expired"
                    job.error_detail = "The indexing worker stopped renewing its lease."
                    failed += 1
                else:
                    job.status = "retry_wait"
                    job.available_at = now
                    job.error_code = "lease_expired"
                    job.error_detail = "Recovered after an interrupted indexing worker."
                    recovered += 1
                job.claimed_by = None
                job.lease_expires_at = None
                job.updated_at = now
                self._reset_target_after_recovery(
                    session,
                    job,
                    failed=job.status == "failed",
                    now=now,
                )
        return {"recovered": recovered, "failed": failed}

    @staticmethod
    def _set_target_processing(session: Session, job: IndexingJob) -> None:
        now = utc_now()
        if job.document_id is not None:
            from backend.app.models.knowledge import Document

            document = session.get(Document, job.document_id)
            if document is not None and document.lifecycle_status != "deleted":
                document.indexing_status = "indexing"
                document.lifecycle_status = "indexing"
                document.metadata_ = {
                    **(document.metadata_ or {}),
                    "indexing_stage": "claimed",
                }
        if job.note_id is not None:
            from backend.app.models.workspace_content import NoteIndexState

            state = session.get(NoteIndexState, job.note_id)
            if state is not None:
                state.status = "indexing"
                state.last_error = None
                state.updated_at = now

    @staticmethod
    def _reset_target_after_recovery(
        session: Session,
        job: IndexingJob,
        *,
        failed: bool,
        now: datetime,
    ) -> None:
        status = "failed" if failed else "pending"
        if job.document_id is not None:
            from backend.app.models.knowledge import Document

            document = session.get(Document, job.document_id)
            if document is not None and document.lifecycle_status != "deleted":
                document.indexing_status = status
                document.lifecycle_status = status
                document.metadata_ = {
                    **(document.metadata_ or {}),
                    "indexing_stage": job.status,
                    "indexing_error_code": "lease_expired",
                }
        if job.note_id is not None:
            from backend.app.models.workspace_content import NoteIndexState

            state = session.get(NoteIndexState, job.note_id)
            if state is not None:
                state.status = status
                state.last_error = "lease_expired"
                state.updated_at = now

    def heartbeat(
        self,
        worker_id: str,
        *,
        service_state: str,
        current_job_id: uuid.UUID | None = None,
        metrics: dict[str, Any] | None = None,
        embedding_device: str | None = None,
        embedding_precision: str | None = None,
        reconciliation_state: str | None = None,
        last_reconciliation_at: datetime | None = None,
        error_code: str | None = None,
    ) -> None:
        if self.session_factory is None:
            return
        now = utc_now()
        with self.session_factory() as session, session.begin():
            row = session.get(IndexerWorker, worker_id)
            if row is None:
                row = IndexerWorker(worker_id=worker_id, started_at=now)
                session.add(row)
            row.service_state = service_state
            row.heartbeat_at = now
            row.stopped_at = now if service_state == "stopped" else None
            row.current_job_id = current_job_id
            row.metrics = metrics or row.metrics or {}
            row.embedding_device = embedding_device or row.embedding_device
            row.embedding_precision = embedding_precision or row.embedding_precision
            row.reconciliation_state = reconciliation_state
            if last_reconciliation_at is not None:
                row.last_reconciliation_at = last_reconciliation_at
            row.last_error_code = error_code

    def publish_generation(
        self,
        worker_id: str,
        *,
        bm25_snapshot_path: str | None,
        point_count: int,
        bm25_changed: bool = True,
    ) -> int:
        if self.session_factory is None:
            raise RuntimeError("PostgreSQL is required for index generations.")
        now = utc_now()
        with self.session_factory() as session, session.begin():
            row = session.scalar(
                select(IndexGeneration).where(IndexGeneration.name == "active").with_for_update()
            )
            if row is None:
                row = IndexGeneration(name="active")
                session.add(row)
                session.flush()
            row.generation = int(row.generation or 0) + 1
            if bm25_changed:
                row.bm25_generation = int(row.bm25_generation or 0) + 1
            row.bm25_snapshot_path = bm25_snapshot_path
            row.qdrant_collection = settings.qdrant_collection_name
            row.point_count = max(0, int(point_count))
            row.published_by = worker_id
            row.published_at = now
            row.updated_at = now
            return row.generation

    def status(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            "indexer_state": "unknown",
            "indexer_seen": False,
            "worker_id": None,
            "worker_heartbeat_at": None,
            "queue_counts": {},
            "queue_by_operation": {},
            "queue_depth": 0,
            "active_jobs": [],
            "recent_errors": [],
            "latest_index_generation": 0,
            "bm25_generation": 0,
            "last_successful_index_at": None,
            "qdrant_collection": settings.qdrant_collection_name,
            "cpu_extraction_workers": settings.indexer_extraction_workers,
            "active_batch_limit": settings.indexer_embed_batch_size,
        }
        if self.session_factory is None:
            return values
        with self.session_factory() as session:
            counts = session.execute(
                select(IndexingJob.status, func.count()).group_by(IndexingJob.status)
            ).all()
            operations = session.execute(
                select(IndexingJob.operation, func.count())
                .where(IndexingJob.status.in_(ACTIVE_JOB_STATUSES))
                .group_by(IndexingJob.operation)
            ).all()
            worker = session.scalar(
                select(IndexerWorker).order_by(IndexerWorker.heartbeat_at.desc()).limit(1)
            )
            active_workers = int(
                session.scalar(
                    select(func.count())
                    .select_from(IndexerWorker)
                    .where(
                        IndexerWorker.heartbeat_at
                        >= utc_now()
                        - timedelta(seconds=settings.indexer_heartbeat_stale_seconds),
                        IndexerWorker.service_state.notin_(["stopped", "degraded"]),
                    )
                )
                or 0
            )
            generation = session.get(IndexGeneration, "active")
            last_success = session.scalar(
                select(func.max(IndexingJob.completed_at)).where(IndexingJob.status == "completed")
            )
            active_jobs = list(
                session.scalars(
                    select(IndexingJob)
                    .where(IndexingJob.status.in_(ACTIVE_JOB_STATUSES))
                    .order_by(
                        IndexingJob.priority.desc(),
                        IndexingJob.created_at,
                    )
                    .limit(25)
                )
            )
            recent_errors = list(
                session.scalars(
                    select(IndexingJob)
                    .where(IndexingJob.error_code.is_not(None))
                    .order_by(IndexingJob.updated_at.desc())
                    .limit(10)
                )
            )
        values["queue_counts"] = {str(key): int(value) for key, value in counts}
        values["active_workers"] = active_workers
        values["queue_by_operation"] = {str(key): int(value) for key, value in operations}
        values["queue_depth"] = sum(
            count
            for status, count in values["queue_counts"].items()
            if status in ACTIVE_JOB_STATUSES
        )
        values["active_jobs"] = [
            {
                "job_id": str(job.id),
                "asset_type": job.asset_type,
                "operation": job.operation,
                "status": job.status,
                "priority": int(job.priority or 0),
                "attempts": int(job.attempts or 0),
                "document_id": str(job.document_id) if job.document_id else None,
                "note_id": str(job.note_id) if job.note_id else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
            }
            for job in active_jobs
        ]
        values["recent_errors"] = [
            {
                "job_id": str(job.id),
                "asset_type": job.asset_type,
                "operation": job.operation,
                "status": job.status,
                "error_code": job.error_code,
                "updated_at": job.updated_at.isoformat(),
            }
            for job in recent_errors
        ]
        if worker is not None:
            age = (utc_now() - worker.heartbeat_at).total_seconds()
            values.update(
                indexer_state=worker.service_state if age <= settings.indexer_heartbeat_stale_seconds else "unknown",
                indexer_seen=age <= settings.indexer_heartbeat_stale_seconds,
                worker_id=worker.worker_id,
                worker_heartbeat_at=worker.heartbeat_at.isoformat(),
                reconciliation_state=worker.reconciliation_state,
                last_reconciliation_at=worker.last_reconciliation_at.isoformat() if worker.last_reconciliation_at else None,
                embedding_device=worker.embedding_device,
                embedding_precision=worker.embedding_precision,
                internal_queue_depths=(worker.metrics or {}).get("queue_depths", {}),
                throughput=(worker.metrics or {}).get("throughput", {}),
                reconciliation_metrics=(worker.metrics or {}).get("reconciliation", {}),
                bm25_metrics=(worker.metrics or {}).get("bm25", {}),
                gpu_metrics=(worker.metrics or {}).get("gpu", {}),
                cpu_metrics=(worker.metrics or {}).get("cpu", {}),
                worker_metrics={
                    key: (worker.metrics or {}).get(key)
                    for key in (
                        "gpu_state",
                        "active_embedding_jobs",
                        "chat_priority_active",
                        "chat_priority_wait_seconds",
                        "embedding_model_gpu_resident",
                        "embedding_model_memory",
                        "embedding_device_configured",
                        "embedding_device_actual",
                        "embedding_model_status",
                        "embedding_runtime",
                        "embedding_batch",
                    )
                },
                active_batch_limit=int(
                    ((worker.metrics or {}).get("adaptive_batch") or {}).get(
                        "current",
                        settings.indexer_embed_batch_size,
                    )
                ),
            )
        if generation is not None:
            values.update(
                latest_index_generation=int(generation.generation or 0),
                bm25_generation=int(generation.bm25_generation or 0),
                bm25_snapshot_path=generation.bm25_snapshot_path,
                qdrant_point_count=int(generation.point_count or 0),
                generation_published_at=generation.published_at.isoformat() if generation.published_at else None,
            )
        values["index_fresh"] = bool(
            values["latest_index_generation"] and values["queue_depth"] == 0
        )
        values["last_successful_index_at"] = last_success.isoformat() if last_success else None
        return values

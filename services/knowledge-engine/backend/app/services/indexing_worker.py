"""Background indexing worker for processing pending IndexingJob rows."""

from __future__ import annotations

import logging
import queue
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock, Thread
from time import perf_counter, sleep
from typing import Any, Callable
from sqlalchemy import func, select, update

from backend.app.core.runtime_state import RuntimeState
from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.operations import IndexingJob
from cial_knowledge_os.corpus.metadata import CorpusMetadataStore

logger = logging.getLogger(__name__)

_SENTINEL = object()


class IndexingWorker:
    """Single-threaded FIFO worker that processes indexing jobs sequentially.

    A ``threading.Lock`` prevents concurrent ``prepare_pipeline()`` calls since
    the Phase 4 pipeline is not thread-safe for indexing.  Multiple uploads can
    enqueue work; jobs are drained one at a time.
    """

    def __init__(
        self,
        *,
        engine: Any,
        runtime_state: RuntimeState,
        corpus_sync: Callable[[], Any] | None = None,
    ) -> None:
        self.engine = engine
        self.runtime_state = runtime_state
        self.corpus_sync = corpus_sync
        self._queue: queue.Queue[object] = queue.Queue()
        self._pipeline_lock = Lock()
        self._thread: Thread | None = None
        self._running = False
        self.ready = False
        self.last_error: str | None = None
        self.last_completed_job: str | None = None
        self.max_attempts = 3

    def start(self) -> None:
        """Start the background worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = Thread(
            target=self._worker_loop,
            name="indexing-worker",
            daemon=True,
        )
        self._recover_interrupted_jobs()
        self._thread.start()
        self.ready = self.last_error != "recovery_failed"
        self.enqueue(None)
        logger.info("indexing_worker_started")

    def stop(self) -> None:
        """Signal the worker to exit and wait for it to drain."""
        self._running = False
        self._queue.put(_SENTINEL)
        if self._thread is not None:
            self._thread.join(timeout=30)
        self._thread = None
        self.ready = False
        logger.info("indexing_worker_stopped")

    def enqueue(self, job_id: uuid.UUID | None = None) -> None:
        """Add an indexing job to the work queue.

        If *job_id* is ``None``, the worker will drain all pending jobs from the
        database.  Otherwise it processes the specific job.
        """
        self._queue.put(job_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while self._running:
            try:
                item = self._queue.get(timeout=2.0)
            except queue.Empty:
                item = None

            if item is _SENTINEL:
                break

            try:
                self._drain_pending_jobs(preferred_id=item if isinstance(item, uuid.UUID) else None)
            except Exception:
                self.last_error = "worker_unhandled_error"
                logger.exception("indexing_worker_unhandled_error")

    def _drain_pending_jobs(self, preferred_id: uuid.UUID | None = None) -> None:
        """Process all pending jobs from the database."""
        if SessionLocal is None:
            logger.warning("indexing_worker_no_database")
            return
        if self.runtime_state.snapshot().get("status") == "starting":
            return
        while self._running:
            job_id = self._claim_job(preferred_id)
            preferred_id = None
            if job_id is None:
                return
            self._process_claimed_job(job_id)

    def _claim_job(self, preferred_id: uuid.UUID | None = None) -> uuid.UUID | None:
        """Atomically claim one durable job across backend processes."""
        if SessionLocal is None:
            return None
        with SessionLocal() as session, session.begin():
            statement = select(IndexingJob).where(IndexingJob.status == "pending")
            if preferred_id is not None:
                statement = statement.where(IndexingJob.id == preferred_id)
            job = session.scalar(statement.order_by(IndexingJob.created_at, IndexingJob.id).with_for_update(skip_locked=True).limit(1))
            if job is None:
                return None
            job.status = "running"; job.attempts = int(job.attempts or 0) + 1
            job.started_at = job.updated_at = datetime.now(timezone.utc); job.completed_at = None
            if job.document_version_id:
                version = session.get(DocumentVersion, job.document_version_id)
                if version is not None: version.status = "indexing"
            if job.document_id:
                document = session.get(Document, job.document_id)
                if document is not None and document.lifecycle_status != "deleted":
                    document.indexing_status = document.lifecycle_status = "indexing"
            return job.id

    def _process_single_job(self, job_id: uuid.UUID) -> None:
        """Run one indexing job with proper state transitions."""
        if SessionLocal is None:
            return
        claimed = self._claim_job(job_id)
        if claimed is not None:
            self._process_claimed_job(claimed)

    def _process_claimed_job(self, job_id: uuid.UUID) -> None:
        with SessionLocal() as session:
            job = session.get(IndexingJob, job_id)
            if job is None or job.status != "running": return
            document_path = (job.metadata_ or {}).get("relative_path", "unknown")
            document_id = job.document_id

        logger.info(
            "indexing_job_started",
            extra={
                "event": "indexing",
                "job_id": str(job_id),
                "document_path": document_path,
            },
        )

        started = perf_counter()
        try:
            # Sync corpus metadata first (ensures DB is current)
            if self.corpus_sync is not None:
                try:
                    self.corpus_sync()
                except Exception:
                    logger.exception("indexing_worker_corpus_sync_failed")

            # Run incremental pipeline (this uses manifest to index only changed files)
            with self._pipeline_lock:
                counts = self.engine.prepare_pipeline(
                    force_rebuild_index=False,
                    on_stage=lambda stage, _: self._mark_stage(job_id, stage),
                )
            logger.info("pipeline_state_refreshed", extra={"event": "pipeline_state_refreshed", "job_id": str(job_id)})
            models_ready, model_message = self.engine.check_ollama_model()

            elapsed_ms = int((perf_counter() - started) * 1000)

            # --- Mark succeeded ---
            with SessionLocal() as session:
                job = session.get(IndexingJob, job_id)
                if job is None: return
                self._persist_and_verify(session, job)
                job.status = "succeeded"; job.message = f"Indexed successfully in {elapsed_ms}ms."
                job.completed_at = job.updated_at = datetime.now(timezone.utc); job.error_detail = None
                # Update document status
                if document_id is not None:
                    document = session.get(Document, document_id)
                    if document is not None:
                        if document.lifecycle_status != "deleted":
                            document.indexed = True
                            document.indexing_status = document.lifecycle_status = "indexed"
                            document.indexed_at = datetime.now(timezone.utc)
                if job.document_version_id is not None:
                    version = session.get(DocumentVersion, job.document_version_id)
                    if version is not None:
                        version.status = "indexed"
                session.commit()

            # Update runtime state
            if self.engine.is_ready() and models_ready:
                self.runtime_state.set_ready(
                    message="Background incremental indexing completed; knowledge engine is ready.",
                    documents_seen=counts.get("documents_seen", 0),
                    documents_indexed=counts.get("documents_indexed", 0),
                )
                logger.info(
                    "knowledge_engine_ready",
                    extra={
                        "event": "knowledge_engine_state",
                        "ready": True,
                        "stage": "ready",
                        "reason": "background_incremental_indexing_completed",
                    },
                )
            else:
                self.runtime_state.update(
                    status="degraded",
                    stage="loading_reranker",
                    engine_ready=False,
                    models_ready=False,
                    index_fresh=True,
                    message=model_message,
                )

            self.last_completed_job = str(job_id); self.last_error = None
            logger.info(
                "index_job_completed",
                extra={
                    "event": "indexing",
                    "job_id": str(job_id),
                    "document_path": document_path,
                    "elapsed_ms": elapsed_ms,
                    "documents_indexed": counts.get("documents_indexed", 0),
                },
            )

        except Exception as exc:
            elapsed_ms = int((perf_counter() - started) * 1000)
            error_message = str(exc)

            # --- Mark failed ---
            try:
                with SessionLocal() as session:
                    job = session.get(IndexingJob, job_id)
                    retry = job is not None and int(job.attempts or 0) < self.max_attempts and not isinstance(exc, (ValueError, ImportError))
                    if job is not None:
                        job.status = "pending" if retry else "failed"
                        job.message = "Retry scheduled after transient indexing failure." if retry else "Indexing failed."
                        job.error_detail = type(exc).__name__
                        job.updated_at = datetime.now(timezone.utc)
                        job.completed_at = None if retry else datetime.now(timezone.utc)
                    if job is not None and job.document_id is not None:
                        document = session.get(Document, job.document_id)
                        if document is not None:
                            if document.lifecycle_status != "deleted":
                                document.indexing_status = document.lifecycle_status = "pending" if retry else "failed"
                    if job is not None and job.document_version_id is not None:
                        version = session.get(DocumentVersion, job.document_version_id)
                        if version is not None:
                            version.status = "pending" if retry else "failed"
                    session.commit()
                    if retry:
                        logger.warning("index_job_retry_scheduled", extra={"event": "index_job_retry_scheduled", "job_id": str(job_id)})
                        sleep(min(2 ** int(job.attempts or 1), 10))
            except Exception:
                logger.exception("indexing_job_fail_update_error")

            self.last_error = type(exc).__name__
            logger.error(
                "index_job_failed",
                extra={
                    "event": "indexing",
                    "job_id": str(job_id),
                    "document_path": document_path,
                    "elapsed_ms": elapsed_ms,
                    "error": error_message,
                },
                exc_info=True,
            )

    def _recover_interrupted_jobs(self) -> None:
        if SessionLocal is None: return
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        try:
            with SessionLocal() as session, session.begin():
                session.execute(update(IndexingJob).where(
                    IndexingJob.status == "running", IndexingJob.updated_at < cutoff,
                    IndexingJob.attempts < self.max_attempts,
                ).values(status="pending", message="Recovered after interrupted worker."))
        except Exception:
            self.last_error = "recovery_failed"; logger.exception("indexing_worker_recovery_failed")

    def _mark_stage(self, job_id: uuid.UUID, stage: str) -> None:
        mapped = {"load":"extracting", "loaded":"extracting", "chunk":"chunking", "chunked":"chunking",
                  "embed":"embedding", "embedded":"embedding", "index":"vector_index", "indexed":"lexical_index",
                  "reranker":"refreshing", "ready":"verifying"}.get(stage, stage)
        if SessionLocal is None: return
        with SessionLocal() as session:
            job = session.get(IndexingJob, job_id)
            if job is None or job.status != "running": return
            job.metadata_ = {**(job.metadata_ or {}), "stage": mapped}
            job.updated_at = datetime.now(timezone.utc); session.commit()
        logger.info("index_stage_changed", extra={"event":"index_stage_changed", "job_id":str(job_id), "stage":mapped})

    def _persist_and_verify(self, session, job: IndexingJob) -> None:
        """Verify live dense/BM25 state and persist stable chunk metadata."""
        from backend.app.models.knowledge import DocumentChunk
        pipeline = self.engine._pipeline
        metadata = job.metadata_ or {}
        action = metadata.get("action")
        document_id = str(job.document_id) if job.document_id else None
        version_id = str(job.document_version_id) if job.document_version_id else None
        chunks = [chunk for chunk in (getattr(pipeline, "chunks", None) or [])
                  if str(chunk.metadata.get("document_id")) == document_id
                  and str(chunk.metadata.get("document_version_id")) == version_id]
        lexical = getattr(getattr(pipeline, "bm25_retriever", None), "_chunks", []) or []
        lexical_matches = [chunk for chunk in lexical
                           if str((chunk.get("metadata") or {}).get("document_id")) == document_id
                           and str((chunk.get("metadata") or {}).get("document_version_id")) == version_id]
        if action == "deleted":
            if chunks or lexical_matches: raise RuntimeError("Deleted document remains in live retrieval state")
            if job.document_id: session.query(DocumentChunk).filter(DocumentChunk.document_id == job.document_id).delete(synchronize_session=False)
            return
        if not chunks or not lexical_matches:
            raise RuntimeError("Current document is absent from dense or BM25 live state")
        required = {"document_id", "document_version_id", "workspace_id", "storage_scope",
                    "department_id", "visibility", "lifecycle_status", "repository_id", "relative_path"}
        for chunk in chunks:
            missing = {field for field in required if chunk.metadata.get(field) in (None, "")}
            if chunk.metadata.get("storage_scope") == "personal" and not chunk.metadata.get("owner_user_id"):
                missing.add("owner_user_id")
            if missing: raise RuntimeError("Current vectors lack required authorization metadata")
        if job.document_id:
            session.query(DocumentChunk).filter(DocumentChunk.document_id == job.document_id).delete(synchronize_session=False)
        for index, chunk in enumerate(chunks):
            item = chunk.metadata
            from cial_knowledge_os.vectorstore import _stable_point_id
            session.add(DocumentChunk(
                document_id=job.document_id, document_version_id=job.document_version_id,
                chunk_id=str(item.get("chunk_id") or f"{document_id}:{index}"), chunk_index=index,
                page=item.get("page_number"), section=item.get("section"), text=chunk.page_content,
                text_preview=chunk.page_content[:500], token_count=item.get("token_count"), metadata_=dict(item),
                qdrant_point_id=_stable_point_id(chunk),
            ))

    def status(self) -> dict[str, object]:
        values = {"index_worker_ready": self.ready, "last_completed_job": self.last_completed_job, "last_error": self.last_error,
                  "pending_jobs": 0, "processing_jobs": 0, "failed_jobs": 0}
        if SessionLocal is None: return values
        try:
            with SessionLocal() as session:
                rows = dict(session.execute(select(IndexingJob.status, func.count()).group_by(IndexingJob.status)).all())
            values.update(pending_jobs=int(rows.get("pending", 0)), processing_jobs=int(rows.get("running", 0)), failed_jobs=int(rows.get("failed", 0)))
        except Exception: pass
        return values

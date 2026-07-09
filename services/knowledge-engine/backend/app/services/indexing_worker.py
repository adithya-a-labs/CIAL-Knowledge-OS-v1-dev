"""Background indexing worker for processing pending IndexingJob rows."""

from __future__ import annotations

import logging
import queue
import uuid
from datetime import datetime, timezone
from threading import Lock, Thread
from time import perf_counter
from typing import Any, Callable

from backend.app.core.runtime_state import RuntimeState
from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document
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
        self._thread.start()
        logger.info("indexing_worker_started")

    def stop(self) -> None:
        """Signal the worker to exit and wait for it to drain."""
        self._running = False
        self._queue.put(_SENTINEL)
        if self._thread is not None:
            self._thread.join(timeout=30)
            self._thread = None
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
                continue

            if item is _SENTINEL:
                break

            try:
                if item is None:
                    self._drain_pending_jobs()
                else:
                    self._process_single_job(item)
            except Exception:
                logger.exception("indexing_worker_unhandled_error")

    def _drain_pending_jobs(self) -> None:
        """Process all pending jobs from the database."""
        if SessionLocal is None:
            logger.warning("indexing_worker_no_database")
            return
        with SessionLocal() as session:
            store = CorpusMetadataStore(session)
            jobs = store.pending_jobs()
            if not jobs:
                logger.info("indexing_worker_no_pending_jobs")
                return
            logger.info(
                "indexing_worker_draining",
                extra={"pending_count": len(jobs)},
            )
        # Process each job individually (fresh session per job for isolation)
        for job in jobs:
            self._process_single_job(job.id)

    def _process_single_job(self, job_id: uuid.UUID) -> None:
        """Run one indexing job with proper state transitions."""
        if SessionLocal is None:
            return

        # --- Mark running ---
        with SessionLocal() as session:
            store = CorpusMetadataStore(session)
            job = session.get(IndexingJob, job_id)
            if job is None:
                logger.warning(
                    "indexing_job_not_found",
                    extra={"job_id": str(job_id)},
                )
                return
            if job.status != "pending":
                logger.info(
                    "indexing_job_already_processed",
                    extra={"job_id": str(job_id), "status": job.status},
                )
                return

            document_path = (job.metadata_ or {}).get("relative_path", "unknown")
            document_id = job.document_id

            store.mark_job_running(job_id)
            session.commit()

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
                )

            elapsed_ms = int((perf_counter() - started) * 1000)

            # --- Mark succeeded ---
            with SessionLocal() as session:
                store = CorpusMetadataStore(session)
                store.mark_job_succeeded(
                    job_id,
                    message=f"Indexed successfully in {elapsed_ms}ms.",
                )
                # Update document status
                if document_id is not None:
                    document = session.get(Document, document_id)
                    if document is not None:
                        document.indexed = True
                        document.indexing_status = "indexed"
                        document.indexed_at = datetime.now(timezone.utc)
                session.commit()

            # Update runtime state
            self.runtime_state.update(
                documents_indexed=counts.get("documents_indexed", 0),
                index_fresh=True,
            )

            logger.info(
                "indexing_job_succeeded",
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
                    store = CorpusMetadataStore(session)
                    store.mark_job_failed(job_id, error=error_message)
                    session.commit()
            except Exception:
                logger.exception("indexing_job_fail_update_error")

            logger.error(
                "indexing_job_failed",
                extra={
                    "event": "indexing",
                    "job_id": str(job_id),
                    "document_path": document_path,
                    "elapsed_ms": elapsed_ms,
                    "error": error_message,
                },
                exc_info=True,
            )

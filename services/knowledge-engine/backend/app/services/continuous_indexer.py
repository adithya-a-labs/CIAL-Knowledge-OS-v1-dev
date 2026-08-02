"""Always-running incremental indexer orchestration."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
import signal
import subprocess
from threading import Event, Lock, Thread
import time
from typing import Any
import uuid

import numpy as np
from sqlalchemy import func, select, text

from backend.app.core.application_config import configured_corpus_root, validate_repository_path
from backend.app.core.config import set_runtime_corpus_root, settings
from backend.app.core.paths import DEFAULT_CORPUS_ROOT
from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document, DocumentChunk, DocumentVersion
from backend.app.models.operations import IndexGeneration, IndexingJob
from backend.app.models.workspace_content import Note, NoteIndexState, NoteVersion
from backend.app.services.indexing_queue import DurableIndexQueue, utc_now
from backend.app.services.gpu_resource_coordinator import GpuResourceCoordinator
from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from backend.app.services.managed_workspace_ingestion import ManagedWorkspaceIngestionService
from backend.app.services.note_indexing_service import (
    NoteIndexingService,
    PreparedNoteRevision,
    SupersededNoteRevision,
    _blocks as note_blocks,
    note_relative_path,
)
from cial_knowledge_os.bm25_snapshot import write_bm25_snapshot
from cial_knowledge_os.corpus.service import CorpusService
from cial_knowledge_os.corpus.watcher import CorpusWatcher

logger = logging.getLogger(__name__)
OCR_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"})


@dataclass(frozen=True, slots=True)
class ChunkEnvelope:
    job_id: uuid.UUID
    asset_id: uuid.UUID
    chunk: Any
    token_count: int
    chunk_index: int = 0


class CrossDocumentBatcher:
    """Bound a batch by chunk count, estimated tokens, and wait time."""

    def __init__(self, *, max_chunks: int, max_tokens: int, max_wait_ms: int) -> None:
        if min(max_chunks, max_tokens, max_wait_ms) <= 0:
            raise ValueError("Batch limits must be positive.")
        self.max_chunks = max_chunks
        self.max_tokens = max_tokens
        self.max_wait_seconds = max_wait_ms / 1000
        self._items: list[ChunkEnvelope] = []
        self._tokens = 0
        self._started_at: float | None = None

    @staticmethod
    def estimate_tokens(text_value: str) -> int:
        return max(1, (len(text_value) + 3) // 4)

    def add(self, item: ChunkEnvelope, *, now: float | None = None) -> list[ChunkEnvelope] | None:
        timestamp = time.monotonic() if now is None else now
        if self._items and (
            len(self._items) >= self.max_chunks
            or self._tokens + item.token_count > self.max_tokens
        ):
            batch = self.flush()
            self._append(item, timestamp)
            return batch
        self._append(item, timestamp)
        if len(self._items) >= self.max_chunks or self._tokens >= self.max_tokens:
            return self.flush()
        return None

    def due(self, *, now: float | None = None) -> bool:
        timestamp = time.monotonic() if now is None else now
        return bool(
            self._items
            and self._started_at is not None
            and timestamp - self._started_at >= self.max_wait_seconds
        )

    def flush(self) -> list[ChunkEnvelope]:
        batch = self._items
        self._items = []
        self._tokens = 0
        self._started_at = None
        return batch

    def _append(self, item: ChunkEnvelope, timestamp: float) -> None:
        if not self._items:
            self._started_at = timestamp
        self._items.append(item)
        self._tokens += item.token_count


@dataclass(slots=True)
class AdaptiveBatchController:
    """Grow healthy GPU batches and reduce them immediately after CUDA OOM."""

    minimum: int
    current: int
    maximum: int
    latency_tolerance: float = 1.15
    vram_target_ratio: float = 0.85
    last_seconds_per_chunk: float | None = None
    oom_count: int = 0

    def __post_init__(self) -> None:
        if not 0 < self.minimum <= self.current <= self.maximum:
            raise ValueError("Adaptive batch limits must satisfy 0 < min <= current <= max.")
        if self.latency_tolerance < 1:
            raise ValueError("Adaptive batch latency tolerance must be at least 1.")
        if not 0 < self.vram_target_ratio <= 1:
            raise ValueError("Adaptive batch VRAM target must be in (0, 1].")

    def record_success(
        self,
        *,
        batch_size: int,
        duration_seconds: float,
        vram_ratio: float | None,
    ) -> int:
        seconds_per_chunk = duration_seconds / max(1, batch_size)
        latency_healthy = (
            self.last_seconds_per_chunk is None
            or seconds_per_chunk <= self.last_seconds_per_chunk * self.latency_tolerance
        )
        memory_healthy = vram_ratio is None or vram_ratio < self.vram_target_ratio
        filled_active_batch = batch_size >= self.current
        self.last_seconds_per_chunk = seconds_per_chunk
        if filled_active_batch and latency_healthy and memory_healthy:
            self.current = min(self.maximum, max(self.current + 1, self.current * 2))
        return self.current

    def record_oom(self, *, attempted_batch_size: int) -> int:
        self.oom_count += 1
        self.current = max(self.minimum, min(self.current, max(1, attempted_batch_size // 2)))
        return self.current


@dataclass(slots=True)
class PreparedAsset:
    job_id: uuid.UUID
    asset_type: str
    asset_id: uuid.UUID
    chunks: list[Any]
    document_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    note: PreparedNoteRevision | None = None
    vectors: list[np.ndarray | None] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ClaimedTarget:
    job_id: uuid.UUID
    asset_type: str
    operation: str
    document_id: uuid.UUID | None
    document_version_id: uuid.UUID | None
    note_id: uuid.UUID | None
    note_version_id: uuid.UUID | None
    metadata: dict[str, Any]


class ContinuousIndexer:
    """Coordinates metadata reconciliation and the bounded indexing stages."""

    def __init__(
        self,
        *,
        engine: KnowledgeEngineService | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.engine = engine or KnowledgeEngineService()
        self.worker_id = worker_id or settings.indexer_worker_id or f"cial-indexer-{uuid.uuid4().hex[:12]}"
        self.queue = DurableIndexQueue()
        self.corpus = CorpusService(
            root=settings.corpus_root_path,
            session_factory=SessionLocal,
            hash_algorithm=settings.corpus_hash,
            batch_size=settings.metadata_batch_size,
            repository_id=settings.corpus_repository_id,
        )
        self.workspace = ManagedWorkspaceIngestionService(
            root=settings.workspace_root_path,
            session_factory=SessionLocal,
        )
        self.stop_event = Event()
        self._heartbeat_stop = Event()
        self._accepting = True
        self._active_jobs: set[uuid.UUID] = set()
        self._active_lock = Lock()
        self._heartbeat_thread: Thread | None = None
        self._watchers: list[CorpusWatcher] = []
        self._writer_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="cial-qdrant-writer",
        )
        self._write_futures: set[Future[None]] = set()
        self._last_reconcile = 0.0
        self._last_recovery = 0.0
        self._bm25_dirty_since: float | None = None
        self._started_monotonic = time.monotonic()
        self._last_embedding_activity = time.monotonic()
        self._gpu_coordinator = GpuResourceCoordinator()
        self._batch_controller = AdaptiveBatchController(
            minimum=settings.indexer_embed_min_batch_size,
            current=settings.indexer_embed_batch_size,
            maximum=settings.indexer_embed_max_batch_size,
            latency_tolerance=settings.indexer_embed_growth_latency_tolerance,
            vram_target_ratio=settings.indexer_embed_vram_target_ratio,
        )
        self._metrics: dict[str, Any] = {
            "queue_depths": {"prepared": 0, "embedding": 0, "writing": 0},
            "throughput": {
                "jobs_completed": 0,
                "documents_completed": 0,
                "chunks_embedded": 0,
                "chunks_reused": 0,
                "gpu_batches": 0,
                "cpu_batches": 0,
            },
            "gpu_policy": settings.indexer_gpu_policy,
            "gpu_state": "initializing",
            "active_embedding_jobs": 0,
            "chat_priority_active": False,
            "chat_priority_wait_seconds": 0.0,
            "embedding_model_gpu_resident": False,
            "embedding_device_configured": settings.indexer_device,
            "embedding_device_actual": "unknown",
            "embedding_model_status": "initializing",
            "embedding_batch": {},
            "adaptive_batch": {
                "current": self._batch_controller.current,
                "minimum": self._batch_controller.minimum,
                "maximum": self._batch_controller.maximum,
                "oom_count": 0,
            },
        }
        self.actual_device = "unknown"
        self.actual_precision = settings.indexer_precision

    def run(self) -> None:
        if not settings.indexer_enabled:
            logger.info("indexer_disabled")
            return
        if SessionLocal is None:
            raise RuntimeError("The standalone indexer requires DATABASE_URL.")
        self.queue.heartbeat(self.worker_id, service_state="starting")
        try:
            runtime = self.engine.prepare_indexer_runtime()
        except Exception:
            self.queue.heartbeat(
                self.worker_id,
                service_state="degraded",
                error_code="runtime_initialization_failed",
            )
            raise
        self.actual_device = str(runtime.get("embedding_device") or settings.indexer_device)
        self.actual_precision = str(runtime.get("embedding_precision") or settings.indexer_precision)
        embedding_runtime = dict(runtime.get("embedding_runtime") or {})
        self._metrics["embedding_device_configured"] = embedding_runtime.get(
            "embedding_device_configured", settings.indexer_device
        )
        self._metrics["embedding_device_actual"] = embedding_runtime.get(
            "embedding_device_actual", self.actual_device
        )
        self._metrics["embedding_model_status"] = (
            "ready_gpu"
            if str(self._metrics["embedding_device_actual"]).startswith("cuda")
            else "ready_cpu"
        )
        self._metrics["embedding_runtime"] = embedding_runtime
        self._metrics["gpu_state"] = (
            "ready" if self.actual_device.startswith("cuda") else "cpu"
        )
        self._metrics["embedding_model_gpu_resident"] = self.actual_device.startswith("cuda")
        logger.info(
            "indexer_model_loaded",
            extra={
                "event": "indexer_model_loaded",
                "worker_id": self.worker_id,
                "configured_device": settings.indexer_device,
                "actual_device": self.actual_device,
                "precision": self.actual_precision,
            },
        )
        recovered = self.queue.recover_expired()
        logger.info("expired_jobs_recovered", extra={"event": "lease_recovery", **recovered})
        self._start_heartbeat()
        try:
            self.reconcile()
            self._start_watchers()
            self.queue.heartbeat(
                self.worker_id,
                service_state="watching",
                embedding_device=self.actual_device,
                embedding_precision=self.actual_precision,
                metrics=self._metrics,
            )
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now - self._last_reconcile >= settings.corpus_reconcile_interval_seconds:
                    self.reconcile()
                if now - self._last_recovery >= max(10, settings.indexer_lease_seconds // 2):
                    self.queue.recover_expired()
                    self._last_recovery = now
                processed = self.drain_once()
                if processed == 0:
                    # Never enter the watching/idle wait with a pending lexical
                    # generation. Continuous bursts are debounced; queue-empty
                    # publication is immediate.
                    if not self._write_futures:
                        self._flush_bm25_if_due(force=True)
                    self._release_idle_gpu_if_due()
                    self.queue.heartbeat(
                        self.worker_id,
                        service_state="active" if self._write_futures else "watching",
                        embedding_device=self.actual_device,
                        embedding_precision=self.actual_precision,
                        metrics=self._metrics,
                    )
                    self.stop_event.wait(settings.indexer_poll_seconds)
        finally:
            self._accepting = False
            for watcher in self._watchers:
                watcher.stop()
            self.stop_event.set()
            self._writer_pool.shutdown(wait=True, cancel_futures=False)
            self._harvest_writes()
            self._heartbeat_stop.set()
            if self._heartbeat_thread is not None:
                self._heartbeat_thread.join(timeout=5)
            self._flush_bm25_if_due(force=True)
            self.queue.heartbeat(
                self.worker_id,
                service_state="stopped",
                embedding_device=self.actual_device,
                embedding_precision=self.actual_precision,
                metrics=self._metrics,
            )
            self.engine.close()
            logger.info("indexer_stopped", extra={"event": "indexer_shutdown", "worker_id": self.worker_id})

    def stop(self) -> None:
        self._accepting = False
        self.stop_event.set()

    def reconcile(self, changed_paths: list[Path] | None = None) -> dict[str, Any]:
        """One metadata-only reconciliation under a PostgreSQL advisory lock."""

        self.queue.heartbeat(
            self.worker_id,
            service_state="reconciling",
            reconciliation_state="running",
            embedding_device=self.actual_device,
            metrics=self._metrics,
        )
        lock_acquired = False
        lock_session = None
        try:
            self._refresh_repository_config()
            validation = validate_repository_path(settings.corpus_root_path)
            if not validation.valid:
                raise RuntimeError(
                    f"Configured enterprise repository is invalid: {validation.message}"
                )
            lock_session = SessionLocal()
            try:
                lock_acquired = bool(
                    lock_session.scalar(
                        text("select pg_try_advisory_lock(hashtext('cial-continuous-reconcile'))")
                    )
                )
            except Exception:
                # Non-PostgreSQL unit fixtures do not support advisory locks.
                lock_acquired = True
            if not lock_acquired:
                return {"skipped": True, "reason": "reconciliation_already_running"}
            enterprise_root = settings.corpus_root_path.resolve()
            workspace_root = settings.workspace_root_path.resolve()
            enterprise_paths = [
                path
                for path in changed_paths or ()
                if path == enterprise_root or enterprise_root in path.parents
            ]
            personal_paths = [
                path
                for path in changed_paths or ()
                if path == workspace_root or workspace_root in path.parents
            ]
            enterprise = self.corpus.sync(force_hash_paths=enterprise_paths)
            personal = self.workspace.sync(force_hash_paths=personal_paths)
            completed = utc_now()
            self._last_reconcile = time.monotonic()
            enterprise_counts = enterprise.to_dict()
            self._metrics["reconciliation"] = {
                key: value
                for key, value in enterprise_counts.items()
                if key != "message"
            }
            self._metrics["reconciliation"]["personal_jobs_created"] = int(personal)
            self._metrics["reconciliation"]["completed_at"] = completed.isoformat()
            self.queue.heartbeat(
                self.worker_id,
                service_state="active",
                reconciliation_state="completed",
                last_reconciliation_at=completed,
                embedding_device=self.actual_device,
                metrics=self._metrics,
            )
            payload = {
                "enterprise": enterprise_counts,
                "personal": personal,
                "targeted_event_paths": len(changed_paths or ()),
            }
            logger.info("indexer_reconciliation_completed", extra={"event": "reconciliation", **payload})
            return payload
        except Exception:
            self.queue.heartbeat(
                self.worker_id,
                service_state="degraded",
                reconciliation_state="failed",
                error_code="reconciliation_failed",
                embedding_device=self.actual_device,
                metrics=self._metrics,
            )
            raise
        finally:
            if lock_acquired and lock_session is not None:
                try:
                    lock_session.execute(
                        text("select pg_advisory_unlock(hashtext('cial-continuous-reconcile'))")
                    )
                    lock_session.commit()
                except Exception:
                    lock_session.rollback()
            if lock_session is not None:
                lock_session.close()

    def _refresh_repository_config(self) -> None:
        latest = configured_corpus_root(DEFAULT_CORPUS_ROOT).resolve()
        if latest == settings.corpus_root_path.resolve():
            return
        restart_watchers = bool(self._watchers)
        for watcher in self._watchers:
            watcher.stop()
        self._watchers.clear()
        set_runtime_corpus_root(latest)
        self.corpus = CorpusService(
            root=settings.corpus_root_path,
            session_factory=SessionLocal,
            hash_algorithm=settings.corpus_hash,
            batch_size=settings.metadata_batch_size,
            repository_id=settings.corpus_repository_id,
        )
        if restart_watchers:
            self._start_watchers()
        logger.info(
            "indexer_repository_configuration_reloaded",
            extra={
                "event": "repository_configuration",
                "repository_id": settings.corpus_repository_id,
            },
        )

    def drain_once(self) -> int:
        if not self._accepting:
            return 0
        self._harvest_writes()
        write_capacity = settings.indexer_write_queue_size - len(self._write_futures)
        if write_capacity <= 0:
            return 0
        targets: list[ClaimedTarget] = []
        claim_limit = min(
            settings.indexer_prepared_queue_size,
            write_capacity,
        )
        if settings.indexer_gpu_policy == "balanced":
            claim_limit = min(
                claim_limit,
                max(2, settings.indexer_extraction_workers * 2),
            )
        for _ in range(claim_limit):
            job_id = self.queue.claim(self.worker_id)
            if job_id is None:
                break
            with self._active_lock:
                self._active_jobs.add(job_id)
            target = self._load_target(job_id)
            if target is not None:
                targets.append(target)
                logger.info(
                    "index_started",
                    extra={
                        "event": "index_started",
                        "job_id": str(job_id),
                        "asset_type": target.asset_type,
                        "operation": target.operation,
                    },
                )
            else:
                self._remove_active(job_id)
        if len(targets) == 1 and self._accepting:
            deadline = time.monotonic() + settings.indexer_embed_max_wait_ms / 1000
            while len(targets) < claim_limit and time.monotonic() < deadline:
                job_id = self.queue.claim(self.worker_id)
                if job_id is None:
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        self.stop_event.wait(min(0.01, remaining))
                    continue
                with self._active_lock:
                    self._active_jobs.add(job_id)
                target = self._load_target(job_id)
                if target is not None:
                    targets.append(target)
                    logger.info(
                        "index_started",
                        extra={
                            "event": "index_started",
                            "job_id": str(job_id),
                            "asset_type": target.asset_type,
                            "operation": target.operation,
                        },
                    )
                else:
                    self._remove_active(job_id)
        if not targets:
            return 0

        self._metrics["queue_depths"]["prepared"] = len(targets)
        self.queue.heartbeat(
            self.worker_id,
            service_state="active",
            embedding_device=self.actual_device,
            embedding_precision=self.actual_precision,
            metrics=self._metrics,
        )
        ready: list[PreparedAsset] = []
        extraction_futures: dict[
            Future[list[Any]],
            tuple[ClaimedTarget, float],
        ] = {}
        with ThreadPoolExecutor(
            max_workers=settings.indexer_extraction_workers,
            thread_name_prefix="cial-extract",
        ) as pool, ThreadPoolExecutor(
            max_workers=settings.indexer_ocr_workers,
            thread_name_prefix="cial-ocr",
        ) as ocr_pool:
            for target in targets:
                if (
                    target.asset_type == "document"
                    and target.operation in {"upsert_version", "reprocess_version"}
                    and target.document_id
                    and target.document_version_id
                ):
                    self.queue.transition(target.job_id, self.worker_id, "extracting")
                    executor = ocr_pool if self._is_ocr_target(target) else pool
                    extraction_futures[
                        executor.submit(
                            self.engine.extract_document_version,
                            target.document_id,
                            target.document_version_id,
                        )
                    ] = (target, time.monotonic())
                elif target.asset_type == "note" and target.note_id:
                    try:
                        self.queue.transition(target.job_id, self.worker_id, "extracting")
                        revision = int(target.metadata.get("note_revision") or 0)
                        action = str(target.metadata.get("action") or "index")
                        with SessionLocal() as session:
                            note = NoteIndexingService(session, self.engine).prepare(
                                target.note_id,
                                revision,
                                action,
                            )
                        self.queue.transition(target.job_id, self.worker_id, "chunked")
                        ready.append(
                            PreparedAsset(
                                job_id=target.job_id,
                                asset_type="note",
                                asset_id=target.note_id,
                                chunks=note.chunks,
                                note=note,
                            )
                        )
                    except SupersededNoteRevision as exc:
                        self.queue.supersede(
                            target.job_id,
                            self.worker_id,
                            message=str(exc),
                        )
                        self._remove_active(target.job_id)
                    except Exception as exc:
                        self._handle_failure(target.job_id, exc)
                else:
                    self._process_non_document_upsert(target)
            for future in as_completed(extraction_futures):
                target, extraction_started = extraction_futures[future]
                try:
                    chunks = future.result()
                    extraction_ms = round(
                        (time.monotonic() - extraction_started) * 1000,
                        2,
                    )
                    self._metrics["throughput"]["chunks_extracted"] = (
                        int(self._metrics["throughput"].get("chunks_extracted", 0))
                        + len(chunks)
                    )
                    logger.info(
                        "document_extraction_completed",
                        extra={
                            "event": "document_extraction",
                            "job_id": str(target.job_id),
                            "chunks": len(chunks),
                            "elapsed_ms": extraction_ms,
                            "format": (
                                str(chunks[0].metadata.get("extension") or "unknown")
                                if chunks
                                else "unknown"
                            ),
                            "ocr_used": any(
                                bool(chunk.metadata.get("ocr_status"))
                                for chunk in chunks
                            ),
                        },
                    )
                    self.queue.transition(target.job_id, self.worker_id, "chunked")
                    ready.append(
                        PreparedAsset(
                            job_id=target.job_id,
                            asset_type="document",
                            asset_id=target.document_id,  # type: ignore[arg-type]
                            document_id=target.document_id,  # type: ignore[arg-type]
                            version_id=target.document_version_id,  # type: ignore[arg-type]
                            chunks=chunks,
                        )
                    )
                    # Once two assets are ready, embedding begins while the CPU
                    # pool continues extracting any outstanding futures.
                    if len(ready) >= 2:
                        self._embed_and_write(ready)
                        ready = []
                except Exception as exc:
                    self._handle_failure(target.job_id, exc)

        if ready:
            self._embed_and_write(ready)
        self._metrics["queue_depths"] = {
            "prepared": 0,
            "embedding": 0,
            "writing": len(self._write_futures),
        }
        return len(targets)

    @staticmethod
    def _is_ocr_target(target: ClaimedTarget) -> bool:
        relative_path = str(target.metadata.get("relative_path") or "")
        return Path(relative_path).suffix.casefold() in OCR_EXTENSIONS

    def _embed_and_write(self, assets: list[PreparedAsset]) -> None:
        by_job = {item.job_id: item for item in assets}
        for item in assets:
            self.queue.transition(item.job_id, self.worker_id, "embedding")
            item.vectors = [None] * len(item.chunks)
            if item.asset_type == "document" and item.document_id is not None:
                reused = self.engine.reusable_document_chunk_embeddings(
                    item.document_id,
                    item.chunks,
                )
                for chunk_index, vector in reused.items():
                    item.vectors[chunk_index] = vector
                self._metrics["throughput"]["chunks_reused"] += len(reused)
                if reused:
                    logger.info(
                        "chunk_embeddings_reused",
                        extra={
                            "event": "chunk_embeddings_reused",
                            "job_id": str(item.job_id),
                            "reused": len(reused),
                            "total": len(item.chunks),
                        },
                    )
        batcher = CrossDocumentBatcher(
            max_chunks=min(
                self._batch_controller.current,
                settings.indexer_embed_queue_size,
            ),
            max_tokens=settings.indexer_embed_max_batch_tokens,
            max_wait_ms=settings.indexer_embed_max_wait_ms,
        )
        batches: list[list[ChunkEnvelope]] = []
        # Round-robin assembly prevents a large document from monopolizing a
        # batch when chunks from other assets are already available.
        positions = {item.job_id: 0 for item in assets}
        remaining = list(assets)
        while remaining:
            next_remaining: list[PreparedAsset] = []
            for item in remaining:
                position = positions[item.job_id]
                if position >= len(item.chunks):
                    continue
                chunk = item.chunks[position]
                positions[item.job_id] = position + 1
                if item.vectors[position] is None:
                    envelope = ChunkEnvelope(
                        job_id=item.job_id,
                        asset_id=item.asset_id,
                        chunk=chunk,
                        token_count=CrossDocumentBatcher.estimate_tokens(chunk.page_content),
                        chunk_index=position,
                    )
                    ready = batcher.add(envelope)
                    if ready:
                        batches.append(ready)
                if positions[item.job_id] < len(item.chunks):
                    next_remaining.append(item)
            remaining = next_remaining
        remainder = batcher.flush()
        if remainder:
            batches.append(remainder)

        try:
            self._metrics["queue_depths"]["embedding"] = sum(
                len(item.chunks) for item in assets
            )
            self._metrics["active_embedding_jobs"] = len(assets)
            for batch in batches:
                self._yield_to_chat_if_needed()
                batch_started = time.monotonic()
                self._metrics["gpu_state"] = (
                    "embedding" if self.actual_device.startswith("cuda") else "cpu"
                )
                vectors = self._embed_with_oom_reduction(batch)
                self._last_embedding_activity = time.monotonic()
                batch_metrics = dict(
                    getattr(self.engine, "_last_embedding_batch_metrics", {}) or {}
                )
                self._metrics["embedding_batch"] = batch_metrics
                self._metrics["embedding_device_actual"] = batch_metrics.get(
                    "device", self._metrics.get("embedding_device_actual")
                )
                self._metrics["embedding_model_gpu_resident"] = bool(
                    getattr(self.engine, "_indexer_embedding_gpu_resident", False)
                )
                self._metrics["embedding_model_status"] = (
                    "embedding_gpu"
                    if self._metrics["embedding_model_gpu_resident"]
                    else "embedding_cpu"
                )
                self._metrics["gpu_state"] = (
                    "embedding"
                    if self._metrics["embedding_model_gpu_resident"]
                    else "cpu_cooperative"
                    if settings.indexer_gpu_cooperative_mode
                    else "cpu"
                )
                inference_seconds = max(time.monotonic() - batch_started, 0.000001)
                for envelope, vector in zip(batch, vectors, strict=True):
                    by_job[envelope.job_id].vectors[envelope.chunk_index] = np.asarray(vector)
                batch_counter = (
                    "gpu_batches"
                    if self._metrics["embedding_model_gpu_resident"]
                    else "cpu_batches"
                )
                self._metrics["throughput"][batch_counter] += 1
                self._metrics["throughput"]["chunks_embedded"] += len(batch)
                self._metrics["queue_depths"]["embedding"] -= len(batch)
                gpu = self._metrics.get("gpu") or {}
                memory_total = float(gpu.get("memory_total_mb") or 0)
                memory_ratio = (
                    float(gpu.get("memory_used_mb") or 0) / memory_total
                    if memory_total > 0
                    else None
                )
                active_limit = self._batch_controller.record_success(
                    batch_size=len(batch),
                    duration_seconds=inference_seconds,
                    vram_ratio=memory_ratio,
                )
                self._metrics["adaptive_batch"].update(
                    current=active_limit,
                    oom_count=self._batch_controller.oom_count,
                    last_chunks_per_second=round(len(batch) / inference_seconds, 2),
                )
                logger.info(
                    "gpu_batch_completed",
                    extra={
                        "event": "gpu_batch_completed",
                        "chunks": len(batch),
                        "assets": len({item.asset_id for item in batch}),
                        "tokens": sum(item.token_count for item in batch),
                        "device": self._metrics["embedding_device_actual"],
                        "next_batch_limit": active_limit,
                        "inference_ms": round(inference_seconds * 1000, 2),
                        "chunks_per_second": round(len(batch) / inference_seconds, 2),
                    },
                )
        except Exception as exc:
            for item in assets:
                self._handle_failure(item.job_id, exc)
            return
        finally:
            self._metrics["active_embedding_jobs"] = 0
            if self._metrics.get("gpu_state") == "embedding":
                self._metrics["gpu_state"] = "idle"

        for item in assets:
            self.queue.transition(item.job_id, self.worker_id, "writing")
            self._write_futures.add(
                self._writer_pool.submit(self._write_prepared_asset, item)
            )
        self._metrics["queue_depths"]["writing"] = len(self._write_futures)

    def _harvest_writes(self) -> None:
        completed = {future for future in self._write_futures if future.done()}
        for future in completed:
            self._write_futures.remove(future)
            try:
                future.result()
            except Exception:
                logger.exception(
                    "qdrant_writer_unhandled_failure",
                    extra={"event": "qdrant_writer_unhandled_failure"},
                )
        self._metrics["queue_depths"]["writing"] = len(self._write_futures)

    def _write_prepared_asset(self, item: PreparedAsset) -> None:
        try:
            write_started = time.monotonic()
            if item.asset_type == "document":
                with SessionLocal() as session:
                    current_job = session.get(IndexingJob, item.job_id)
                    current_operation = (
                        current_job.operation if current_job is not None else "upsert_version"
                    )
                if current_operation == "delete_asset":
                    self.engine.delete_document_asset(item.document_id)  # type: ignore[arg-type]
                    counts = {"chunks_indexed": 0}
                elif current_operation == "refresh_metadata":
                    self.engine.refresh_document_metadata(item.document_id)  # type: ignore[arg-type]
                    counts = {"chunks_indexed": len(item.chunks)}
                else:
                    if any(vector is None for vector in item.vectors):
                        raise RuntimeError("The embedding stage produced an incomplete vector set.")
                    matrix = np.stack(
                        [vector for vector in item.vectors if vector is not None]
                    ).astype(np.float32)
                    counts = self.engine.write_document_version(
                        item.document_id,  # type: ignore[arg-type]
                        item.version_id,  # type: ignore[arg-type]
                        item.chunks,
                        matrix,
                    )
            elif item.note is not None:
                note_vectors = (
                    np.stack(
                        [vector for vector in item.vectors if vector is not None]
                    ).astype(np.float32)
                    if item.vectors
                    else np.empty((0, 0), dtype=np.float32)
                )
                with SessionLocal() as session:
                    counts = NoteIndexingService(
                        session,
                        self.engine,
                    ).write_prepared(item.note, note_vectors)
            else:
                raise ValueError("Prepared indexing asset has no writable target.")
            self.queue.transition(item.job_id, self.worker_id, "verifying")
            self.queue.complete(
                item.job_id,
                self.worker_id,
                message=f"Indexed and verified {counts['chunks_indexed']} chunks.",
            )
            logger.info(
                "qdrant_batch_written",
                extra={
                    "event": "qdrant_batch_written",
                    "job_id": str(item.job_id),
                    "asset_type": item.asset_type,
                    "chunks": len(item.chunks),
                    "elapsed_ms": round((time.monotonic() - write_started) * 1000, 2),
                },
            )
            logger.info(
                "index_completed",
                extra={
                    "event": "index_completed",
                    "job_id": str(item.job_id),
                    "asset_type": item.asset_type,
                    "chunks": int(counts["chunks_indexed"]),
                },
            )
            self._metrics["throughput"]["jobs_completed"] += 1
            if item.asset_type == "document":
                self._metrics["throughput"]["documents_completed"] += 1
            self._remove_active(item.job_id)
            self._mark_bm25_dirty()
        except SupersededNoteRevision as exc:
            self.queue.supersede(item.job_id, self.worker_id, message=str(exc))
            self._remove_active(item.job_id)
        except Exception as exc:
            self._handle_failure(item.job_id, exc)

    def _embed_with_oom_reduction(self, batch: list[ChunkEnvelope]) -> np.ndarray:
        try:
            controller = getattr(self, "_batch_controller", None)
            active_limit = (
                controller.current
                if controller is not None
                else settings.indexer_embed_batch_size
            )
            return self.engine.embed_chunk_batch(
                [item.chunk for item in batch],
                batch_size=min(active_limit, len(batch)),
            )
        except RuntimeError as exc:
            if "out of memory" not in str(exc).casefold() or len(batch) <= 1:
                raise
            midpoint = len(batch) // 2
            controller = getattr(self, "_batch_controller", None)
            next_limit = (
                controller.record_oom(attempted_batch_size=len(batch))
                if controller is not None
                else midpoint
            )
            metrics = getattr(self, "_metrics", None)
            if metrics is not None and controller is not None:
                metrics["adaptive_batch"].update(
                    current=next_limit,
                    oom_count=controller.oom_count,
                )
            logger.warning(
                "cuda_oom_batch_reduced",
                extra={
                    "event": "embedding_batch_resize",
                    "from": len(batch),
                    "to": midpoint,
                    "next_batch_limit": next_limit,
                },
            )
            return np.concatenate(
                (
                    self._embed_with_oom_reduction(batch[:midpoint]),
                    self._embed_with_oom_reduction(batch[midpoint:]),
                ),
                axis=0,
            )

    def _yield_to_chat_if_needed(self) -> None:
        if not settings.indexer_gpu_cooperative_mode:
            return
        active = self._gpu_coordinator.chat_active()
        self._metrics["chat_priority_active"] = active
        if not active:
            return
        self._metrics["gpu_state"] = "yielding_to_chat"
        try:
            if self.engine.release_indexer_gpu():
                self._metrics["embedding_model_gpu_resident"] = False
                self._metrics["embedding_device_actual"] = "cpu"
                self._metrics["embedding_model_status"] = "yielding_to_chat"
        except Exception:
            logger.warning("indexer_gpu_priority_release_failed", exc_info=True)
        waited = self._gpu_coordinator.wait_for_chat(self.stop_event)
        self._metrics["chat_priority_wait_seconds"] = round(
            float(self._metrics.get("chat_priority_wait_seconds") or 0.0) + waited,
            3,
        )
        self._metrics["chat_priority_active"] = False
        self._metrics["gpu_state"] = "warming"

    def _release_idle_gpu_if_due(self) -> bool:
        if (
            not settings.indexer_release_gpu_when_idle
            or not self.actual_device.startswith("cuda")
            or time.monotonic() - self._last_embedding_activity
            < settings.indexer_gpu_idle_release_seconds
        ):
            return False
        try:
            released = self.engine.release_indexer_gpu()
        except Exception:
            logger.warning("indexer_idle_gpu_release_failed", exc_info=True)
            return False
        if released:
            self._metrics["gpu_state"] = "released_idle"
            self._metrics["embedding_model_gpu_resident"] = False
            self._metrics["embedding_device_actual"] = "cpu"
            self._metrics["embedding_model_status"] = "released_idle"
            logger.info(
                "indexer_embedding_gpu_released",
                extra={
                    "event": "gpu_resource_released",
                    "worker_id": self.worker_id,
                    "idle_seconds": round(
                        time.monotonic() - self._last_embedding_activity,
                        2,
                    ),
                },
            )
        return released

    def _process_non_document_upsert(self, target: ClaimedTarget) -> None:
        try:
            if target.operation == "rebuild_scope":
                kind = str(target.metadata.get("request_kind") or "rebuild")
                if kind in {"reconcile", "corpus_sync"}:
                    self.reconcile()
                else:
                    self._enqueue_rebuild_plan(target)
                self.queue.complete(target.job_id, self.worker_id, message=f"{kind} request expanded successfully.")
            elif target.asset_type == "document" and target.document_id:
                self.queue.transition(target.job_id, self.worker_id, "writing")
                if target.operation == "delete_asset":
                    self.engine.delete_document_asset(target.document_id)
                elif target.operation == "refresh_metadata":
                    self.engine.refresh_document_metadata(target.document_id)
                else:
                    raise ValueError(f"Unsupported document operation: {target.operation}")
                self.queue.transition(target.job_id, self.worker_id, "verifying")
                self.queue.complete(target.job_id, self.worker_id)
                self._mark_bm25_dirty()
            else:
                raise ValueError("The indexing job target is invalid.")
            self._metrics["throughput"]["jobs_completed"] += 1
            self._remove_active(target.job_id)
        except Exception as exc:
            self._handle_failure(target.job_id, exc)

    def _enqueue_rebuild_plan(self, target: ClaimedTarget) -> None:
        scope = dict(target.metadata.get("scope") or {})
        asset_type = str(scope.get("asset_type") or "all")
        with SessionLocal() as session, session.begin():
            document_query = select(Document).where(
                Document.deleted_at.is_(None),
                Document.current_version_id.is_not(None),
            )
            if scope.get("document_id"):
                document_query = document_query.where(
                    Document.id == uuid.UUID(str(scope["document_id"]))
                )
            if scope.get("workspace_id"):
                document_query = document_query.where(
                    Document.workspace_id == uuid.UUID(str(scope["workspace_id"]))
                )
            if scope.get("repository_id"):
                document_query = document_query.where(
                    Document.repository_id == str(scope["repository_id"])
                )
            documents = (
                list(session.scalars(document_query))
                if asset_type in {"all", "document"}
                else []
            )
            for document in documents:
                version_id = document.current_version_id
                existing = session.scalar(
                    select(IndexingJob).where(
                        IndexingJob.document_version_id == version_id,
                        IndexingJob.operation == "reprocess_version",
                        IndexingJob.status.in_(
                            ("pending", "claimed", "extracting", "chunked", "embedding", "writing", "verifying", "retry_wait")
                        ),
                    )
                )
                if existing is None:
                    session.add(
                        IndexingJob(
                            asset_type="document",
                            document_id=document.id,
                            document_version_id=version_id,
                            operation="reprocess_version",
                            status="pending",
                            priority=max(0, int(target.metadata.get("priority") or 0)),
                            max_attempts=settings.indexer_max_attempts,
                            force_rebuild=bool(target.metadata.get("force")),
                            content_hash=document.content_hash,
                            repository_id=document.repository_id,
                            metadata_={
                                "source": "rebuild_plan",
                                "action": "reprocess",
                                "relative_path": document.relative_path,
                            },
                        )
                    )
            note_query = select(Note).where(
                Note.deleted_at.is_(None),
                Note.is_archived.is_(False),
            )
            if scope.get("workspace_id"):
                note_query = note_query.where(
                    Note.workspace_id == uuid.UUID(str(scope["workspace_id"]))
                )
            repository_id = str(scope.get("repository_id") or "")
            if repository_id.startswith("personal:"):
                try:
                    owner_id = uuid.UUID(repository_id.removeprefix("personal:"))
                except ValueError:
                    notes = []
                else:
                    notes = list(
                        session.scalars(note_query.where(Note.owner_user_id == owner_id))
                    )
            elif scope.get("repository_id"):
                notes = []
            else:
                notes = (
                    list(session.scalars(note_query))
                    if asset_type in {"all", "note"}
                    else []
                )
            if asset_type not in {"all", "note"}:
                notes = []
            for note in notes:
                version = session.scalar(
                    select(NoteVersion).where(
                        NoteVersion.note_id == note.id,
                        NoteVersion.revision == note.revision,
                    )
                )
                if version is None:
                    continue
                existing = session.scalar(
                    select(IndexingJob).where(
                        IndexingJob.note_version_id == version.id,
                        IndexingJob.operation == "reprocess_version",
                        IndexingJob.status.in_(
                            ("pending", "claimed", "extracting", "chunked", "embedding", "writing", "verifying", "retry_wait")
                        ),
                    )
                )
                if existing is None:
                    session.add(
                        IndexingJob(
                            asset_type="note",
                            note_id=note.id,
                            note_version_id=version.id,
                            operation="reprocess_version",
                            status="pending",
                            priority=max(0, int(target.metadata.get("priority") or 0)),
                            max_attempts=settings.indexer_max_attempts,
                            repository_id=f"personal:{note.owner_user_id}",
                            metadata_={
                                "source": "rebuild_plan",
                                "entity_type": "note",
                                "note_id": str(note.id),
                                "note_revision": note.revision,
                                "action": "index",
                            },
                        )
                    )

    def publish_bm25_generation(self) -> None:
        started = time.monotonic()
        chunks: list[dict[str, Any]] = []
        with SessionLocal() as session:
            for row in session.scalars(select(DocumentChunk).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)):
                chunks.append({"text": row.text or "", "metadata": row.metadata_ or {}})
            notes = session.execute(
                select(Note, NoteIndexState)
                .join(NoteIndexState, NoteIndexState.note_id == Note.id)
                .where(
                    Note.deleted_at.is_(None),
                    Note.is_archived.is_(False),
                    NoteIndexState.status == "indexed",
                    NoteIndexState.indexed_revision == Note.revision,
                )
            ).all()
            for note, _state in notes:
                for index, (block_id, section, body) in enumerate(note_blocks(note)):
                    chunks.append(
                        {
                            "text": body,
                            "metadata": {
                                "entity_type": "note",
                                "note_id": str(note.id),
                                "note_revision": note.revision,
                                "workspace_id": str(note.workspace_id),
                                "organization_id": str(note.organization_id),
                                "repository_id": f"personal:{note.owner_user_id}",
                                "storage_scope": "personal",
                                "owner_user_id": str(note.owner_user_id),
                                "visibility": "private",
                                "lifecycle_status": "active",
                                "relative_path": note_relative_path(note.id),
                                "section": section,
                                "block_id": block_id,
                                "chunk_index": index,
                                "chunk_id": f"note:{note.id}:{note.revision}:{index}",
                            },
                        }
                    )
            generation = session.get(IndexGeneration, "active")
            next_generation = int(generation.bm25_generation or 0) + 1 if generation else 1
        snapshot_path = settings.bm25_path / "continuous" / "current.json"
        write_bm25_snapshot(snapshot_path, generation=next_generation, chunks=chunks)
        pipeline = self.engine._pipeline
        point_count = 0
        if pipeline is not None:
            point_count = int(
                pipeline.client.count(
                    collection_name=pipeline.config.qdrant_collection_name,
                    exact=True,
                ).count
            )
        generation = self.queue.publish_generation(
            self.worker_id,
            bm25_snapshot_path=str(snapshot_path.resolve()),
            point_count=point_count,
        )
        self._metrics["bm25"] = {
            "generation": generation,
            "chunks": len(chunks),
            "publish_ms": round((time.monotonic() - started) * 1000, 2),
        }
        logger.info(
            "bm25_generation_published",
            extra={
                "event": "bm25_generation",
                "generation": generation,
                "chunks": len(chunks),
                "point_count": point_count,
                "elapsed_ms": self._metrics["bm25"]["publish_ms"],
            },
        )

    def _mark_bm25_dirty(self) -> None:
        if self._bm25_dirty_since is None:
            self._bm25_dirty_since = time.monotonic()
        self._flush_bm25_if_due()

    def _flush_bm25_if_due(self, *, force: bool = False) -> bool:
        if self._bm25_dirty_since is None:
            return False
        elapsed = time.monotonic() - self._bm25_dirty_since
        if not force and elapsed < settings.bm25_refresh_debounce_seconds:
            return False
        self.publish_bm25_generation()
        self._bm25_dirty_since = None
        return True

    def _load_target(self, job_id: uuid.UUID) -> ClaimedTarget | None:
        with SessionLocal() as session:
            job = session.get(IndexingJob, job_id)
            if job is None:
                return None
            return ClaimedTarget(
                job_id=job.id,
                asset_type=job.asset_type,
                operation=job.operation,
                document_id=job.document_id,
                document_version_id=job.document_version_id,
                note_id=job.note_id,
                note_version_id=job.note_version_id,
                metadata=dict(job.metadata_ or {}),
            )

    def _start_watchers(self) -> None:
        if not settings.corpus_watch:
            return
        debounce = settings.corpus_watch_debounce_ms / 1000
        for root in (settings.corpus_root_path, settings.workspace_root_path):
            watcher = CorpusWatcher(
                root=root,
                sync_callback=self.reconcile,
                debounce_seconds=debounce,
                stability_attempts=settings.corpus_file_stability_checks,
                stability_interval=settings.corpus_file_stability_interval_ms / 1000,
            )
            watcher.start()
            self._watchers.append(watcher)

    def _start_heartbeat(self) -> None:
        def loop() -> None:
            while not self._heartbeat_stop.wait(settings.indexer_heartbeat_seconds):
                try:
                    with self._active_lock:
                        active = tuple(self._active_jobs)
                    for job_id in active:
                        if not self.queue.renew(job_id, self.worker_id):
                            raise RuntimeError(
                                f"Indexer lease was lost for job {job_id}."
                            )
                    self._sample_system_metrics()
                    self.queue.heartbeat(
                        self.worker_id,
                        service_state="active" if active else "watching",
                        current_job_id=active[0] if active else None,
                        metrics=self._metrics,
                        embedding_device=self.actual_device,
                        embedding_precision=self.actual_precision,
                    )
                    logger.debug(
                        "worker_heartbeat",
                        extra={
                            "event": "worker_heartbeat",
                            "worker_id": self.worker_id,
                            "active_jobs": len(active),
                        },
                    )
                except Exception:
                    logger.exception("indexer_heartbeat_or_lease_failed")
                    self._accepting = False
                    self.stop_event.set()
                    return

        self._heartbeat_thread = Thread(target=loop, name="cial-indexer-heartbeat", daemon=True)
        self._heartbeat_thread.start()

    def _sample_system_metrics(self) -> None:
        elapsed = max(time.monotonic() - self._started_monotonic, 0.000001)
        throughput = self._metrics["throughput"]
        throughput["documents_per_hour"] = round(
            float(throughput.get("documents_completed") or 0) * 3600 / elapsed,
            2,
        )
        throughput["chunks_per_minute"] = round(
            float(throughput.get("chunks_embedded") or 0) * 60 / elapsed,
            2,
        )
        throughput["uptime_seconds"] = round(elapsed, 2)
        try:
            import psutil

            self._metrics["cpu"] = {
                "utilization_percent": float(psutil.cpu_percent(interval=None)),
                "process_utilization_percent": float(
                    psutil.Process().cpu_percent(interval=None)
                ),
                "logical_cores": float(psutil.cpu_count(logical=True) or 0),
            }
        except (ImportError, OSError):
            logger.debug("cpu_metrics_unavailable", exc_info=True)

        if not self.actual_device.casefold().startswith("cuda"):
            return
        try:
            import torch

            device_index = (
                int(self.actual_device.rsplit(":", 1)[1])
                if ":" in self.actual_device
                else torch.cuda.current_device()
            )
            self._metrics["embedding_model_memory"] = {
                "allocated_mb": round(
                    torch.cuda.memory_allocated(device_index) / (1024 * 1024),
                    2,
                ),
                "reserved_mb": round(
                    torch.cuda.memory_reserved(device_index) / (1024 * 1024),
                    2,
                ),
                "gpu_resident": bool(
                    getattr(self.engine, "_indexer_embedding_gpu_resident", False)
                ),
            }
        except (ImportError, RuntimeError, ValueError):
            logger.debug("embedding_model_memory_unavailable", exc_info=True)
        executable = shutil.which("nvidia-smi")
        if not executable:
            return
        try:
            command = [
                executable,
                "--query-gpu=name,driver_version,utilization.gpu,memory.used,memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ]
            if ":" in self.actual_device:
                command.insert(1, f"--id={self.actual_device.rsplit(':', 1)[1]}")
            result = subprocess.run(
                command,
                capture_output=True,
                check=True,
                text=True,
                timeout=2,
            )
            values = [value.strip() for value in result.stdout.splitlines()[0].split(",")]
            if len(values) == 6:
                self._metrics["gpu"] = {
                    "device_name": values[0],
                    "driver_version": values[1],
                    "utilization_percent": float(values[2]),
                    "memory_used_mb": float(values[3]),
                    "memory_free_mb": float(values[4]),
                    "memory_total_mb": float(values[5]),
                }
        except (OSError, ValueError, subprocess.SubprocessError, IndexError):
            logger.debug("gpu_metrics_unavailable", exc_info=True)

    def _handle_failure(self, job_id: uuid.UUID, exc: Exception) -> None:
        message = str(exc).casefold()
        if "no longer current" in message or "superseded" in message:
            self.queue.supersede(
                job_id,
                self.worker_id,
                message="Superseded by a newer committed asset version.",
            )
            self._remove_active(job_id)
            logger.info(
                "indexing_job_superseded",
                extra={
                    "event": "indexing_job_superseded",
                    "job_id": str(job_id),
                },
            )
            return
        transient = any(
            marker in message
            for marker in ("timeout", "temporar", "connection", "locked", "out of memory", "unavailable")
        )
        code = (
            "cuda_oom" if "out of memory" in message
            else "temporary_dependency_failure" if transient
            else "permanent_index_failure"
        )
        status = self.queue.fail(
            job_id,
            self.worker_id,
            error_code=code,
            safe_detail=type(exc).__name__,
            transient=transient,
        )
        self._remove_active(job_id)
        logger.exception(
            "index_failed",
            extra={"event": "index_failed", "job_id": str(job_id), "error_code": code, "status": status},
        )

    def _remove_active(self, job_id: uuid.UUID) -> None:
        with self._active_lock:
            self._active_jobs.discard(job_id)

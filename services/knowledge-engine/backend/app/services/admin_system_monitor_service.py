"""Admin-only operational telemetry assembled from live runtime sources."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any
import os
import uuid

from backend.app.core.config import settings
from backend.app.lan.status import disabled_status


_ACTIVE_JOB_STATES = {
    "claimed",
    "extracting",
    "chunked",
    "embedding",
    "writing",
    "verifying",
}
_PIPELINE_EVENTS_BY_STATE = {
    "pending": ("document_detected",),
    "claimed": ("extraction_started",),
    "extracting": ("extraction_started",),
    "chunked": ("extraction_completed", "chunking_completed"),
    "embedding": ("embedding_started",),
    "writing": ("embedding_batch_completed",),
    "verifying": ("qdrant_write_completed",),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _age_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return max(0.0, (_utc_now() - parsed).total_seconds())
    except (TypeError, ValueError):
        return None


class AdminSystemMonitorService:
    """Project existing health, queue, model, and query telemetry for operators."""

    def __init__(
        self,
        *,
        system_status_service: Any,
        runtime_state: Any,
        engine: Any,
        indexing_service: Any,
        chat_concurrency: Any | None = None,
    ) -> None:
        self.system_status_service = system_status_service
        self.runtime_state = runtime_state
        self.engine = engine
        self.indexing_service = indexing_service
        self.chat_concurrency = chat_concurrency
        self._started_at = monotonic()
        self._lock = RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=250)
        self._last_job_states: dict[str, str] = {}
        self._last_generation = 0
        self._last_worker_state = "unknown"
        self._active_chat_requests = 0
        self._active_chat_stages: dict[str, dict[str, Any]] = {}
        self._last_failed_stage: str | None = None
        self._last_timeout_reason: str | None = None

    def record_event(
        self,
        event_type: str,
        *,
        severity: str = "info",
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "severity": severity,
            "message": message,
            "timestamp": _iso_now(),
            "metadata": dict(metadata or {}),
        }
        with self._lock:
            self._events.append(event)
        return event

    def chat_started(self, request_id: str) -> None:
        with self._lock:
            self._active_chat_requests += 1
            self._active_chat_stages[request_id] = {
                "stage": "connected",
                "status": "started",
                "started_monotonic": monotonic(),
                "failed_stage": None,
                "timeout_reason": None,
            }
        self.record_event(
            "chat_started",
            message="An authenticated AI request entered the query pipeline.",
            metadata={"request_id": request_id},
        )

    def chat_stage(
        self,
        request_id: str,
        stage: str,
        status: str,
        metrics: dict[str, Any],
    ) -> None:
        error_state = metrics.get("error_state")
        timeout_reason = (
            str(error_state)
            if metrics.get("timeout_state") == "timed_out"
            else None
        )
        with self._lock:
            current = self._active_chat_stages.setdefault(
                request_id,
                {"started_monotonic": monotonic()},
            )
            current.update(stage=stage, status=status)
            if status == "started":
                current["started_monotonic"] = monotonic()
            if error_state:
                # A terminal chat-level failure follows the component event.
                # Preserve the component that actually failed so operators see
                # "dense_retrieval", "bm25_retrieval", etc., not merely "chat".
                if stage != "chat" or not current.get("failed_stage"):
                    current["failed_stage"] = stage
                    current["timeout_reason"] = timeout_reason
                    self._last_failed_stage = stage
                    self._last_timeout_reason = timeout_reason
        if error_state:
            self.record_event(
                "retrieval_stage_failed",
                severity="warning",
                message=f"Query stage {stage} degraded.",
                metadata={
                    "request_id": request_id,
                    "stage": stage,
                    "error_state": str(error_state),
                    "timeout_state": metrics.get("timeout_state"),
                    "duration_ms": metrics.get("duration_ms"),
                    "candidate_count": metrics.get("candidate_count"),
                },
            )

    def chat_completed(
        self,
        request_id: str,
        *,
        succeeded: bool,
        latency_ms: int,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            self._active_chat_requests = max(0, self._active_chat_requests - 1)
            completed_stage = self._active_chat_stages.pop(request_id, {})
            if completed_stage.get("failed_stage"):
                self._last_failed_stage = str(
                    completed_stage["failed_stage"]
                )
                self._last_timeout_reason = completed_stage.get(
                    "timeout_reason"
                )
        self.record_event(
            "chat_completed" if succeeded else "retrieval_failed",
            severity="info" if succeeded else "error",
            message=(
                "The AI request completed."
                if succeeded
                else "The AI request failed in the query pipeline."
            ),
            metadata={
                "request_id": request_id,
                "latency_ms": latency_ms,
                **({"error_type": error_type} if error_type else {}),
            },
        )

    def _sample_backend_cpu(self) -> dict[str, Any]:
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return {
                "utilization_percent": float(psutil.cpu_percent(interval=None)),
                "process_utilization_percent": float(
                    process.cpu_percent(interval=None)
                ),
                "logical_cores": int(psutil.cpu_count(logical=True) or 0),
            }
        except (ImportError, OSError):
            return {}

    def _derive_events(self, queue: dict[str, Any]) -> None:
        worker_state = str(queue.get("indexer_state") or "unknown")
        generation = int(queue.get("latest_index_generation") or 0)
        active_jobs = list(queue.get("active_jobs") or [])
        current_states = {
            str(job.get("job_id")): str(job.get("status") or "unknown")
            for job in active_jobs
            if job.get("job_id")
        }
        with self._lock:
            previous_states = self._last_job_states
            previous_worker = self._last_worker_state
            previous_generation = self._last_generation
            self._last_job_states = current_states
            self._last_worker_state = worker_state
            self._last_generation = generation

        if worker_state != previous_worker:
            self.record_event(
                "worker_failed"
                if worker_state in {"degraded", "stopped", "unknown"}
                else "worker_started",
                severity=(
                    "error"
                    if worker_state in {"degraded", "stopped"}
                    else "warning"
                    if worker_state == "unknown"
                    else "info"
                ),
                message=f"Indexer worker state changed to {worker_state}.",
                metadata={"worker_state": worker_state},
            )
        if generation > previous_generation and previous_generation:
            self.record_event(
                "generation_published",
                message=f"Index generation {generation} became active.",
                metadata={"generation": generation},
            )
        for job in active_jobs:
            job_id = str(job.get("job_id") or "")
            state = str(job.get("status") or "unknown")
            if not job_id or previous_states.get(job_id) == state:
                continue
            event_types = _PIPELINE_EVENTS_BY_STATE.get(state, ())
            for event_type in event_types:
                self.record_event(
                    event_type,
                    message=f"Indexing job entered {state}.",
                    metadata={
                        "job_id": job_id,
                        "asset_type": job.get("asset_type"),
                        "operation": job.get("operation"),
                        "status": state,
                    },
                )

    def snapshot(self) -> dict[str, Any]:
        status = self.system_status_service.snapshot()
        try:
            queue = self.indexing_service.queue.status()
        except Exception as exc:  # noqa: BLE001 - monitor must show partial failure.
            queue = {
                "queue_counts": {},
                "queue_by_operation": {},
                "active_jobs": [],
                "recent_errors": [],
            }
            self.record_event(
                "service_failed",
                severity="error",
                message="Index queue telemetry is unavailable.",
                metadata={"component": "index_queue", "error_type": type(exc).__name__},
            )
        self._derive_events(queue)
        diagnostics = self.engine.runtime_diagnostics()
        query = self.engine.chat_debug_snapshot()
        chat_concurrency = (
            self.chat_concurrency.snapshot()
            if self.chat_concurrency is not None
            else {}
        )
        reader_snapshot = getattr(self.engine, "publication_reader_snapshot", None)
        publication_readers = (
            reader_snapshot()
            if callable(reader_snapshot)
            else {
                "active_query_runtime_reader_count": 0,
                "pending_publication_activation": False,
            }
        )
        worker_heartbeat = queue.get("worker_heartbeat_at")
        worker_age = _age_seconds(worker_heartbeat)
        worker_stale = (
            worker_age is None
            or worker_age > settings.indexer_heartbeat_stale_seconds
        )
        counts = dict(queue.get("queue_counts") or {})
        throughput = dict(queue.get("throughput") or {})
        gpu_metrics = dict(queue.get("gpu_metrics") or {})
        cpu_metrics = dict(queue.get("cpu_metrics") or {})
        internal_depths = dict(queue.get("internal_queue_depths") or {})
        active_jobs = list(queue.get("active_jobs") or [])
        active_tasks = sum(
            1 for job in active_jobs if str(job.get("status")) in _ACTIVE_JOB_STATES
        )
        with self._lock:
            events = list(reversed(self._events))
            active_chat_requests = self._active_chat_requests
            active_query = next(
                reversed(self._active_chat_stages.values()),
                None,
            )
            last_failed_stage = self._last_failed_stage
            last_timeout_reason = self._last_timeout_reason

        return {
            "status": status["status"],
            "label": status["label"],
            "generated_at": status["timestamps"]["generated_at"],
            "uptime_seconds": round(monotonic() - self._started_at, 2),
            "stale": worker_stale,
            "connection_hint_seconds": 2,
            "lan_access": status.get("lan_access", disabled_status()),
            "infrastructure": {
                "backend": status["components"]["backend"],
                "postgresql": status["components"]["postgresql"],
                "qdrant": status["components"]["qdrant"],
                "service_latency_ms": status["latency_ms"]["total"],
                "uptime_seconds": round(monotonic() - self._started_at, 2),
            },
            "indexing": {
                "worker_status": queue.get("indexer_state", "unknown"),
                "worker_heartbeat_at": worker_heartbeat,
                "worker_heartbeat_age_seconds": worker_age,
                "worker_stale": worker_stale,
                "active_workers": int(queue.get("active_workers") or 0),
                "queue_depth": int(queue.get("queue_depth") or 0),
                "priority_queues": dict(queue.get("queue_by_operation") or {}),
                "pending_jobs": int(counts.get("pending", 0)),
                "active_jobs_count": active_tasks,
                "completed_jobs": int(counts.get("completed", 0)),
                "failed_jobs": int(counts.get("failed", 0)),
                "active_jobs": active_jobs,
                "recent_errors": list(queue.get("recent_errors") or []),
                "active_published_generation": int(
                    queue.get("latest_index_generation") or 0
                ),
                "bm25_generation": int(queue.get("bm25_generation") or 0),
                "state": (
                    "updating"
                    if int(queue.get("queue_depth") or 0) > 0
                    else "ready"
                    if queue.get("index_fresh")
                    else "degraded"
                ),
                "last_successful_publish": queue.get("generation_published_at"),
                "throughput": throughput,
                "internal_queue_depths": internal_depths,
            },
            "gpu": {
                "embedding_device_configured": (
                    (queue.get("worker_metrics") or {}).get(
                        "embedding_device_configured"
                    )
                    or settings.indexer_device
                ),
                "embedding_device_actual": (
                    (queue.get("worker_metrics") or {}).get(
                        "embedding_device_actual"
                    )
                    or queue.get("embedding_device")
                ),
                "embedding_model_status": (
                    (queue.get("worker_metrics") or {}).get(
                        "embedding_model_status"
                    )
                ),
                "embedding_batch": (
                    (queue.get("worker_metrics") or {}).get("embedding_batch")
                    or {}
                ),
                "cuda_available": bool(
                    queue.get("indexer_seen")
                    and str(queue.get("embedding_device") or "").startswith("cuda")
                ),
                "device": queue.get("embedding_device") or settings.indexer_device,
                "utilization_percent": gpu_metrics.get("utilization_percent"),
                "memory_used_mb": gpu_metrics.get("memory_used_mb"),
                "memory_total_mb": gpu_metrics.get("memory_total_mb"),
                "embedding_device": (
                    (queue.get("worker_metrics") or {}).get(
                        "embedding_device_actual"
                    )
                    or queue.get("embedding_device")
                    or settings.indexer_device
                ),
                "precision": queue.get("embedding_precision")
                or settings.indexer_precision,
                "batch_size": int(
                    queue.get("active_batch_limit")
                    or settings.indexer_embed_batch_size
                ),
                "embedding_throughput_chunks_per_minute": throughput.get(
                    "chunks_per_minute"
                ),
                "state": (queue.get("worker_metrics") or {}).get("gpu_state")
                or queue.get("gpu_state"),
                "embedding_model_gpu_resident": (
                    (queue.get("worker_metrics") or {}).get(
                        "embedding_model_gpu_resident"
                    )
                ),
                "active_embedding_jobs": (
                    (queue.get("worker_metrics") or {}).get(
                        "active_embedding_jobs"
                    )
                ),
                "embedding_model_memory": (
                    (queue.get("worker_metrics") or {}).get(
                        "embedding_model_memory"
                    )
                    or {}
                ),
                "chat_priority_active": (
                    (queue.get("worker_metrics") or {}).get(
                        "chat_priority_active"
                    )
                ),
                "generation_start": query.get("generation_gpu_start") or {},
                "generation_end": query.get("generation_gpu_end") or {},
            },
            "cpu": {
                **self._sample_backend_cpu(),
                "indexer": cpu_metrics,
                "extraction_workers": settings.indexer_extraction_workers,
                "active_worker_count": int(queue.get("active_workers") or 0),
                "current_tasks": active_tasks,
                "ocr_workers": settings.indexer_ocr_workers,
            },
            "models": {
                "ollama_available": status["components"]["ollama"]["available"],
                "loaded_models": status["components"]["ollama"].get(
                    "loaded_models", []
                ),
                "embedding_model": settings.embedding_model_name,
                "embedding_model_ready": bool(
                    diagnostics.get("embedding_ready")
                ),
                "dense_model_status": diagnostics.get(
                    "dense_model_status",
                    "unavailable",
                ),
                "query_embedding_device": diagnostics.get(
                    "query_embedding_device"
                )
                or diagnostics.get("embedding_device")
                or settings.query_embedding_device,
                "query_embedding_dtype": diagnostics.get(
                    "query_embedding_dtype"
                ),
                "query_embedding_model_state": diagnostics.get(
                    "query_embedding_model_state"
                ),
                "query_embedding_cache_status": diagnostics.get(
                    "query_embedding_cache_status"
                ),
                "reranker_model": settings.reranker_model_name,
                "reranker_ready": bool(diagnostics.get("reranker_ready")),
                "reranker_status": diagnostics.get(
                    "reranker_status",
                    "unavailable",
                ),
                "bm25_status": diagnostics.get(
                    "bm25_status",
                    "unavailable",
                ),
                "reranker_device": diagnostics.get("reranker_device"),
                "reranker_dtype": diagnostics.get("reranker_dtype"),
                "reranker_model_loaded": diagnostics.get(
                    "reranker_model_loaded"
                ),
                "reranker_warmed": diagnostics.get("reranker_warmed"),
                "reranker_warm_duration_ms": diagnostics.get(
                    "reranker_warm_duration_ms"
                ),
                "dense_model_warmed": diagnostics.get(
                    "dense_model_warmed"
                ),
                "dense_model_warm_duration_ms": diagnostics.get(
                    "dense_model_warm_duration_ms"
                ),
                "reranker_gpu_memory": diagnostics.get(
                    "reranker_gpu_memory"
                )
                or {},
            },
            "query": {
                "active_chat_requests": active_chat_requests,
                "active_chat_request_count": chat_concurrency.get(
                    "active_chat_request_count", active_chat_requests
                ),
                "queued_chat_request_count": chat_concurrency.get(
                    "queued_chat_request_count", 0
                ),
                "counts_by_stage": chat_concurrency.get("counts_by_stage", {}),
                "resource_gates": chat_concurrency.get("gates", {}),
                "queue_wait_ms_p50": chat_concurrency.get("queue_wait_ms_p50"),
                "queue_wait_ms_p95": chat_concurrency.get("queue_wait_ms_p95"),
                "capacity_rejections": {
                    "global": chat_concurrency.get(
                        "global_limit_rejection_count", 0
                    ),
                    "per_user": chat_concurrency.get(
                        "per_user_limit_rejection_count", 0
                    ),
                },
                **publication_readers,
                "status": query.get("status", "idle"),
                "current_stage": (
                    active_query.get("stage")
                    if active_query
                    else query.get("current_stage")
                ),
                "current_stage_duration_ms": (
                    int(
                        (
                            monotonic()
                            - float(active_query["started_monotonic"])
                        )
                        * 1000
                    )
                    if active_query
                    and active_query.get("started_monotonic") is not None
                    else query.get("current_stage_duration_ms")
                ),
                "failed_stage": (
                    active_query.get("failed_stage")
                    if active_query
                    else query.get("failed_stage") or last_failed_stage
                ),
                "timeout_reason": (
                    active_query.get("timeout_reason")
                    if active_query
                    else query.get("timeout_reason")
                    or last_timeout_reason
                ),
                "validation_latency_ms": query.get("validation_latency"),
                "retrieval_latency_ms": query.get("retrieval_latency"),
                "parallel_retrieval_duration_ms": query.get(
                    "parallel_retrieval_duration_ms"
                ),
                "dense_started": query.get("dense_started"),
                "dense_completed": query.get("dense_completed"),
                "bm25_started": query.get("bm25_started"),
                "bm25_completed": query.get("bm25_completed"),
                "query_embedding_metrics": query.get(
                    "query_embedding_metrics"
                )
                or {},
                "qdrant_metrics": query.get("qdrant_metrics") or {},
                "qdrant_index_status": query.get(
                    "qdrant_index_status",
                    diagnostics.get("qdrant_index_status"),
                ),
                "qdrant_payload_index_fields": query.get(
                    "qdrant_payload_index_fields",
                    diagnostics.get("qdrant_payload_index_fields", []),
                ),
                "retrieval_cache_metrics": query.get(
                    "retrieval_cache_metrics"
                )
                or {},
                "retrieval_cache_size": query.get(
                    "retrieval_cache_size",
                    diagnostics.get("retrieval_cache_size", 0),
                ),
                "retrieval_cache_invalidation_reason": query.get(
                    "retrieval_cache_invalidation_reason",
                    diagnostics.get(
                        "retrieval_cache_invalidation_reason"
                    ),
                ),
                "bm25_search_duration_ms": query.get(
                    "bm25_search_duration_ms"
                ),
                "bm25_candidate_count": query.get("bm25_candidate_count"),
                "bm25_snapshot_loaded_at": query.get(
                    "bm25_snapshot_loaded_at"
                ),
                "bm25_snapshot_size": query.get("bm25_snapshot_size"),
                "bm25_snapshot_load_duration_ms": query.get(
                    "bm25_snapshot_load_duration_ms"
                ),
                "bm25_index_activation_duration_ms": query.get(
                    "bm25_index_activation_duration_ms"
                ),
                "bm25_document_count": query.get("bm25_document_count"),
                "bm25_chunk_count": query.get("bm25_chunk_count"),
                "bm25_runtime_state": query.get("bm25_runtime_state"),
                "bm25_snapshot_version": query.get(
                    "bm25_snapshot_version"
                ),
                "bm25_loaded_at": query.get("bm25_loaded_at"),
                "bm25_load_duration_ms": query.get(
                    "bm25_load_duration_ms"
                ),
                "reranker_latency_ms": query.get("reranker_latency"),
                "reranker_metrics": query.get("reranker_metrics") or {},
                "generation_latency_ms": query.get("generation_latency"),
                "generation_metrics": query.get("generation_metrics") or {},
                "total_latency_ms": query.get("total_latency"),
                "last_error": query.get("last_error"),
            },
            "events": events[:100],
        }

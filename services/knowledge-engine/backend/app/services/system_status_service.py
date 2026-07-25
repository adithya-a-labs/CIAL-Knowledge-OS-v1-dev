"""Authenticated, real-time health snapshot for the AI Assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from time import monotonic
from typing import Any, Callable

import httpx

from backend.app.core.config import settings
from backend.app.db.health import check_database_health

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latency_ms(started_at: float) -> int:
    return max(0, round((monotonic() - started_at) * 1000))


class SystemStatusService:
    """Build one bounded status response from live component telemetry."""

    def __init__(self, *, runtime_state: Any, engine: Any, indexing_service: Any) -> None:
        self.runtime_state = runtime_state
        self.engine = engine
        self.indexing_service = indexing_service

    @staticmethod
    def _component(
        *,
        available: bool | None,
        detail: str,
        checked_at: str,
        latency_ms: int,
        degraded: bool = False,
    ) -> dict[str, Any]:
        status = "unknown" if available is None else "degraded" if degraded else "available" if available else "unavailable"
        return {
            "status": status,
            "available": available,
            "detail": detail,
            "checked_at": checked_at,
            "latency_ms": latency_ms,
        }

    def _probe_database(self, checked_at: str) -> dict[str, Any]:
        started = monotonic()
        health = check_database_health()
        return self._component(
            available=health.database_ready,
            detail=(
                health.database_message
                if health.database_ready
                else "PostgreSQL is not configured."
                if not health.database_configured
                else "PostgreSQL metadata health check failed."
            ),
            checked_at=checked_at,
            latency_ms=_latency_ms(started),
        )

    def _probe_qdrant(self, checked_at: str) -> dict[str, Any]:
        started = monotonic()
        if settings.qdrant_mode.casefold() != "server":
            ready = bool(self.runtime_state.snapshot().get("qdrant_ready"))
            return self._component(
                available=ready,
                detail="Embedded Qdrant is available through the active query runtime." if ready else "Embedded Qdrant is not ready.",
                checked_at=checked_at,
                latency_ms=_latency_ms(started),
            )
        headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}
        url = f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection_name}"
        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=min(3.0, settings.qdrant_health_timeout_seconds),
            )
            response.raise_for_status()
            result = response.json().get("result") or {}
            points = result.get("points_count")
            return self._component(
                available=True,
                detail=f"Collection {settings.qdrant_collection_name} is available"
                + (f" with {points} points." if points is not None else "."),
                checked_at=checked_at,
                latency_ms=_latency_ms(started),
            )
        except Exception as exc:  # noqa: BLE001 - status must degrade, not fail.
            logger.warning(
                "system_status_component_unavailable",
                extra={"event": "system_status", "component": "qdrant", "error_type": type(exc).__name__},
            )
            return self._component(
                available=False,
                detail=f"Qdrant collection check failed ({type(exc).__name__}).",
                checked_at=checked_at,
                latency_ms=_latency_ms(started),
            )

    def _probe_ollama(self, checked_at: str) -> dict[str, Any]:
        started = monotonic()
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"
        try:
            response = httpx.get(f"{host.rstrip('/')}/api/tags", timeout=3.0)
            response.raise_for_status()
            models = {
                str(model.get("name") or model.get("model") or "")
                for model in (response.json().get("models") or [])
            }
            configured = settings.ollama_model_name
            installed = configured in models
            return self._component(
                available=installed,
                detail=(
                    f"Ollama model {configured} is available."
                    if installed
                    else f"Ollama is reachable, but model {configured} is not installed."
                ),
                checked_at=checked_at,
                latency_ms=_latency_ms(started),
                degraded=not installed,
            ) | {"loaded_models": sorted(model for model in models if model)}
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "system_status_component_unavailable",
                extra={"event": "system_status", "component": "ollama", "error_type": type(exc).__name__},
            )
            return self._component(
                available=False,
                detail=f"Ollama check failed ({type(exc).__name__}).",
                checked_at=checked_at,
                latency_ms=_latency_ms(started),
            )

    def snapshot(self) -> dict[str, Any]:
        total_started = monotonic()
        checked_at = _utc_now()
        runtime = self.runtime_state.snapshot()

        database = self._probe_database(checked_at)
        try:
            queue_started = monotonic()
            queue = self.indexing_service.queue.status()
            queue_component = self._component(
                available=True,
                detail="Durable indexing queue telemetry is available.",
                checked_at=checked_at,
                latency_ms=_latency_ms(queue_started),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "system_status_component_unavailable",
                extra={"event": "system_status", "component": "index_queue", "error_type": type(exc).__name__},
            )
            queue = {
                "queue_counts": {},
                "queue_depth": 0,
                "active_jobs": [],
                "indexer_seen": False,
                "indexer_state": "unknown",
                "latest_index_generation": int(runtime.get("latest_index_generation") or 0),
                "bm25_generation": int(runtime.get("bm25_generation") or 0),
            }
            queue_component = self._component(
                available=False,
                detail=f"Indexing queue telemetry failed ({type(exc).__name__}).",
                checked_at=checked_at,
                latency_ms=_latency_ms(queue_started),
            )

        if (
            not bool(runtime.get("retrieval_ready"))
            and int(queue.get("latest_index_generation") or 0) > 0
        ):
            refresh = getattr(self.engine, "request_generation_refresh", None)
            if callable(refresh):
                refresh()

        diagnostics: dict[str, Any] = {}
        diagnostics_method: Callable[[], dict[str, Any]] | None = getattr(self.engine, "runtime_diagnostics", None)
        if callable(diagnostics_method):
            diagnostics = diagnostics_method()

        # Independent network probes run together; each has its own hard timeout.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="system-status") as executor:
            qdrant_future = executor.submit(self._probe_qdrant, checked_at)
            ollama_future = executor.submit(self._probe_ollama, checked_at)
            qdrant = qdrant_future.result()
            ollama = ollama_future.result()
        generation = int(queue.get("latest_index_generation") or runtime.get("latest_index_generation") or 0)
        published_at = queue.get("generation_published_at")
        engine_ready = bool(runtime.get("engine_ready")) and bool(self.engine.is_ready())
        embedding_ready = bool(diagnostics.get("embedding_ready", runtime.get("models_ready")))
        generation_ready = generation > 0 and bool(published_at)
        queue_depth = int(queue.get("queue_depth") or 0)
        active_jobs = list(queue.get("active_jobs") or [])
        indexing_active = queue_depth > 0 or bool(active_jobs)
        worker_seen = bool(queue.get("indexer_seen"))
        worker_state = str(queue.get("indexer_state") or "unknown")

        components = {
            "backend": self._component(
                available=True,
                detail="API process is responding.",
                checked_at=checked_at,
                latency_ms=0,
            ),
            "postgresql": database,
            "qdrant": qdrant,
            "published_generation": self._component(
                available=generation_ready,
                detail=(
                    f"Published generation {generation} is active."
                    if generation_ready
                    else "No valid published index generation is available."
                ),
                checked_at=checked_at,
                latency_ms=0,
            ),
            "worker": self._component(
                available=worker_seen,
                detail=f"Indexer worker state is {worker_state}.",
                checked_at=checked_at,
                latency_ms=0,
                degraded=worker_seen and worker_state in {"degraded", "stopped", "unknown"},
            ),
            "queue": queue_component,
            "ollama": ollama,
            "embedding_model": self._component(
                available=embedding_ready,
                detail=(
                    f"Embedding model {settings.embedding_model_name} is loaded."
                    if embedding_ready
                    else f"Embedding model {settings.embedding_model_name} is not ready."
                ),
                checked_at=checked_at,
                latency_ms=0,
            ),
        }

        chat_available = all(
            (
                bool(database["available"]),
                bool(qdrant["available"]),
                generation_ready,
                engine_ready,
                bool(ollama["available"]),
                embedding_ready,
            )
        )
        gpu_metrics = dict(queue.get("gpu_metrics") or {})
        configured_device = str(queue.get("embedding_device") or settings.indexer_device)
        gpu_requested = configured_device.startswith("cuda")
        gpu_available = (
            True
            if gpu_metrics
            else False
            if configured_device.startswith(("cuda", "cpu"))
            else None
        )
        components["gpu"] = self._component(
            available=gpu_available,
            detail=(
                f"GPU telemetry is available for {configured_device}."
                if gpu_available
                else "GPU telemetry is unavailable; CPU operation may still be usable."
            ),
            checked_at=checked_at,
            latency_ms=0,
            degraded=gpu_requested and not bool(gpu_available),
        )

        noncritical_degraded = (
            not worker_seen
            or not bool(queue_component["available"])
            or (gpu_requested and not bool(gpu_available))
        )
        if not chat_available:
            status = "red"
            label = "Unavailable"
        elif indexing_active and worker_seen and worker_state not in {"degraded", "stopped", "unknown"}:
            status = "blue"
            label = "Updating knowledge"
        elif noncritical_degraded:
            status = "yellow"
            label = "Degraded"
        else:
            status = "green"
            label = "System ready"

        payload = {
            "status": status,
            "label": label,
            "chat_available": chat_available,
            "indexing_active": indexing_active,
            "components": components,
            "index": {
                "generation": generation,
                "bm25_generation": int(queue.get("bm25_generation") or 0),
                "published_at": published_at,
                "point_count": int(queue.get("qdrant_point_count") or 0),
            },
            "indexing": {
                "worker_state": worker_state,
                "worker_seen": worker_seen,
                "worker_heartbeat_at": queue.get("worker_heartbeat_at"),
                "queue_depth": queue_depth,
                "queue_counts": dict(queue.get("queue_counts") or {}),
                "active_jobs": active_jobs,
                "last_successful_index_at": queue.get("last_successful_index_at"),
            },
            "models": {
                "ollama": settings.ollama_model_name,
                "embedding": settings.embedding_model_name,
                "embedding_device": diagnostics.get("embedding_device") or configured_device,
                "embedding_ready": embedding_ready,
            },
            "gpu": {
                "available": gpu_available,
                "requested": gpu_requested,
                "device": configured_device,
                "utilization_percent": gpu_metrics.get("utilization_percent"),
                "memory_used_mb": gpu_metrics.get("memory_used_mb"),
                "memory_total_mb": gpu_metrics.get("memory_total_mb"),
            },
            "timestamps": {
                "generated_at": checked_at,
                "worker_heartbeat_at": queue.get("worker_heartbeat_at"),
                "generation_published_at": published_at,
                "last_successful_index_at": queue.get("last_successful_index_at"),
            },
            "latency_ms": {
                **{name: component["latency_ms"] for name, component in components.items()},
                "total": _latency_ms(total_started),
            },
        }
        logger.info(
            "health_check_completed",
            extra={
                "event": "health_check_completed",
                "telemetry_type": "system_status_snapshot",
                "status": status,
                "chat_available": chat_available,
                "indexing_active": indexing_active,
                "generation": generation,
                "queue_depth": queue_depth,
                "latency_ms": payload["latency_ms"]["total"],
            },
        )
        return payload

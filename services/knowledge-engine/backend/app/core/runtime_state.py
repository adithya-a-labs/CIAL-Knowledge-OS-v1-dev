"""Shared backend runtime readiness state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Literal
import logging


RuntimeStatus = Literal["starting", "ready", "indexing", "degraded", "failed", "no_documents"]
logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RuntimeState:
    status: RuntimeStatus = "starting"
    api_ready: bool = False
    retrieval_ready: bool = False
    engine_available: bool = False
    engine_ready: bool = False
    stage: str = "starting"
    documents_seen: int = 0
    documents_indexed: int = 0
    index_fresh: bool = False
    indexer_seen: bool = False
    indexer_state: str = "unknown"
    qdrant_ready: bool = False
    models_ready: bool = False
    database_ready: bool = False
    latest_index_generation: int = 0
    bm25_generation: int = 0
    last_startup_check_at: str | None = None
    last_index_run_at: str | None = None
    message: str = "Backend startup checks have not completed."

    def __post_init__(self) -> None:
        self._lock = RLock()

    def update(self, **values: object) -> None:
        with self._lock:
            previous_status = self.status
            previous_ready = self.engine_ready
            for key, value in values.items():
                if not hasattr(self, key):
                    raise AttributeError(f"Unknown runtime state field: {key}")
                setattr(self, key, value)
            if previous_status != self.status or previous_ready != self.engine_ready:
                logger.info(
                    "knowledge_engine_state_changed",
                    extra={
                        "event": "knowledge_engine_state",
                        "previous_status": previous_status,
                        "new_status": self.status,
                        "previous_ready": previous_ready,
                        "new_ready": self.engine_ready,
                        "stage": self.stage,
                        "reason": values.get("message"),
                        "updated_at": utc_now_iso(),
                    },
                )

    def set_ready(self, *, message: str, documents_seen: int, documents_indexed: int) -> None:
        """Authoritatively mark the shared, already-initialized engine ready."""

        self.update(
            status="ready",
            stage="ready",
            engine_ready=True,
            api_ready=True,
            retrieval_ready=True,
            qdrant_ready=True,
            models_ready=True,
            index_fresh=True,
            documents_seen=documents_seen,
            documents_indexed=documents_indexed,
            last_index_run_at=utc_now_iso(),
            message=message,
        )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            payload = asdict(self)
        payload.pop("_lock", None)
        return payload

    def chat_unavailable_detail(self) -> dict[str, object]:
        state = self.snapshot()
        status = str(state["status"])
        if not state["retrieval_ready"]:
            reason = "retrieval_index_unavailable"
        elif not state["engine_available"]:
            reason = "startup_failed"
        elif status == "failed" and not state["qdrant_ready"] and state["documents_seen"]:
            reason = "qdrant_unavailable"
        elif status == "failed":
            reason = "startup_failed"
        elif not state["qdrant_ready"]:
            reason = "qdrant_unavailable"
        elif not state["models_ready"]:
            reason = "model_unavailable"
        else:
            reason = "engine_not_ready"
        return {
            "reason": reason,
            "status": status,
            "stage": state["stage"],
            "phase": "4.5",
            "message": state["message"],
            "engine_ready": state["engine_ready"],
            "api_ready": state["api_ready"],
            "retrieval_ready": state["retrieval_ready"],
            "qdrant_ready": state["qdrant_ready"],
            "models_ready": state["models_ready"],
            "documents_seen": state["documents_seen"],
            "documents_indexed": state["documents_indexed"],
        }

"""Shared backend runtime readiness state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Literal


RuntimeStatus = Literal["starting", "ready", "indexing", "degraded", "failed", "no_documents"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RuntimeState:
    status: RuntimeStatus = "starting"
    engine_available: bool = False
    engine_ready: bool = False
    documents_seen: int = 0
    documents_indexed: int = 0
    index_fresh: bool = False
    qdrant_ready: bool = False
    models_ready: bool = False
    last_startup_check_at: str | None = None
    last_index_run_at: str | None = None
    message: str = "Backend startup checks have not completed."

    def __post_init__(self) -> None:
        self._lock = RLock()

    def update(self, **values: object) -> None:
        with self._lock:
            for key, value in values.items():
                if not hasattr(self, key):
                    raise AttributeError(f"Unknown runtime state field: {key}")
                setattr(self, key, value)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            payload = asdict(self)
        payload.pop("_lock", None)
        return payload

    def chat_unavailable_detail(self) -> dict[str, object]:
        state = self.snapshot()
        status = str(state["status"])
        if status == "no_documents":
            reason = "no_documents_found"
        elif status == "indexing":
            reason = "indexing_in_progress"
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
            "phase": "4.5",
            "message": state["message"],
            "engine_ready": state["engine_ready"],
            "qdrant_ready": state["qdrant_ready"],
            "models_ready": state["models_ready"],
            "documents_seen": state["documents_seen"],
            "documents_indexed": state["documents_indexed"],
        }

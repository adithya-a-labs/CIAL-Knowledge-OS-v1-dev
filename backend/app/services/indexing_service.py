"""Indexing service state and coordination."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.core.runtime_state import RuntimeState
from .knowledge_engine_service import KnowledgeEngineService


class IndexingService:
    def __init__(self, engine: KnowledgeEngineService, runtime_state: RuntimeState) -> None:
        self.engine = engine
        self.runtime_state = runtime_state

    def status(self) -> dict[str, object]:
        return self.runtime_state.snapshot()

    def rebuild(self, *, force: bool) -> dict[str, object]:
        self.runtime_state.update(
            status="indexing",
            engine_ready=False,
            index_fresh=False,
            message="Index rebuild is running.",
        )
        try:
            counts = self.engine.prepare_pipeline(force_rebuild_index=force)
            models_ready, model_message = self.engine.check_ollama_model()
        except Exception as exc:  # noqa: BLE001 - route returns runtime state.
            message = str(exc)
            self.runtime_state.update(
                status="failed",
                engine_ready=False,
                qdrant_ready=False if "qdrant" in message.casefold() else self.runtime_state.snapshot()["qdrant_ready"],
                models_ready=False if "model" in message.casefold() else self.runtime_state.snapshot()["models_ready"],
                index_fresh=False,
                last_index_run_at=datetime.now(timezone.utc).isoformat(),
                message=message,
            )
            return self.runtime_state.snapshot()

        ready = bool(models_ready)
        self.runtime_state.update(
            status="ready" if ready else "degraded",
            engine_ready=ready,
            qdrant_ready=True,
            models_ready=ready,
            documents_seen=counts["documents_seen"],
            documents_indexed=counts["documents_indexed"],
            index_fresh=True,
            last_index_run_at=datetime.now(timezone.utc).isoformat(),
            message="Index rebuild completed." if ready else model_message,
        )
        return self.runtime_state.snapshot()

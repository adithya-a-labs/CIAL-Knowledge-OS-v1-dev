"""API-facing durable indexing coordination; no vector work runs here."""

from __future__ import annotations

from typing import Any
import uuid

from backend.app.core.runtime_state import RuntimeState
from backend.app.services.indexing_queue import DurableIndexQueue
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


class IndexingService:
    def __init__(self, engine: KnowledgeEngineService, runtime_state: RuntimeState) -> None:
        self.engine = engine
        self.runtime_state = runtime_state
        self.queue = DurableIndexQueue()

    def status(self) -> dict[str, Any]:
        try:
            queue_status = self.queue.status()
        except Exception:
            queue_status = {
                "indexer_state": "unknown",
                "indexer_seen": False,
                "queue_counts": {},
                "queue_by_operation": {},
                "latest_index_generation": 0,
                "bm25_generation": 0,
            }
        if (
            not self.runtime_state.retrieval_ready
            and int(queue_status.get("latest_index_generation") or 0) > 0
            and self.engine.refresh_query_runtime_if_needed()
        ):
            self.runtime_state.update(
                status="ready",
                stage="ready",
                retrieval_ready=True,
                engine_ready=True,
                index_fresh=bool(queue_status.get("index_fresh")),
                message="Query runtime activated from the latest committed index generation.",
            )
        payload = {**self.runtime_state.snapshot(), **queue_status}
        # Never expose a local absolute snapshot path through an admin-neutral
        # health endpoint.
        payload.pop("bm25_snapshot_path", None)
        payload["engine_ready"] = bool(payload.get("retrieval_ready"))
        return payload

    def rebuild(
        self,
        *,
        force: bool,
        scope: dict[str, Any] | None = None,
        requested_by: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        job = self.queue.enqueue_control(
            request_kind="rebuild",
            scope=scope,
            requested_by=requested_by,
            force=force,
            priority=10,
        )
        return {
            "status": "accepted",
            "job_id": str(job.id),
            "message": "Rebuild request queued for the standalone indexer.",
        }

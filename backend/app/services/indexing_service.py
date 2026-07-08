"""Indexing service state and coordination."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.schemas.indexing import IndexStatusResponse
from .knowledge_engine_service import KnowledgeEngineService


class IndexingService:
    def __init__(self, engine: KnowledgeEngineService) -> None:
        self.engine = engine
        self._status = IndexStatusResponse(status="idle", message="Indexing has not run in this API process.")

    def status(self) -> IndexStatusResponse:
        return self._status

    def rebuild(self, *, force: bool) -> IndexStatusResponse:
        self._status = IndexStatusResponse(status="indexing", message="Index rebuild is running.")
        ok, message, documents_seen, documents_indexed = self.engine.rebuild_index(force=force)
        self._status = IndexStatusResponse(
            status="completed" if ok else "failed",
            documents_seen=documents_seen,
            documents_indexed=documents_indexed,
            last_run_at=datetime.now(timezone.utc).isoformat(),
            message=message,
        )
        return self._status

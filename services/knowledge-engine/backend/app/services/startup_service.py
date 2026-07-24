"""Lightweight API readiness; corpus indexing belongs to ``indexer_main``."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.application_config import validate_repository_path
from backend.app.core.config import settings
from backend.app.core.runtime_state import RuntimeState, utc_now_iso
from backend.app.db.health import check_database_health
from backend.app.services.indexing_queue import DurableIndexQueue
from backend.app.services.knowledge_engine_service import KnowledgeEngineService

logger = logging.getLogger(__name__)


class StartupService:
    def __init__(
        self,
        *,
        engine: KnowledgeEngineService,
        runtime_state: RuntimeState,
        corpus_service: Any | None = None,
        workspace_ingestion: Any | None = None,
    ) -> None:
        # Kept as optional compatibility inputs for old composition roots. They
        # are deliberately never called during API startup.
        self.engine = engine
        self.runtime_state = runtime_state
        self.corpus_service = corpus_service
        self.workspace_ingestion = workspace_ingestion

    def run_startup(self) -> None:
        """Prepare query-time dependencies without corpus-wide work."""

        self.runtime_state.update(
            status="starting",
            api_ready=False,
            retrieval_ready=False,
            engine_available=self.engine.engine_available,
            engine_ready=False,
            last_startup_check_at=utc_now_iso(),
            message="API readiness checks are running.",
        )
        if settings.auto_index_on_startup or settings.force_rebuild_on_startup:
            logger.warning(
                "deprecated_api_startup_index_flags_ignored",
                extra={
                    "event": "startup",
                    "CIAL_AUTO_INDEX_ON_STARTUP": settings.auto_index_on_startup,
                    "CIAL_FORCE_REBUILD_ON_STARTUP": settings.force_rebuild_on_startup,
                },
            )
        try:
            self.validate_corpus_root()
            self.ensure_required_folders()
            database = check_database_health()
            database_ready = bool(database.database_ready)
            self.runtime_state.update(database_ready=database_ready)

            config = self.engine.build_config(force_rebuild_index=False)
            qdrant_ready, qdrant_message = self.check_qdrant(config)
            self.runtime_state.update(qdrant_ready=qdrant_ready)

            models_ready, model_message = self.engine.check_ollama_model(config)
            self.runtime_state.update(models_ready=models_ready)

            runtime: dict[str, Any] = {
                "retrieval_ready": False,
                "message": qdrant_message,
            }
            if qdrant_ready:
                runtime = self.engine.prepare_query_runtime()

            queue_status = DurableIndexQueue().status() if database_ready else {}
            retrieval_ready = bool(runtime.get("retrieval_ready") and models_ready)
            message = str(runtime.get("message") or qdrant_message)
            if runtime.get("retrieval_ready") and not models_ready:
                message = model_message
            self.runtime_state.update(
                status="ready" if retrieval_ready else "degraded",
                stage="ready" if retrieval_ready else "query_runtime_unavailable",
                api_ready=True,
                retrieval_ready=retrieval_ready,
                engine_ready=retrieval_ready,
                qdrant_ready=qdrant_ready,
                models_ready=models_ready,
                indexer_seen=bool(queue_status.get("indexer_seen")),
                indexer_state=str(queue_status.get("indexer_state") or "unknown"),
                index_fresh=bool(runtime.get("retrieval_ready")),
                latest_index_generation=int(queue_status.get("latest_index_generation") or 0),
                bm25_generation=int(queue_status.get("bm25_generation") or 0),
                last_startup_check_at=utc_now_iso(),
                message=message,
            )
        except Exception as exc:  # API process remains alive and observable.
            logger.exception("query_runtime_startup_failed")
            self.runtime_state.update(
                status="degraded",
                api_ready=True,
                retrieval_ready=False,
                engine_ready=False,
                last_startup_check_at=utc_now_iso(),
                message=f"API started, but retrieval is unavailable: {exc}",
            )

    def ensure_required_folders(self) -> None:
        for path in (
            settings.indexes_path,
            settings.bm25_path,
            settings.outputs_path,
            settings.models_path,
            settings.workspace_root_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate_corpus_root(self) -> None:
        result = validate_repository_path(settings.corpus_root_path)
        if not result.valid:
            raise RuntimeError(result.message)
        if not result.writable:
            logger.warning(
                "corpus_root_not_writable",
                extra={
                    "event": "startup",
                    "repository_id": settings.corpus_repository_id,
                },
            )

    # Compatibility helpers retained for tests and migration callers. They are
    # not consulted by ``run_startup``.
    def sync_corpus_metadata(self) -> None:
        return None

    def detect_documents(self) -> int:
        return 0

    def _should_skip_indexing(self, sync_summary: Any | None) -> bool:
        if settings.force_rebuild_on_startup:
            return False
        if sync_summary is not None and bool(getattr(sync_summary, "differences_found", False)):
            return False
        return not self._has_pending_jobs()

    def _has_pending_jobs(self) -> bool:
        return bool(DurableIndexQueue().status().get("queue_counts", {}).get("pending", 0))

    def _pending_job_count(self) -> int:
        return int(DurableIndexQueue().status().get("queue_counts", {}).get("pending", 0))

    @staticmethod
    def check_qdrant(config: Any) -> tuple[bool, str]:
        try:
            from cial_knowledge_os.vectorstore import create_qdrant_client

            client = create_qdrant_client(config)
            try:
                client.get_collections()
            finally:
                client.close()
        except Exception as exc:
            return False, f"Qdrant server is unavailable: {exc}"
        return True, "Qdrant server is available."

"""Backend startup readiness workflow for the Phase 4.5 engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.core.runtime_state import RuntimeState, utc_now_iso
from backend.app.services.knowledge_engine_service import KnowledgeEngineService

logger = logging.getLogger(__name__)

_SUPPORTED_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".csv",
    ".pptx",
    ".ppt",
    ".txt",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
}


class StartupService:
    def __init__(
        self,
        *,
        engine: KnowledgeEngineService,
        runtime_state: RuntimeState,
    ) -> None:
        self.engine = engine
        self.runtime_state = runtime_state

    def run_startup(self) -> None:
        """Prepare the Phase 4.5 pipeline without crashing the API process."""

        now = utc_now_iso()
        self.runtime_state.update(
            status="starting",
            engine_available=self.engine.engine_available,
            engine_ready=False,
            last_startup_check_at=now,
            message="Backend startup checks are running.",
        )
        try:
            self.ensure_required_folders()
            documents_seen = self.detect_documents()
            self.runtime_state.update(documents_seen=documents_seen)

            if not self.engine.engine_available:
                self.runtime_state.update(
                    status="failed",
                    engine_ready=False,
                    models_ready=False,
                    message="Phase 4.5 engine imports failed.",
                )
                return

            if documents_seen == 0:
                self.runtime_state.update(
                    status="no_documents",
                    engine_ready=False,
                    documents_indexed=0,
                    index_fresh=False,
                    message=(
                        f"No documents were found under {settings.data_files_path}. "
                        "Add documents and rebuild or restart the backend."
                    ),
                )
                return

            config = self.engine.build_config(
                force_rebuild_index=settings.force_rebuild_on_startup
            )
            qdrant_ready, qdrant_message = self.check_qdrant(config)
            self.runtime_state.update(qdrant_ready=qdrant_ready)
            if not qdrant_ready:
                self.runtime_state.update(
                    status="failed",
                    engine_ready=False,
                    message=qdrant_message,
                )
                return

            ollama_ready, ollama_message = self.engine.check_ollama_model(config)
            self.runtime_state.update(models_ready=ollama_ready)

            if not settings.auto_index_on_startup:
                self.runtime_state.update(
                    status="degraded",
                    engine_ready=False,
                    message="Automatic startup indexing is disabled.",
                )
                return

            self.runtime_state.update(
                status="indexing",
                engine_ready=False,
                message="Indexing documents with Phase4RAGPipeline.",
            )
            counts = self.engine.prepare_pipeline(
                force_rebuild_index=settings.force_rebuild_on_startup
            )
            self.runtime_state.update(
                documents_seen=counts["documents_seen"] or documents_seen,
                documents_indexed=counts["documents_indexed"],
                index_fresh=True,
                last_index_run_at=utc_now_iso(),
            )

            if not ollama_ready:
                self.runtime_state.update(
                    status="degraded",
                    engine_ready=False,
                    models_ready=False,
                    message=ollama_message,
                )
                return

            self.runtime_state.update(
                status="ready",
                engine_ready=True,
                models_ready=True,
                message="Phase 4.5 engine is ready.",
            )
        except Exception as exc:  # noqa: BLE001 - startup must not crash the API.
            logger.exception("phase45_startup_failed")
            self.runtime_state.update(
                status="failed",
                engine_ready=False,
                models_ready=False,
                message=f"Phase 4.5 startup failed: {exc}",
            )

    def ensure_required_folders(self) -> None:
        for path in (
            settings.data_files_path,
            settings.indexes_path,
            settings.bm25_path,
            settings.outputs_path,
            settings.models_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def detect_documents(self) -> int:
        root = settings.data_files_path
        if not root.exists():
            return 0
        return sum(
            1
            for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() in _SUPPORTED_DOCUMENT_SUFFIXES
        )

    @staticmethod
    def check_qdrant(config: Any) -> tuple[bool, str]:
        try:
            from qdrant_client import QdrantClient
        except Exception as exc:  # noqa: BLE001
            return False, f"Qdrant client dependency is unavailable: {exc}"

        client: QdrantClient | None = None
        try:
            if config.qdrant_mode == "server":
                client = QdrantClient(
                    url=config.qdrant_url,
                    api_key=config.qdrant_api_key,
                )
            elif config.qdrant_mode == "embedded":
                Path(config.qdrant_dir).mkdir(parents=True, exist_ok=True)
                client = QdrantClient(path=str(config.qdrant_dir))
            else:
                return False, f"Unsupported Qdrant mode: {config.qdrant_mode}"
            client.get_collections()
        except Exception as exc:  # noqa: BLE001
            return False, f"Qdrant is unavailable for mode '{config.qdrant_mode}': {exc}"
        finally:
            if client is not None:
                client.close()
        return True, "Qdrant is available."

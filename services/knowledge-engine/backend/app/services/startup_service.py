"""Backend startup readiness workflow for the Phase 4.5 engine."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from backend.app.core.application_config import validate_repository_path
from backend.app.core.config import settings
from backend.app.core.runtime_state import RuntimeState, utc_now_iso
from backend.app.db.session import SessionLocal
from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from cial_knowledge_os.corpus.metadata import CorpusMetadataStore
from cial_knowledge_os.corpus.models import CorpusSyncSummary
from cial_knowledge_os.corpus.service import CorpusService

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

_STAGE_MESSAGES = {
    "load": "Loading documents with Phase4RAGPipeline.load().",
    "loaded": "Documents loaded.",
    "chunk": "Chunking documents with Phase4RAGPipeline.chunk().",
    "chunked": "Documents chunked.",
    "embed": "Embedding chunks with Phase4RAGPipeline.embed().",
    "embedded": "Chunk embeddings created.",
    "index": "Indexing chunks with Phase4RAGPipeline.index().",
    "indexed": "Vector and BM25 indexes updated; loading Phase 4 reranker.",
    "reranker": "Loading Phase 4 reranker.",
    "ready": "Phase 4.5 pipeline initialization completed.",
}


class StartupService:
    def __init__(
        self,
        *,
        engine: KnowledgeEngineService,
        runtime_state: RuntimeState,
        corpus_service: CorpusService | None = None,
    ) -> None:
        self.engine = engine
        self.runtime_state = runtime_state
        self.corpus_service = corpus_service

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
            self.validate_corpus_root()
            logger.info(
                "corpus_repository_config_loaded",
                extra={
                    "event": "startup",
                    "corpus_root": str(settings.corpus_root_path),
                    "repository_id": settings.corpus_repository_id,
                    "application_config_file": settings.application_config_file,
                },
            )
            self.ensure_required_folders()
            sync_summary = self.sync_corpus_metadata()
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
                        f"No documents were found under {settings.corpus_root_path}. "
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

            # --- Incremental skip logic ---
            skip_indexing = self._should_skip_indexing(sync_summary)
            changed_files = (
                int(getattr(sync_summary, "files_added", 0) or 0)
                + int(getattr(sync_summary, "files_modified", 0) or 0)
                + int(getattr(sync_summary, "files_moved", 0) or 0)
                + int(getattr(sync_summary, "files_renamed", 0) or 0)
            ) if sync_summary is not None else 0
            removed_files = int(getattr(sync_summary, "files_removed", 0) or 0) if sync_summary is not None else 0
            decision = "skip" if skip_indexing else ("full_rebuild" if settings.force_rebuild_on_startup else "incremental")
            decision_reason = (
                "force_rebuild_requested" if settings.force_rebuild_on_startup
                else "index_current" if skip_indexing
                else "corpus_changes_or_pending_jobs"
            )
            logger.info(
                "corpus_startup_indexing_decision",
                extra={
                    "event": "startup",
                    "decision": decision,
                    "reason": decision_reason,
                    "discovered_files": documents_seen,
                    "changed_files": changed_files,
                    "removed_files": removed_files,
                    "collection_name": config.qdrant_collection_name,
                    "index_stale": not skip_indexing,
                    "metadata_schema_version": 2,
                    "expected_metadata_schema_version": 2,
                },
            )

            if skip_indexing:
                logger.info(
                    "corpus_startup_indexing_skipped",
                    extra={
                        "event": "startup",
                        "reason": "no_changes",
                        "documents_seen": documents_seen,
                        "indexing_mode": "skip",
                    },
                )
                # Still need to initialize the pipeline for chat readiness
                self.runtime_state.update(
                    status="indexing",
                    engine_ready=False,
                    message="Loading pipeline (no indexing work needed).",
                )
            else:
                pending_count = self._pending_job_count()
                logger.info(
                    "corpus_startup_indexing_started",
                    extra={
                        "event": "startup",
                        "pending_jobs": pending_count,
                        "force_rebuild": settings.force_rebuild_on_startup,
                        "indexing_mode": decision,
                        "changed_files": changed_files,
                        "removed_files": removed_files,
                    },
                )
                self.runtime_state.update(
                    status="indexing",
                    engine_ready=False,
                    message="Indexing documents with Phase4RAGPipeline.",
                )

            counts = self.engine.prepare_pipeline(
                force_rebuild_index=settings.force_rebuild_on_startup,
                on_stage=self._on_pipeline_stage,
            )
            self.runtime_state.update(
                documents_seen=counts["documents_seen"] or documents_seen,
                documents_indexed=counts["documents_indexed"],
                index_fresh=True,
                last_index_run_at=utc_now_iso(),
            )

            # Mark all pending startup jobs as succeeded
            self._complete_pending_startup_jobs()

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
                stage="ready",
                engine_ready=True,
                models_ready=True,
                message="Phase 4.5 engine is ready.",
            )
            logger.info(
                "knowledge_engine_ready",
                extra={
                    "event": "knowledge_engine_state",
                    "ready": True,
                    "stage": "ready",
                    "collection_name": config.qdrant_collection_name,
                    "bm25_ready": bool(getattr(self.engine._pipeline, "bm25_retriever", None)),
                    "reranker_ready": bool(getattr(self.engine._pipeline, "reranker", None)),
                    "pipeline_loaded": self.engine.is_ready(),
                },
            )
        except Exception as exc:  # noqa: BLE001 - startup must not crash the API.
            logger.exception("phase45_startup_failed")
            self.runtime_state.update(
                status="failed",
                engine_ready=False,
                models_ready=False,
                message=f"Phase 4.5 startup failed: {exc}",
            )

    def sync_corpus_metadata(self) -> CorpusSyncSummary | None:
        """Run corpus sync and return the summary for skip-logic decisions."""
        if not settings.corpus_sync_on_startup or self.corpus_service is None:
            return None
        try:
            summary = self.corpus_service.sync()
        except Exception as exc:  # noqa: BLE001 - metadata sync must not crash chat startup.
            logger.exception("corpus_startup_sync_failed")
            self.runtime_state.update(
                message=f"Corpus metadata sync failed; continuing startup: {exc}",
            )
            return None
        log_payload = summary.to_dict()
        log_payload["sync_message"] = log_payload.pop("message", "")
        logger.info(
            "corpus_startup_sync_completed",
            extra={"event": "corpus_sync", **log_payload},
        )
        return summary

    def _should_skip_indexing(self, sync_summary: CorpusSyncSummary | None) -> bool:
        """Decide whether to skip the indexing pipeline on startup.

        Skip when:
        - Corpus sync found zero differences.
        - No pending indexing jobs exist in the database.
        - Not a force-rebuild.
        """
        if settings.force_rebuild_on_startup:
            return False
        if sync_summary is not None and sync_summary.differences_found:
            return False
        if self._has_pending_jobs():
            return False
        return True

    def _has_pending_jobs(self) -> bool:
        """Check whether any pending indexing jobs exist in the DB."""
        if SessionLocal is None:
            return False
        try:
            with SessionLocal() as session:
                store = CorpusMetadataStore(session)
                return store.has_pending_jobs()
        except Exception:  # noqa: BLE001
            return False

    def _pending_job_count(self) -> int:
        """Return the number of pending indexing jobs."""
        if SessionLocal is None:
            return 0
        try:
            with SessionLocal() as session:
                store = CorpusMetadataStore(session)
                return len(store.pending_jobs())
        except Exception:  # noqa: BLE001
            return 0

    def _complete_pending_startup_jobs(self) -> None:
        """Mark all pending startup-created indexing jobs as succeeded."""
        if SessionLocal is None:
            return
        try:
            with SessionLocal() as session:
                store = CorpusMetadataStore(session)
                jobs = store.pending_jobs()
                for job in jobs:
                    store.mark_job_running(job.id)
                    store.mark_job_succeeded(
                        job.id,
                        message="Completed during startup pipeline indexing.",
                    )
                    # Update associated document
                    if job.document_id is not None:
                        from backend.app.models.knowledge import Document
                        document = session.get(Document, job.document_id)
                        if document is not None:
                            document.indexed = True
                            document.indexing_status = "indexed"
                            document.lifecycle_status = "indexed"
                            document.indexed_at = datetime.now(timezone.utc)
                session.commit()
                if jobs:
                    logger.info(
                        "corpus_startup_jobs_completed",
                        extra={
                            "event": "startup",
                            "jobs_completed": len(jobs),
                        },
                    )
        except Exception:  # noqa: BLE001 - non-critical
            logger.exception("corpus_startup_jobs_completion_failed")

    def ensure_required_folders(self) -> None:
        for path in (
            settings.indexes_path,
            settings.bm25_path,
            settings.outputs_path,
            settings.models_path,
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
                    "corpus_root": str(result.path),
                    "repository_id": settings.corpus_repository_id,
                },
            )

    def detect_documents(self) -> int:
        root = settings.corpus_root_path
        if not root.exists():
            return 0
        return sum(
            1
            for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() in _SUPPORTED_DOCUMENT_SUFFIXES
        )

    def _on_pipeline_stage(self, stage: str, counts: dict[str, int]) -> None:
        values: dict[str, object] = {
            "status": "indexing",
            "stage": stage,
            "engine_ready": False,
            "last_startup_check_at": utc_now_iso(),
            "message": _STAGE_MESSAGES.get(stage, f"Phase 4.5 startup stage: {stage}."),
        }
        if counts.get("documents_seen"):
            values["documents_seen"] = counts["documents_seen"]
        if stage in {"indexed", "reranker", "ready"}:
            values["documents_indexed"] = counts["documents_indexed"]
            values["index_fresh"] = bool(counts["documents_indexed"])
            values["last_index_run_at"] = utc_now_iso()
        self.runtime_state.update(**values)

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

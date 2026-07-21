"""Development FastAPI application for CIAL Knowledge OS."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import sys
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.paths import KNOWLEDGE_ENGINE_SRC

if str(KNOWLEDGE_ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(KNOWLEDGE_ENGINE_SRC))

from backend.app.api.routes import auth, chat, corpus, documents, evaluation, exports, health, indexing, notes, summaries, settings as settings_routes, workspaces
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.core.runtime_state import RuntimeState
from backend.app.db.session import SessionLocal
from backend.app.services.document_service import DocumentService
from backend.app.services.evaluation_service import EvaluationService
from backend.app.services.export_service import ExportService
from backend.app.services.indexing_service import IndexingService
from backend.app.services.indexing_worker import IndexingWorker
from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from backend.app.services.message_transformation_service import OllamaTransformationGenerator
from backend.app.services.managed_workspace_ingestion import ManagedWorkspaceIngestionService
from backend.app.services.startup_service import StartupService
from cial_knowledge_os.corpus.service import CorpusService
from cial_knowledge_os.corpus.watcher import CorpusWatcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    watchers = []
    if settings.corpus_watch:
        watcher = CorpusWatcher(
            root=settings.corpus_root_path,
            sync_callback=lambda: (app.state.corpus_service.sync(), app.state.indexing_worker.enqueue()),
        )
        try:
            watcher.start()
            app.state.corpus_watcher = watcher
            watchers.append(watcher)
            workspace_watcher = CorpusWatcher(
                root=settings.workspace_root_path,
                sync_callback=lambda: (app.state.workspace_ingestion.sync(), app.state.indexing_worker.enqueue()),
            )
            workspace_watcher.start()
            app.state.workspace_watcher = workspace_watcher
            watchers.append(workspace_watcher)
        except Exception as exc:  # noqa: BLE001 - watcher is optional.
            logger.exception("corpus_watcher_start_failed")
            app.state.corpus_watcher_error = str(exc)

    # Start background indexing worker
    app.state.indexing_worker.start()
    app.state.export_service.start()

    startup_thread = Thread(
        target=app.state.startup_service.run_startup,
        name="phase45-startup",
        daemon=True,
    )
    app.state.startup_thread = startup_thread
    startup_thread.start()
    try:
        yield
    finally:
        for watcher in watchers:
            watcher.stop()
        app.state.indexing_worker.stop()
        app.state.export_service.stop()
        app.state.knowledge_engine.close()


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="CIAL Knowledge OS API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = KnowledgeEngineService()
    runtime_state = RuntimeState(engine_available=engine.engine_available)
    corpus_service = CorpusService(
        root=settings.corpus_root_path,
        session_factory=SessionLocal,
        hash_algorithm=settings.corpus_hash,
        batch_size=settings.metadata_batch_size,
        repository_id=settings.corpus_repository_id,
    )
    workspace_ingestion = ManagedWorkspaceIngestionService(root=settings.workspace_root_path, session_factory=SessionLocal)
    startup_service = StartupService(engine=engine, runtime_state=runtime_state,
        corpus_service=corpus_service, workspace_ingestion=workspace_ingestion)
    indexing_worker = IndexingWorker(
        engine=engine,
        runtime_state=runtime_state,
        corpus_sync=corpus_service.sync if SessionLocal is not None else None,
    )
    app.state.runtime_state = runtime_state
    app.state.knowledge_engine = engine
    app.state.corpus_service = corpus_service
    app.state.startup_service = startup_service
    app.state.indexing_worker = indexing_worker
    app.state.workspace_ingestion = workspace_ingestion
    app.state.document_service = DocumentService(root=settings.corpus_root_path)
    app.state.indexing_service = IndexingService(engine, runtime_state)
    app.state.evaluation_service = EvaluationService()
    app.state.export_service = ExportService(indexing_wakeup=indexing_worker.enqueue)
    app.state.transformation_generator = OllamaTransformationGenerator()

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(corpus.router, prefix="/api", tags=["corpus"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(documents.router, prefix="/api", tags=["documents"])
    app.include_router(indexing.router, prefix="/api", tags=["indexing"])
    app.include_router(settings_routes.router, prefix="/api", tags=["settings"])
    app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
    app.include_router(notes.router, prefix="/api", tags=["notes"])
    app.include_router(summaries.router, prefix="/api", tags=["summaries"])
    app.include_router(evaluation.router, prefix="/api", tags=["evaluation"])
    app.include_router(exports.router, prefix="/api", tags=["exports"])
    return app


app = create_app()

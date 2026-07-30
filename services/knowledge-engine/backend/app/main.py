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

from backend.app.api.routes import admin_system, auth, chat, corpus, documents, evaluation, exports, health, indexing, notes, saved_knowledge, search, summaries, settings as settings_routes, workspaces
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.core.runtime_state import RuntimeState
from backend.app.db.session import SessionLocal
from backend.app.services.document_service import DocumentService
from backend.app.services.evaluation_service import EvaluationService
from backend.app.services.export_service import ExportService
from backend.app.services.indexing_service import IndexingService
from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from backend.app.services.message_transformation_service import OllamaTransformationGenerator
from backend.app.services.startup_service import StartupService
from backend.app.services.summary_worker import SummaryWorker
from backend.app.services.system_status_service import SystemStatusService
from backend.app.services.admin_system_monitor_service import AdminSystemMonitorService
from backend.app.services.chat_concurrency import ChatConcurrencyController
from cial_knowledge_os.corpus.service import CorpusService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.chat_concurrency.start()
    app.state.export_service.start()
    app.state.summary_worker.start()

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
        app.state.summary_worker.stop()
        app.state.export_service.stop()
        app.state.chat_concurrency.close()
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
    startup_service = StartupService(
        engine=engine,
        runtime_state=runtime_state,
        corpus_service=corpus_service,
    )
    app.state.runtime_state = runtime_state
    app.state.knowledge_engine = engine
    app.state.chat_concurrency = ChatConcurrencyController()
    app.state.corpus_service = corpus_service
    app.state.startup_service = startup_service
    app.state.document_service = DocumentService(root=settings.corpus_root_path)
    app.state.indexing_service = IndexingService(engine, runtime_state)
    app.state.system_status_service = SystemStatusService(
        runtime_state=runtime_state,
        engine=engine,
        indexing_service=app.state.indexing_service,
    )
    app.state.admin_system_monitor_service = AdminSystemMonitorService(
        system_status_service=app.state.system_status_service,
        runtime_state=runtime_state,
        engine=engine,
        indexing_service=app.state.indexing_service,
        chat_concurrency=app.state.chat_concurrency,
    )
    app.state.evaluation_service = EvaluationService()
    app.state.export_service = ExportService()
    transformation_generator = OllamaTransformationGenerator(
        generation_context_factory=lambda cancel_event=None: (
            app.state.chat_concurrency.external_generation(
                cancel_event=cancel_event
            )
        )
    )
    app.state.transformation_generator = transformation_generator
    app.state.summary_worker = SummaryWorker(transformation_generator)

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(admin_system.router, prefix="/api", tags=["admin-system"])
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(corpus.router, prefix="/api", tags=["corpus"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(documents.router, prefix="/api", tags=["documents"])
    app.include_router(indexing.router, prefix="/api", tags=["indexing"])
    app.include_router(settings_routes.router, prefix="/api", tags=["settings"])
    app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
    app.include_router(notes.router, prefix="/api", tags=["notes"])
    app.include_router(search.router, prefix="/api", tags=["search"])
    app.include_router(saved_knowledge.router, prefix="/api", tags=["saved-knowledge"])
    app.include_router(summaries.router, prefix="/api", tags=["summaries"])
    app.include_router(evaluation.router, prefix="/api", tags=["evaluation"])
    app.include_router(exports.router, prefix="/api", tags=["exports"])
    return app


app = create_app()

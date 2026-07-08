"""Development FastAPI application for CIAL Knowledge OS."""

from __future__ import annotations

from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import chat, documents, evaluation, exports, health, indexing
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.core.runtime_state import RuntimeState
from backend.app.services.document_service import DocumentService
from backend.app.services.evaluation_service import EvaluationService
from backend.app.services.export_service import ExportService
from backend.app.services.indexing_service import IndexingService
from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from backend.app.services.startup_service import StartupService


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    startup_service = StartupService(engine=engine, runtime_state=runtime_state)
    app.state.runtime_state = runtime_state
    app.state.knowledge_engine = engine
    app.state.startup_service = startup_service
    app.state.document_service = DocumentService(root=settings.data_files_path)
    app.state.indexing_service = IndexingService(engine, runtime_state)
    app.state.evaluation_service = EvaluationService()
    app.state.export_service = ExportService()

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(documents.router, prefix="/api", tags=["documents"])
    app.include_router(indexing.router, prefix="/api", tags=["indexing"])
    app.include_router(evaluation.router, prefix="/api", tags=["evaluation"])
    app.include_router(exports.router, prefix="/api", tags=["exports"])
    return app


app = create_app()

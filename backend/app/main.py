"""Development FastAPI application for CIAL Knowledge OS."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import chat, documents, evaluation, exports, health, indexing
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.services.document_service import DocumentService
from backend.app.services.evaluation_service import EvaluationService
from backend.app.services.export_service import ExportService
from backend.app.services.indexing_service import IndexingService
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="CIAL Knowledge OS API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = KnowledgeEngineService()
    app.state.knowledge_engine = engine
    app.state.document_service = DocumentService()
    app.state.indexing_service = IndexingService(engine)
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

"""Health route."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.core.config import settings
from backend.app.db.health import check_database_health

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    runtime = request.app.state.runtime_state.snapshot()
    database = check_database_health().as_dict()
    return {
        "status": runtime["status"],
        "service": settings.app_name,
        "phase": settings.phase,
        "engine_available": runtime["engine_available"],
        "engine_ready": runtime["engine_ready"],
        "qdrant_ready": runtime["qdrant_ready"],
        "models_ready": runtime["models_ready"],
        "documents_seen": runtime["documents_seen"],
        "documents_indexed": runtime["documents_indexed"],
        "index_fresh": runtime["index_fresh"],
        "message": runtime["message"],
        **database,
    }

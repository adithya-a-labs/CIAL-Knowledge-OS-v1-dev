"""Health route."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.core.config import settings

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    engine = request.app.state.knowledge_engine
    return {
        "status": "ok",
        "service": settings.app_name,
        "phase": settings.phase,
        "engine_available": engine.engine_available,
    }

"""Health route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.app.core.config import settings
from backend.app.db.health import check_database_health
from backend.app.security.access import require_authenticated_access_context

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }


@router.get("/system/status")
def system_status(
    request: Request,
    _access_context: object = Depends(require_authenticated_access_context),
) -> dict[str, object]:
    """Return the authenticated AI Assistant health contract."""

    return request.app.state.system_status_service.snapshot()

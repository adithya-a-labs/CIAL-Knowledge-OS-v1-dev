"""Indexing routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.schemas.indexing import IndexStatusResponse, RebuildIndexRequest, RebuildIndexResponse
from backend.app.security.access import can_manage_settings, require_authenticated_access_context

router = APIRouter()


@router.post("/index/rebuild", response_model=RebuildIndexResponse, status_code=status.HTTP_202_ACCEPTED)
def rebuild_index(payload: RebuildIndexRequest, request: Request) -> dict[str, object]:
    access = require_authenticated_access_context(request)
    if not can_manage_settings(access):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrative permission required.")
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Explicit rebuild confirmation is required.")
    return request.app.state.indexing_service.rebuild(
        force=payload.force,
        scope=payload.scope,
        requested_by=access.principal.user_id,
    )


@router.get("/index/status", response_model=IndexStatusResponse)
def index_status(request: Request) -> dict[str, object]:
    return request.app.state.indexing_service.status()


@router.get("/indexer/status", response_model=IndexStatusResponse, include_in_schema=True)
def indexer_status(request: Request) -> dict[str, object]:
    """Compatibility alias using the service-oriented v2 endpoint name."""

    return request.app.state.indexing_service.status()

"""Indexing routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.schemas.indexing import (
    IndexStatusResponse,
    RebuildIndexRequest,
    RebuildIndexResponse,
)

router = APIRouter()


@router.post("/index/rebuild", response_model=RebuildIndexResponse)
def rebuild_index(payload: RebuildIndexRequest, request: Request) -> RebuildIndexResponse:
    status = request.app.state.indexing_service.rebuild(force=payload.force)
    return RebuildIndexResponse(
        status="completed" if status.status == "completed" else "failed",
        message=status.message,
    )


@router.get("/index/status", response_model=IndexStatusResponse)
def index_status(request: Request) -> IndexStatusResponse:
    return request.app.state.indexing_service.status()

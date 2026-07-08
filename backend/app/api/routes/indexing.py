"""Indexing routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.schemas.indexing import IndexStatusResponse, RebuildIndexRequest

router = APIRouter()


@router.post("/index/rebuild", response_model=IndexStatusResponse)
def rebuild_index(payload: RebuildIndexRequest, request: Request) -> dict[str, object]:
    return request.app.state.indexing_service.rebuild(force=payload.force)


@router.get("/index/status", response_model=IndexStatusResponse)
def index_status(request: Request) -> dict[str, object]:
    return request.app.state.indexing_service.status()

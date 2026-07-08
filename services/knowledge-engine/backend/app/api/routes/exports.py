"""Export routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.schemas.exports import ExportListResponse

router = APIRouter()


@router.get("/exports", response_model=ExportListResponse)
def list_exports(request: Request) -> ExportListResponse:
    return ExportListResponse(exports=request.app.state.export_service.list_exports())

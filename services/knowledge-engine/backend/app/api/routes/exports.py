"""Export routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from backend.app.core.paths import OUTPUTS_ROOT
from backend.app.security.access import require_authenticated_access_context
from backend.app.db.session import get_db_session
from backend.app.repositories.chats import ChatRepository
from sqlalchemy.orm import Session

from backend.app.schemas.exports import ExportListResponse

router = APIRouter()


@router.get("/exports", response_model=ExportListResponse)
def list_exports(request: Request) -> ExportListResponse:
    return ExportListResponse(exports=request.app.state.export_service.list_exports())


@router.get("/exports/chat/{filename}")
def download_chat_export(filename: str, request: Request, db: Session = Depends(get_db_session)):
    access = require_authenticated_access_context(request)
    if filename != __import__('pathlib').Path(filename).name or not filename.startswith("cial-response-"):
        raise HTTPException(status_code=404, detail="Export not found.")
    try:
        message_id = __import__('uuid').UUID(filename.removeprefix("cial-response-")[:36])
    except ValueError:
        raise HTTPException(status_code=404, detail="Export not found.")
    if ChatRepository(db).get_message_for_user(message_id, access.principal.user_id) is None:
        raise HTTPException(status_code=404, detail="Export not found.")
    path = OUTPUTS_ROOT / "chat" / filename
    if not path.is_file(): raise HTTPException(status_code=404, detail="Export not found.")
    return FileResponse(path, filename=filename)

"""Authenticated global search routes."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.search import RecentSearchList, SearchRequest, SearchResponse
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.personal_workspace_service import WorkspaceNotFound
from backend.app.services.search_service import SearchService

router = APIRouter()


def service(db: Session = Depends(get_db_session)) -> SearchService:
    return SearchService(db)


def invoke(request: Request, current: SearchService, method: str, *args):
    access = require_authenticated_access_context(request)
    try:
        return getattr(current, method)(access, *args)
    except WorkspaceNotFound as exc:
        raise HTTPException(404, detail="Search context was not found.") from exc
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.post("/search", response_model=SearchResponse)
def global_search(payload: SearchRequest, request: Request, current: SearchService = Depends(service)):
    return invoke(request, current, "search", payload)


@router.get("/search/recent", response_model=RecentSearchList)
def recent_searches(request: Request, current: SearchService = Depends(service)):
    return invoke(request, current, "recent")


@router.delete("/search/recent", status_code=204)
def clear_recent_searches(request: Request, current: SearchService = Depends(service)):
    invoke(request, current, "clear_recent", None)


@router.delete("/search/recent/{history_id}", status_code=204)
def delete_recent_search(history_id: uuid.UUID, request: Request, current: SearchService = Depends(service)):
    invoke(request, current, "clear_recent", history_id)

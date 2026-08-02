"""Authenticated personal notebook workspace routes."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.notebooks import (
    NotebookArtifactCreate, NotebookArtifactList, NotebookArtifactRecord,
    NotebookChatBindingRecord, NotebookCreate, NotebookList, NotebookRecord,
    NotebookSourceList, NotebookSourceRecord, NotebookSourceReorder,
    NotebookSourcesAttach, NotebookSourceUpdate, NotebookUpdate,
)
from backend.app.security.access import RequestAccessContext, require_authenticated_access_context
from backend.app.services.notebook_service import NotebookArtifactService, NotebookChatBindingService, NotebookNotFound, NotebookService, NotebookSourceService
from backend.app.services.summary_service import SummaryError

router = APIRouter()


def _notebooks(db: Session = Depends(get_db_session)): return NotebookService(db)
def _sources(db: Session = Depends(get_db_session)): return NotebookSourceService(db)
def _bindings(db: Session = Depends(get_db_session)): return NotebookChatBindingService(db)


def _safe(callable_):
    try: return callable_()
    except NotebookNotFound as exc: raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "notebook_not_found", "message": str(exc)}) from exc
    except (ValueError, SummaryError) as exc: raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "notebook_invalid_request", "message": str(exc)}) from exc


@router.get("/notebooks", response_model=NotebookList)
def list_notebooks(access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookService = Depends(_notebooks)):
    return {"items": [service.payload(item) for item in service.list(access)]}


@router.post("/notebooks", response_model=NotebookRecord, status_code=201)
def create_notebook(payload: NotebookCreate, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookService = Depends(_notebooks)):
    return _safe(lambda: service.payload(service.create(access, payload)))


@router.get("/notebooks/{notebook_id}", response_model=NotebookRecord)
def get_notebook(notebook_id: uuid.UUID, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookService = Depends(_notebooks)):
    return _safe(lambda: service.payload(service.get(access, notebook_id)))


@router.patch("/notebooks/{notebook_id}", response_model=NotebookRecord)
def update_notebook(notebook_id: uuid.UUID, payload: NotebookUpdate, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookService = Depends(_notebooks)):
    return _safe(lambda: service.payload(service.update(access, notebook_id, payload)))


@router.delete("/notebooks/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: uuid.UUID, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookService = Depends(_notebooks)):
    _safe(lambda: service.delete(access, notebook_id)); return Response(status_code=204)


def _source_list(access, service, notebook_id):
    items = [service.payload(access, row) for row in service.list(access, notebook_id)]
    return {"items": items, "attached_count": len(items), "active_count": sum(bool(item["is_default_active"]) for item in items), "ready_count": sum(bool(item["ready"]) for item in items)}


@router.get("/notebooks/{notebook_id}/sources", response_model=NotebookSourceList)
def list_notebook_sources(notebook_id: uuid.UUID, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookSourceService = Depends(_sources)):
    return _safe(lambda: _source_list(access, service, notebook_id))


@router.post("/notebooks/{notebook_id}/sources", response_model=NotebookSourceList, status_code=201)
def attach_notebook_sources(notebook_id: uuid.UUID, payload: NotebookSourcesAttach, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookSourceService = Depends(_sources)):
    def call(): service.attach(access, notebook_id, payload.sources); return _source_list(access, service, notebook_id)
    return _safe(call)


@router.patch("/notebooks/{notebook_id}/sources/{source_id}", response_model=NotebookSourceRecord)
def update_notebook_source(notebook_id: uuid.UUID, source_id: uuid.UUID, payload: NotebookSourceUpdate, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookSourceService = Depends(_sources)):
    return _safe(lambda: service.payload(access, service.update(access, notebook_id, source_id, payload.is_default_active)))


@router.delete("/notebooks/{notebook_id}/sources/{source_id}", status_code=204)
def detach_notebook_source(notebook_id: uuid.UUID, source_id: uuid.UUID, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookSourceService = Depends(_sources)):
    _safe(lambda: service.detach(access, notebook_id, source_id)); return Response(status_code=204)


@router.post("/notebooks/{notebook_id}/sources/reorder", response_model=NotebookSourceList)
def reorder_notebook_sources(notebook_id: uuid.UUID, payload: NotebookSourceReorder, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookSourceService = Depends(_sources)):
    def call(): service.reorder(access, notebook_id, payload.source_ids); return _source_list(access, service, notebook_id)
    return _safe(call)


@router.get("/notebooks/{notebook_id}/chat-session", response_model=NotebookChatBindingRecord)
@router.post("/notebooks/{notebook_id}/chat-session", response_model=NotebookChatBindingRecord)
def notebook_chat_session(notebook_id: uuid.UUID, access: RequestAccessContext = Depends(require_authenticated_access_context), service: NotebookChatBindingService = Depends(_bindings)):
    return _safe(lambda: service.payload(access, service.get_or_create(access, notebook_id)))


@router.get("/notebooks/{notebook_id}/artifacts", response_model=NotebookArtifactList)
def list_notebook_artifacts(notebook_id: uuid.UUID, request: Request, access: RequestAccessContext = Depends(require_authenticated_access_context), db: Session = Depends(get_db_session)):
    service = NotebookArtifactService(db, request.app.state.transformation_generator)
    return _safe(lambda: {"items": [service.payload(item) for item in service.list(access, notebook_id)]})


@router.post("/notebooks/{notebook_id}/artifacts", response_model=NotebookArtifactRecord, status_code=201)
def create_notebook_artifact(notebook_id: uuid.UUID, payload: NotebookArtifactCreate, request: Request, access: RequestAccessContext = Depends(require_authenticated_access_context), db: Session = Depends(get_db_session)):
    service = NotebookArtifactService(db, request.app.state.transformation_generator)
    return _safe(lambda: service.payload(service.create(access, notebook_id, payload)))


@router.get("/notebooks/{notebook_id}/artifacts/{artifact_id}", response_model=NotebookArtifactRecord)
def get_notebook_artifact(notebook_id: uuid.UUID, artifact_id: uuid.UUID, request: Request, access: RequestAccessContext = Depends(require_authenticated_access_context), db: Session = Depends(get_db_session)):
    service = NotebookArtifactService(db, request.app.state.transformation_generator)
    return _safe(lambda: service.payload(service.get(access, notebook_id, artifact_id)))


@router.delete("/notebooks/{notebook_id}/artifacts/{artifact_id}", status_code=204)
def delete_notebook_artifact(notebook_id: uuid.UUID, artifact_id: uuid.UUID, request: Request, access: RequestAccessContext = Depends(require_authenticated_access_context), db: Session = Depends(get_db_session)):
    service = NotebookArtifactService(db, request.app.state.transformation_generator)
    _safe(lambda: service.delete(access, notebook_id, artifact_id)); return Response(status_code=204)

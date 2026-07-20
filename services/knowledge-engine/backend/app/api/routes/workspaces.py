"""Thin authenticated routes for the caller's private workspace."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.schemas.workspaces import FolderCreate, WorkspacePreferences
from backend.app.security.access import RequestAccessContext, require_authenticated_access_context
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceAuthenticationRequired, WorkspaceNotFound

router = APIRouter()


def _service(session: Session = Depends(get_db_session)) -> PersonalWorkspaceService:
    return PersonalWorkspaceService(session)


def _call(access_context: RequestAccessContext, service: PersonalWorkspaceService, method: str, *args):
    try:
        result = getattr(service, method)(access_context, *args)
        if method in {"get_or_create", "tree", "folder", "summary", "preferences"}:
            service.session.commit()
        return result
    except WorkspaceAuthenticationRequired as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except WorkspaceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/workspaces/me")
def workspace_me(access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    workspace = _call(access_context, service, "get_or_create")
    return service._workspace_payload(workspace)


@router.get("/workspaces/me/summary")
def workspace_summary(access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "summary")


@router.get("/workspaces/me/tree")
def workspace_tree(access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "tree")


@router.get("/workspaces/me/root")
def workspace_root(access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "folder", None)


@router.get("/workspaces/me/folders/{folder_id}")
def workspace_folder(folder_id: uuid.UUID, access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "folder", folder_id)


@router.post("/workspaces/me/folders", status_code=status.HTTP_201_CREATED)
def create_workspace_folder(payload: FolderCreate, access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "create_folder", payload.name, uuid.UUID(payload.parent_id) if payload.parent_id else None)


@router.get("/workspaces/me/preferences", response_model=WorkspacePreferences, response_model_by_alias=True)
def get_workspace_preferences(access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "preferences")


@router.patch("/workspaces/me/preferences", response_model=WorkspacePreferences, response_model_by_alias=True)
def save_workspace_preferences(payload: WorkspacePreferences, access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "save_preferences", payload)


@router.post("/workspaces/me/preferences/reset", response_model=WorkspacePreferences, response_model_by_alias=True)
def reset_workspace_preferences(access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "reset_preferences")


@router.post("/workspaces/me/documents/upload", status_code=status.HTTP_201_CREATED)
def upload_workspace_document(file: UploadFile = File(...), folder_id: str | None = Form(default=None), access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    return _call(access_context, service, "upload", file.filename or "upload", file.file, uuid.UUID(folder_id) if folder_id else None)


@router.delete("/workspaces/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_document(document_id: uuid.UUID, access_context: RequestAccessContext = Depends(require_authenticated_access_context), service: PersonalWorkspaceService = Depends(_service)):
    _call(access_context, service, "delete_document", document_id)

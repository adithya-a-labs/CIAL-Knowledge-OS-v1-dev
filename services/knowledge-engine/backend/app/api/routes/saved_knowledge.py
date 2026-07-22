"""Saved Knowledge CRUD routes."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from backend.app.db.session import get_db_session
from backend.app.schemas.saved_knowledge import SavedKnowledgeCreate, SavedKnowledgeList, SavedKnowledgeRecord, SavedKnowledgeUpdate
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.personal_workspace_service import WorkspaceNotFound
from backend.app.services.saved_knowledge_service import SavedKnowledgeConflict, SavedKnowledgeService

router=APIRouter()
def service(db:Session=Depends(get_db_session)):return SavedKnowledgeService(db)
def invoke(request,current,method,*args):
    access=require_authenticated_access_context(request)
    try:return getattr(current,method)(access,*args)
    except WorkspaceNotFound as exc:raise HTTPException(404,detail="Saved Knowledge item not found.") from exc
    except SavedKnowledgeConflict as exc:raise HTTPException(409,detail={"code":"version_conflict","message":str(exc)}) from exc
    except ValueError as exc:raise HTTPException(422,detail=str(exc)) from exc

@router.post("/saved-knowledge",response_model=SavedKnowledgeRecord,status_code=201)
def create_saved(payload:SavedKnowledgeCreate,request:Request,current:SavedKnowledgeService=Depends(service)):return invoke(request,current,"create_from_message",payload)
@router.get("/saved-knowledge",response_model=SavedKnowledgeList)
def list_saved(request:Request,query:str="",favorite:bool=False,collection:str|None=None,limit:int=Query(50,ge=1,le=100),current:SavedKnowledgeService=Depends(service)):return invoke(request,current,"list",query,favorite,collection,limit)
@router.get("/saved-knowledge/{item_id}",response_model=SavedKnowledgeRecord)
def get_saved(item_id:uuid.UUID,request:Request,current:SavedKnowledgeService=Depends(service)):return invoke(request,current,"get",item_id)
@router.patch("/saved-knowledge/{item_id}",response_model=SavedKnowledgeRecord)
def update_saved(item_id:uuid.UUID,payload:SavedKnowledgeUpdate,request:Request,current:SavedKnowledgeService=Depends(service)):return invoke(request,current,"update",item_id,payload)
@router.delete("/saved-knowledge/{item_id}",status_code=204)
def delete_saved(item_id:uuid.UUID,request:Request,current:SavedKnowledgeService=Depends(service)):invoke(request,current,"delete",item_id)
@router.post("/saved-knowledge/{item_id}/duplicate",response_model=SavedKnowledgeRecord,status_code=201)
def duplicate_saved(item_id:uuid.UUID,request:Request,current:SavedKnowledgeService=Depends(service)):return invoke(request,current,"duplicate",item_id)
@router.post("/saved-knowledge/{item_id}/convert-to-note",status_code=201)
def convert_saved_to_note(item_id:uuid.UUID,request:Request,current:SavedKnowledgeService=Depends(service)):return invoke(request,current,"convert_to_note",item_id)

"""Authenticated private note routes."""
from __future__ import annotations
import re, uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from backend.app.db.session import get_db_session
from backend.app.schemas.notes import LinkDocumentCreate, NoteCreate, NoteList, NoteRecord, NoteUpdate, TagCreate, TagUpdate
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.note_service import NoteConflict, NoteService
from backend.app.services.personal_workspace_service import WorkspaceNotFound

router=APIRouter()
def service(db:Session=Depends(get_db_session)): return NoteService(db)
def conflict_detail(exc:NoteConflict):
    current=NoteRecord.model_validate(exc.current).model_dump(mode="json")
    return jsonable_encoder({"code":"revision_conflict","message":str(exc),"current":current})
def call(request:Request, svc:NoteService, method:str,*args):
    access=require_authenticated_access_context(request)
    try: return getattr(svc,method)(access,*args)
    except WorkspaceNotFound as exc: raise HTTPException(404,detail=str(exc)) from exc
    except NoteConflict as exc:
        raise HTTPException(409,detail=conflict_detail(exc)) from exc
    except ValueError as exc: raise HTTPException(422,detail=str(exc)) from exc
def enqueue(request:Request,svc:NoteService):
    worker=getattr(request.app.state,"indexing_worker",None)
    if worker is not None and svc.last_index_job_id is not None: worker.enqueue(svc.last_index_job_id)

@router.get("/workspaces/me/notes",response_model=NoteList)
def list_notes(request:Request,query:str="",filter:str="all",tag_id:uuid.UUID|None=None,cursor:str|None=None,limit:int=Query(25,ge=1,le=100),svc:NoteService=Depends(service)): return call(request,svc,"list",query,filter,tag_id,cursor,limit)
@router.post("/workspaces/me/notes",response_model=NoteRecord,status_code=201)
def create_note(payload:NoteCreate,request:Request,svc:NoteService=Depends(service)):
    result=call(request,svc,"create",payload.title);enqueue(request,svc);return result
@router.get("/workspaces/me/notes/{note_id}",response_model=NoteRecord)
def get_note(note_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): return call(request,svc,"get",note_id)
@router.patch("/workspaces/me/notes/{note_id}",response_model=NoteRecord)
def update_note(note_id:uuid.UUID,payload:NoteUpdate,request:Request,svc:NoteService=Depends(service)):
    result=call(request,svc,"update",note_id,payload);enqueue(request,svc);return result
@router.delete("/workspaces/me/notes/{note_id}",status_code=204)
def delete_note(note_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): call(request,svc,"delete",note_id);enqueue(request,svc)
@router.post("/workspaces/me/notes/{note_id}/restore",response_model=NoteRecord)
def restore_note(note_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)):
    result=call(request,svc,"restore",note_id);enqueue(request,svc);return result
@router.post("/workspaces/me/notes/{note_id}/duplicate",response_model=NoteRecord,status_code=201)
def duplicate_note(note_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)):
    result=call(request,svc,"duplicate",note_id);enqueue(request,svc);return result
@router.get("/workspaces/me/notes/{note_id}/versions")
def note_versions(note_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): return {"items":call(request,svc,"versions",note_id)}
@router.get("/workspaces/me/note-tags")
def list_tags(request:Request,svc:NoteService=Depends(service)): return {"items":call(request,svc,"tags")}
@router.post("/workspaces/me/note-tags",status_code=201)
def create_tag(payload:TagCreate,request:Request,svc:NoteService=Depends(service)): return call(request,svc,"create_tag",payload.name,payload.color)
@router.patch("/workspaces/me/note-tags/{tag_id}")
def rename_tag(tag_id:uuid.UUID,payload:TagUpdate,request:Request,svc:NoteService=Depends(service)): return call(request,svc,"rename_tag",tag_id,payload.name,payload.color)
@router.delete("/workspaces/me/note-tags/{tag_id}",status_code=204)
def delete_tag(tag_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): call(request,svc,"delete_tag",tag_id)
@router.post("/workspaces/me/notes/{note_id}/tags/{tag_id}",response_model=NoteRecord)
def add_tag(note_id:uuid.UUID,tag_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): return call(request,svc,"add_tag",note_id,tag_id)
@router.delete("/workspaces/me/notes/{note_id}/tags/{tag_id}",status_code=204)
def remove_tag(note_id:uuid.UUID,tag_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): call(request,svc,"remove_tag",note_id,tag_id)
@router.post("/workspaces/me/notes/{note_id}/documents",response_model=NoteRecord)
def link_document(note_id:uuid.UUID,payload:LinkDocumentCreate,request:Request,svc:NoteService=Depends(service)): return call(request,svc,"link_document",note_id,payload.document_id)
@router.delete("/workspaces/me/notes/{note_id}/documents/{document_id}",status_code=204)
def unlink_document(note_id:uuid.UUID,document_id:uuid.UUID,request:Request,svc:NoteService=Depends(service)): call(request,svc,"unlink_document",note_id,document_id)
@router.get("/workspaces/me/notes/{note_id}/export")
def export_note(note_id:uuid.UUID,request:Request,format:str="markdown",svc:NoteService=Depends(service)):
    if format!="markdown": raise HTTPException(422,detail="Only markdown export is supported for notes.")
    access=require_authenticated_access_context(request); note=call(request,svc,"get",note_id); safe=re.sub(r"[^A-Za-z0-9._-]+","-",note["title"]).strip("-") or "note"
    svc._audit(access.principal.user_id,"workspace.note.exported",note["id"]); svc.session.commit()
    return Response(note["content_markdown"],media_type="text/markdown; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{safe[:80]}.md"'})

"""Grounded summary APIs, including NDJSON operational progress."""
from __future__ import annotations
import json, queue, threading, uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.app.db.session import get_db_session
from backend.app.schemas.summaries import SaveSummaryNote, SummaryCreate, SummaryList, SummaryRecord
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.personal_workspace_service import WorkspaceNotFound
from backend.app.services.summary_service import SummaryError, SummaryService

router=APIRouter()
def svc(request:Request,db:Session=Depends(get_db_session)): return SummaryService(db,request.app.state.transformation_generator)
def invoke(request,service,method,*args):
    access=require_authenticated_access_context(request)
    try:return getattr(service,method)(access,*args)
    except WorkspaceNotFound as exc: raise HTTPException(404,detail=str(exc)) from exc
    except SummaryError as exc: raise HTTPException(422,detail={"code":"summary_error","message":str(exc)}) from exc

@router.post("/summaries",response_model=SummaryRecord,status_code=201)
def create_summary(payload:SummaryCreate,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"create",payload)
@router.get("/summaries",response_model=SummaryList)
def list_summaries(request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"list")

@router.post("/summaries/stream")
def stream_summary(payload:SummaryCreate,request:Request,service:SummaryService=Depends(svc)):
    access=require_authenticated_access_context(request); request_id=str(uuid.uuid4()); events:queue.Queue=queue.Queue(); cancelled=threading.Event()
    def emit(stage_id,metrics):
        if cancelled.is_set(): raise SummaryError("Summary generation cancelled.")
        event_metrics=dict(metrics); status_value=event_metrics.pop("status","started")
        events.put({"request_id":request_id,"type":"stage","stage_id":stage_id,"status":status_value,"metrics":event_metrics})
    def run():
        try:
            result=service.create(access,payload,emit); events.put({"request_id":request_id,"type":"result","stage_id":"complete","status":"completed","payload":jsonable_encoder(result)})
        except Exception: events.put({"request_id":request_id,"type":"error","stage_id":"complete","status":"failed","payload":{"message":"The local summary could not be completed."}})
        finally: events.put(None)
    thread=threading.Thread(target=run,name=f"summary-{request_id}",daemon=True); thread.start()
    def body():
        try:
            while True:
                item=events.get()
                if item is None: break
                yield json.dumps(item,separators=(",",":"))+"\n"
        finally: cancelled.set()
    return StreamingResponse(body(),media_type="application/x-ndjson",headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})

@router.get("/summaries/{summary_id}",response_model=SummaryRecord)
def get_summary(summary_id:uuid.UUID,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"get",summary_id)
@router.delete("/summaries/{summary_id}",status_code=204)
def delete_summary(summary_id:uuid.UUID,request:Request,service:SummaryService=Depends(svc)): invoke(request,service,"delete",summary_id)
@router.post("/summaries/{summary_id}/save-to-note")
def save_to_note(summary_id:uuid.UUID,payload:SaveSummaryNote,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"save_to_note",summary_id,payload.title)
@router.get("/summaries/{summary_id}/export")
def export_summary(summary_id:uuid.UUID,request:Request,format:str="markdown",service:SummaryService=Depends(svc)):
    if format!="markdown": raise HTTPException(422,detail="Only Markdown summary export is currently supported.")
    item=invoke(request,service,"get",summary_id)
    if item["status"]!="completed": raise HTTPException(409,detail="Summary is not complete.")
    return Response(item["content_markdown"] or "",media_type="text/markdown; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="summary-{summary_id}.md"'})

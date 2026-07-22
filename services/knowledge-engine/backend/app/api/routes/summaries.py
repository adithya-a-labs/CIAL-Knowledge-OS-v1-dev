"""Grounded summary APIs, including NDJSON operational progress."""
from __future__ import annotations
import json, os, queue, re, tempfile, threading, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.background import BackgroundTasks
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from backend.app.db.session import get_db_session
from typing import Literal
from backend.app.schemas.summaries import DocumentAnalysisCreate, DocumentAnalysisCreateResponse, DocumentAnalysisListResponse, SaveSummaryNote, SummaryConfig, SummaryCreate, SummaryFollowUp, SummaryList, SummaryRecord
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.personal_workspace_service import WorkspaceNotFound
from backend.app.services.summary_service import SummaryCancelled, SummaryError, SummaryService
from backend.app.services.document_summary_service import DocumentSummaryError, DocumentSummaryService
from backend.app.models.workspace_content import SummaryArtifact
from backend.app.services.export_document import ExportDocument, ExportSource, MarkdownExportParser, cited_reference_ids
from backend.app.services.export_renderers import DocxRenderer, PdfRenderer

router=APIRouter()
def svc(request:Request,db:Session=Depends(get_db_session)): return SummaryService(db,request.app.state.transformation_generator)
def document_svc(request:Request,db:Session=Depends(get_db_session)): return DocumentSummaryService(db,request.app.state.transformation_generator)
def invoke(request,service,method,*args):
    access=require_authenticated_access_context(request)
    try:return getattr(service,method)(access,*args)
    except WorkspaceNotFound as exc: raise HTTPException(404,detail=str(exc)) from exc
    except SummaryError as exc: raise HTTPException(422,detail={"code":"summary_error","message":str(exc)}) from exc

def invoke_document(request,service,method,*args):
    access=require_authenticated_access_context(request)
    try:return getattr(service,method)(access,*args)
    except DocumentSummaryError as exc: raise HTTPException(exc.status_code,detail={"code":exc.code,"message":str(exc)}) from exc

@router.get("/documents/{document_id}/analysis",response_model=DocumentAnalysisListResponse)
def get_document_analysis(document_id:uuid.UUID,request:Request,summary_type:Literal["overview","detailed","key_points","action_items"]="overview",length:Literal["brief","standard","detailed"]="standard",service:DocumentSummaryService=Depends(document_svc)):
    return invoke_document(request,service,"get_analysis",document_id,summary_type,length)

@router.post("/documents/{document_id}/analysis",response_model=DocumentAnalysisCreateResponse,status_code=202)
def create_document_analysis(document_id:uuid.UUID,payload:DocumentAnalysisCreate,request:Request,service:DocumentSummaryService=Depends(document_svc)):
    result=invoke_document(request,service,"create",document_id,payload)
    if result["disposition"]=="queued": request.app.state.summary_worker.enqueue(result["summary"]["id"])
    return result

@router.post("/summaries",response_model=SummaryRecord,status_code=201)
def create_summary(payload:SummaryCreate,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"create",payload)
@router.get("/summaries",response_model=SummaryList)
def list_summaries(request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"list")

@router.get("/summaries/config",response_model=SummaryConfig)
def summary_config(): return SummaryConfig()

@router.get("/summaries/new",response_model=SummaryConfig,include_in_schema=False)
def legacy_summary_config(): return SummaryConfig()

@router.post("/summaries/stream")
def stream_summary(payload:SummaryCreate,request:Request,service:SummaryService=Depends(svc)):
    access=require_authenticated_access_context(request); request_id=str(uuid.uuid4()); events:queue.Queue=queue.Queue(); cancelled=threading.Event()
    def emit(stage_id,metrics):
        if cancelled.is_set(): raise SummaryError("Summary generation cancelled.")
        event_metrics=dict(metrics); status_value=event_metrics.pop("status","started")
        events.put({"request_id":request_id,"type":"stage","stage_id":stage_id,"status":status_value,"metrics":event_metrics})
    def token(delta):
        if cancelled.is_set(): raise SummaryCancelled("Summary generation cancelled.")
        events.put({"request_id":request_id,"type":"token","stage_id":"documents.merging","status":"started","delta":delta})
    def run():
        try:
            result=service.create(access,payload,emit,token,cancelled); events.put({"request_id":request_id,"type":"result","stage_id":"complete","status":"completed","payload":jsonable_encoder(result)})
        except SummaryCancelled: events.put({"request_id":request_id,"type":"cancelled","stage_id":"complete","status":"failed","payload":{"message":"Summary generation stopped."}})
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
def get_summary(summary_id:uuid.UUID,request:Request,service:SummaryService=Depends(svc),document_service:DocumentSummaryService=Depends(document_svc)):
    row=service.db.get(SummaryArtifact,summary_id)
    return invoke_document(request,document_service,"get",summary_id) if row is not None and row.document_id is not None else invoke(request,service,"get",summary_id)
@router.get("/summaries/{summary_id}/status",response_model=SummaryRecord)
def get_summary_status(summary_id:uuid.UUID,request:Request,service:DocumentSummaryService=Depends(document_svc)): return invoke_document(request,service,"get",summary_id)
@router.post("/summaries/{summary_id}/cancel",response_model=SummaryRecord)
def cancel_document_summary(summary_id:uuid.UUID,request:Request,service:DocumentSummaryService=Depends(document_svc)): return invoke_document(request,service,"cancel",summary_id)
@router.delete("/summaries/{summary_id}",status_code=204)
def delete_summary(summary_id:uuid.UUID,request:Request,service:SummaryService=Depends(svc)): invoke(request,service,"delete",summary_id)
@router.post("/summaries/{summary_id}/save-to-note")
def save_to_note(summary_id:uuid.UUID,payload:SaveSummaryNote,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"save_to_note",summary_id,payload.title)
@router.post("/summaries/{summary_id}/save-to-saved-knowledge",status_code=201)
def save_to_saved(summary_id:uuid.UUID,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"save_to_saved_knowledge",summary_id)
@router.post("/summaries/{summary_id}/ask-follow-up")
def ask_follow_up(summary_id:uuid.UUID,payload:SummaryFollowUp,request:Request,service:SummaryService=Depends(svc)): return invoke(request,service,"ask_follow_up",summary_id,payload.mode)
@router.get("/summaries/{summary_id}/export")
def export_summary(summary_id:uuid.UUID,request:Request,background_tasks:BackgroundTasks,format:str="markdown",service:SummaryService=Depends(svc)):
    if format not in {"markdown","pdf","docx"}: raise HTTPException(422,detail="Choose markdown, pdf, or docx.")
    item=invoke(request,service,"get",summary_id)
    if item["status"]!="completed": raise HTTPException(409,detail="Summary is not complete.")
    references=[]
    for citation in item["citations"]:
        source=next((value for value in item["sources"] if value.get("source_id") in {citation.get("document_id"),citation.get("note_id")}),None)
        label=(source or {}).get("title") or citation.get("section") or "Source"
        location=f", p. {citation['page_number']}" if citation.get("page_number") else ""
        references.append(f"[{citation['citation_id']}] {label}{location}")
    markdown=(item["content_markdown"] or "").rstrip()+"\n\n## Sources\n\n"+"\n".join(f"- {value}" for value in references)
    safe=re.sub(r"[^A-Za-z0-9._-]+","-",item["title"]).strip("-")[:80] or f"summary-{summary_id}"
    if format=="markdown": return Response(markdown,media_type="text/markdown; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{safe}.md"'})
    export_sources=[]
    for citation in item["citations"]:
        source=next((value for value in item["sources"] if value.get("source_id") in {citation.get("document_id"),citation.get("note_id")}),None)
        try: number=int(citation["citation_id"])
        except (TypeError,ValueError): continue
        export_sources.append(ExportSource(citation_number=number,document_title=(source or {}).get("title") or citation.get("section") or "Source",page_number=citation.get("page_number")))
    document=ExportDocument(title=item["title"],subtitle=None,generated_at=item.get("completed_at") or datetime.now(timezone.utc),query=None,context_metadata={},blocks=MarkdownExportParser().parse(item["content_markdown"] or ""),citations=cited_reference_ids(item["content_markdown"] or ""),sources=export_sources,footer_metadata={"summary_id":str(summary_id)})
    descriptor,path=tempfile.mkstemp(prefix="cial-summary-",suffix=f".{format}");os.close(descriptor)
    try: (PdfRenderer() if format=="pdf" else DocxRenderer()).render(document,__import__('pathlib').Path(path))
    except Exception: os.unlink(path);raise HTTPException(500,detail="The summary export could not be generated.")
    background_tasks.add_task(os.unlink,path)
    mime="application/pdf" if format=="pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path,media_type=mime,filename=f"{safe}.{format}")

"""Authenticated durable export job API."""
from __future__ import annotations
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from backend.app.db.session import get_db_session
from backend.app.repositories.exports import ExportRepository
from backend.app.schemas.exports import ExportCreateRequest, ExportCreateResponse, ExportJobResponse, ExportListResponse, ExportPreview, ExportProgress, ExportWorkspaceSaveRequest, ExportWorkspaceSaveResponse
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.export_service import ExportError, suggested_workspace_filename

router=APIRouter()
def _error(exc:ExportError):return HTTPException(status_code=exc.status_code,detail={"code":exc.code,"message":str(exc)})
def _owned(export_id,request,db):
    access=require_authenticated_access_context(request);job=ExportRepository(db).get_for_user(export_id,access.principal.user_id)
    if job is None:raise HTTPException(status_code=404,detail={"code":"export_not_found","message":"Export not found."})
    if job.expires_at<=datetime.now(timezone.utc) and job.status not in {"expired","cancelled"}:job.status="expired";job.progress_stage="expired";db.commit()
    return job
def _response(job):
    ready=job.status=="ready"
    return ExportJobResponse(export_id=job.id,format=job.format,status=job.status,progress=ExportProgress(stage=job.progress_stage,percent=job.progress_percent),error={"code":job.error_code or "export_failed","message":job.safe_error_message or "Export failed."} if job.status=="failed" else None,filename=job.output_filename if ready else None,mime_type=job.output_mime_type if ready else None,file_size_bytes=job.file_size_bytes if ready else None,preview=ExportPreview(type="pdf" if job.format=="pdf" else "html",url=f"/api/exports/{job.id}/preview") if ready else None,download_url=f"/api/exports/{job.id}/download" if ready else None,suggested_workspace_filename=suggested_workspace_filename(job) if ready else None)

@router.post("/exports",response_model=ExportCreateResponse,status_code=status.HTTP_202_ACCEPTED)
def create_export(payload:ExportCreateRequest,request:Request,db:Session=Depends(get_db_session)):
    access=require_authenticated_access_context(request)
    try:job=request.app.state.export_service.create(db,access.principal.user_id,payload)
    except ExportError as exc:raise _error(exc) from exc
    return ExportCreateResponse(export_id=job.id,status="queued")
@router.get("/exports",response_model=ExportListResponse)
def list_exports(request:Request):
    require_authenticated_access_context(request);return ExportListResponse(exports=request.app.state.export_service.list_exports())
@router.get("/exports/{export_id}",response_model=ExportJobResponse)
def get_export(export_id:uuid.UUID,request:Request,db:Session=Depends(get_db_session)):return _response(_owned(export_id,request,db))
@router.get("/exports/{export_id}/preview")
def preview_export(export_id:uuid.UUID,request:Request,db:Session=Depends(get_db_session)):
    job=_owned(export_id,request,db)
    if job.status!="ready":raise HTTPException(status_code=409,detail={"code":"export_not_ready","message":"Export is not ready."})
    try:path=request.app.state.export_service.artifact(job,preview=job.format=="docx")
    except ExportError as exc:raise _error(exc) from exc
    headers={"X-Content-Type-Options":"nosniff"}
    if job.format=="pdf":return FileResponse(path,media_type="application/pdf",headers={**headers,"Content-Disposition":f'inline; filename="{job.output_filename}"'})
    headers["Content-Security-Policy"]="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; font-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    return HTMLResponse(path.read_text(encoding="utf-8"),headers=headers)
@router.get("/exports/{export_id}/download")
def download_export(export_id:uuid.UUID,request:Request,db:Session=Depends(get_db_session)):
    job=_owned(export_id,request,db)
    if job.status!="ready":raise HTTPException(status_code=409,detail={"code":"export_not_ready","message":"Export is not ready."})
    try:path=request.app.state.export_service.artifact(job)
    except ExportError as exc:raise _error(exc) from exc
    job.downloaded_at=datetime.now(timezone.utc);db.commit()
    return FileResponse(path,media_type=job.output_mime_type,filename=job.output_filename,headers={"X-Content-Type-Options":"nosniff"})
@router.post("/exports/{export_id}/save-to-workspace",response_model=ExportWorkspaceSaveResponse,status_code=status.HTTP_201_CREATED)
def save_export_to_workspace(export_id:uuid.UUID,payload:ExportWorkspaceSaveRequest,request:Request,db:Session=Depends(get_db_session)):
    access=require_authenticated_access_context(request);job=_owned(export_id,request,db)
    try:return ExportWorkspaceSaveResponse.model_validate(request.app.state.export_service.save_to_workspace(db,access,job,payload.filename,payload.folder_id))
    except ExportError as exc:raise _error(exc) from exc
@router.delete("/exports/{export_id}",status_code=204)
def delete_export(export_id:uuid.UUID,request:Request,db:Session=Depends(get_db_session)):
    job=_owned(export_id,request,db);request.app.state.export_service.cancel(db,job);return Response(status_code=204)

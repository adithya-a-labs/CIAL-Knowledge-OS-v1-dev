"""Durable, immutable, backend-only assistant export job pipeline."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from html import unescape
import hashlib, json, logging, os, queue, re, shutil, unicodedata, uuid, zipfile
from pathlib import Path
from threading import Thread
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.operations import ExportJob
from backend.app.repositories.chats import ChatRepository
from backend.app.repositories.exports import ExportRepository
from backend.app.schemas.exports import ExportCreateRequest, ExportFile
from backend.app.services.export_document import ExportDocument, ExportSource, MarkdownExportParser, cited_reference_ids
from backend.app.services.export_renderers import DocxRenderer, HtmlPreviewRenderer, PdfRenderer
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceAuthenticationRequired, WorkspaceNotFound

_SENTINEL = object()
logger=logging.getLogger(__name__)
MIMES={"pdf":"application/pdf","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
WINDOWS_RESERVED={"con","prn","aux","nul",*(f"com{number}" for number in range(1,10)),*(f"lpt{number}" for number in range(1,10))}
WORKSPACE_FILENAME_MAX=160

class ExportError(RuntimeError):
    def __init__(self, message: str, code: str, status_code: int=400): super().__init__(message); self.code=code; self.status_code=status_code

def sanitize_filename(title: str, format: str, now: datetime) -> str:
    value=re.sub(r"[\x00-\x1f<>:\"/\\|?*]+"," ",title); value=re.sub(r"\s+"," ",value).strip(" .")[:80] or "Assistant-Response"
    value=value.replace(" ","-")
    return f"CIAL-Knowledge-OS_{value}_{now:%Y-%m-%d_%H-%M}.{format}"

def _workspace_name_stem(value: str) -> str:
    value=unescape(value);value=re.sub(r"<[^>]*>"," ",value);value=re.sub(r"!\[([^]]*)\]\([^)]*\)",r"\1",value);value=re.sub(r"\[([^]]+)\]\([^)]*\)",r"\1",value)
    value=re.sub(r"\[\d+\]"," ",value);value=re.sub(r"[`#*_~>]"," ",value);value=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode("ascii").casefold()
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]+',"-",value);value=re.sub(r"[^a-z0-9]+","-",value).strip("-. ")
    if value in WINDOWS_RESERVED:value=f"knowledge-os-{value}"
    return value

def suggested_workspace_filename(job, now: datetime | None=None) -> str:
    now=now or datetime.now(timezone.utc);source=(job.title or "").strip() or str((job.source_snapshot or {}).get("query") or "").strip() or "knowledge-os-export"
    stem=_workspace_name_stem(source) or "knowledge-os-export";suffix=f"_{now:%Y-%m-%d}.{job.format}";stem=stem[:WORKSPACE_FILENAME_MAX-len(suffix)].rstrip("-.") or "knowledge-os-export"
    return f"{stem}{suffix}"

def validate_workspace_filename(value: str | None, job, now: datetime | None=None) -> str:
    if value is None or not value.strip():return suggested_workspace_filename(job,now)
    raw=value.strip()
    if raw in {".",".."} or ".." in raw or "/" in raw or "\\" in raw or re.match(r"^[a-zA-Z]:",raw) or Path(raw).is_absolute():
        raise ExportError("Choose a filename without folders or path components.","invalid_export_filename",422)
    expected=f".{job.format}";provided=Path(raw).suffix.casefold()
    if provided and provided!=expected:raise ExportError(f"The filename extension must be {expected}.","invalid_export_filename",422)
    stem=_workspace_name_stem(raw[:-len(provided)] if provided else raw)
    if not stem:raise ExportError("Enter a valid filename.","invalid_export_filename",422)
    stem=stem[:WORKSPACE_FILENAME_MAX-len(expected)].rstrip("-.")
    return f"{stem}{expected}"

class ExportService:
    def __init__(self, outputs_root: Path | None=None, indexing_wakeup=None) -> None:
        self.root=(outputs_root or settings.export_root_path).resolve(); self._queue: queue.Queue[object]=queue.Queue(maxsize=settings.export_queue_limit); self._thread=None; self._running=False
        self.indexing_wakeup=indexing_wakeup
        self.parser=MarkdownExportParser(); self.pdf=PdfRenderer(); self.docx=DocxRenderer(); self.html=HtmlPreviewRenderer()
    def start(self):
        self.root.mkdir(parents=True,exist_ok=True)
        if SessionLocal:
            with SessionLocal() as db: repo=ExportRepository(db); repo.mark_interrupted_failed(); db.commit(); self.cleanup_expired(db)
        if self._thread and self._thread.is_alive(): return
        self._running=True; self._thread=Thread(target=self._loop,name="export-worker",daemon=True); self._thread.start()
    def stop(self):
        self._running=False
        try:self._queue.put_nowait(_SENTINEL)
        except queue.Full:pass
        if self._thread:self._thread.join(timeout=15)
    def list_exports(self) -> list[ExportFile]:
        from backend.app.core.paths import REPO_ROOT
        allowed={".csv",".xlsx",".html",".json",".jsonl",".log",".txt"}; result=[]
        outputs=settings.outputs_path
        if not outputs.exists():return []
        for path in sorted((p for p in outputs.rglob("*") if p.is_file() and p.suffix.casefold() in allowed),key=lambda p:p.stat().st_mtime,reverse=True)[:200]:
            relative=path.relative_to(REPO_ROOT).as_posix(); stat=path.stat(); result.append(ExportFile(id=hashlib.sha1(relative.encode()).hexdigest()[:16],name=path.name,path=relative,type=path.suffix.lstrip("."),size_bytes=stat.st_size,modified_at=datetime.fromtimestamp(stat.st_mtime,tz=timezone.utc).isoformat()))
        return result
    def create(self, db: Session, user_id: uuid.UUID, payload: ExportCreateRequest) -> ExportJob:
        message=ChatRepository(db).get_message_for_user(payload.message_id,user_id)
        if message is None or message.session_id != payload.session_id: raise ExportError("Message not found.","message_not_found",404)
        if message.role!="assistant" or not message.content.strip(): raise ExportError("This message cannot be exported.","message_not_exportable",422)
        if len(message.content.encode("utf-8"))>settings.export_max_content_bytes: raise ExportError("The response is too large to export.","content_too_large",413)
        user_meta=message.metadata_ or {}; question=None
        try:
            q=ChatRepository(db).get_message_for_user(uuid.UUID(str(user_meta.get("user_message_id"))),user_id); question=q.content if q and q.role=="user" else None
        except (ValueError,TypeError): pass
        snapshot={"content":message.content,"citations":message.citations or [],"sources":message.sources or [],"metadata":{k:v for k,v in user_meta.items() if k not in {"evidence_snapshot","generation_request"}},"query":question,"message_created_at":message.created_at.isoformat()}
        canonical=json.dumps(snapshot,sort_keys=True,separators=(",",":"),ensure_ascii=False); digest=hashlib.sha256(canonical.encode()).hexdigest()
        repo=ExportRepository(db)
        if repo.active_count(user_id)>=3 or repo.active_count()>=20: raise ExportError("Too many exports are already running.","export_limit_reached",429)
        job=repo.add(ExportJob(user_id=user_id,session_id=payload.session_id,message_id=payload.message_id,format=payload.format,status="queued",progress_stage="queued",progress_percent=0,title=payload.title.strip(),options=payload.options.model_dump(mode="json"),source_snapshot=snapshot,source_content_hash=digest,expires_at=datetime.now(timezone.utc)+timedelta(hours=settings.export_ttl_hours)))
        db.commit(); db.refresh(job)
        try:self._queue.put_nowait(job.id)
        except queue.Full: job.status="failed"; job.error_code="queue_full"; job.safe_error_message="The export queue is full. Please retry."; db.commit()
        return job
    def _loop(self):
        while self._running:
            item=self._queue.get()
            if item is _SENTINEL:return
            try:self.process(item)
            except Exception:logger.exception("export_worker_unhandled_error",extra={"export_id":str(item)})
    def _stage(self,db,job,stage,percent):
        db.refresh(job)
        if job.status=="cancelled":raise ExportError("Export cancelled.","cancelled",409)
        job.status="processing"; job.progress_stage=stage; job.progress_percent=percent
        if job.started_at is None:job.started_at=datetime.now(timezone.utc)
        db.commit()
    def _document(self,job):
        snap=job.source_snapshot; ids=cited_reference_ids(snap["content"]); source_by={int(str(x.get("id","0")).removeprefix("S")):x for x in snap["sources"] if str(x.get("id","")).removeprefix("S").isdigit()}
        sources=[]
        for number in ids if job.options.get("include_sources",True) else []:
            x=source_by.get(number)
            if not x:continue
            sources.append(ExportSource(number,str(x.get("document_name") or "Unknown document"),x.get("page_number") or x.get("page"),x.get("location_label"),x.get("repository_id"),x.get("file_url")))
        context={**(snap.get("metadata") or {}),"export_options":job.options}
        return ExportDocument(job.title,None,datetime.now(timezone.utc),snap.get("query"),context,self.parser.parse(snap["content"]),ids,sources,{"message_id":str(job.message_id)})
    def process(self,job_id):
        if not SessionLocal:return
        with SessionLocal() as db:
            job=ExportRepository(db).get(job_id)
            if not job or job.status!="queued":return
            temp_paths=[]
            try:
                self._stage(db,job,"loading_content",10)
                canonical=json.dumps(job.source_snapshot,sort_keys=True,separators=(",",":"),ensure_ascii=False)
                if hashlib.sha256(canonical.encode()).hexdigest()!=job.source_content_hash:raise ExportError("Export source changed.","stale_content")
                self._stage(db,job,"parsing",30); document=self._document(job)
                self._stage(db,job,"laying_out",50)
                folder=(self.root/hashlib.sha256(str(job.user_id).encode()).hexdigest()[:16]/str(job.id)).resolve()
                if self.root not in folder.parents:raise ExportError("Invalid export storage.","storage_error")
                folder.mkdir(parents=True,exist_ok=True); filename=sanitize_filename(job.title,job.format,datetime.now(timezone.utc)); final=folder/filename; temporary=folder/(filename+".tmp"); temp_paths.append(temporary)
                self._stage(db,job,"rendering",70)
                (self.pdf if job.format=="pdf" else self.docx).render(document,temporary)
                preview=None
                if job.format=="docx": preview=folder/"preview.html.tmp"; preview.write_text(self.html.render(document),encoding="utf-8"); temp_paths.append(preview)
                self._stage(db,job,"finalizing",90); self._validate(job.format,temporary); os.replace(temporary,final)
                if preview: preview_final=folder/"preview.html"; os.replace(preview,preview_final); job.preview_storage_key=str(preview_final.relative_to(self.root).as_posix())
                job.storage_key=str(final.relative_to(self.root).as_posix()); job.output_filename=filename; job.output_mime_type=MIMES[job.format]; job.file_size_bytes=final.stat().st_size; job.status="ready"; job.progress_stage="ready"; job.progress_percent=100; job.completed_at=datetime.now(timezone.utc); db.commit()
            except Exception as exc:
                for path in temp_paths:
                    try:path.unlink(missing_ok=True)
                    except OSError:pass
                if getattr(exc,"code",None)=="cancelled":job.status="cancelled";job.progress_stage="cancelled"
                else:
                    job.status="failed";job.progress_stage="failed";job.error_code=getattr(exc,"code","generation_failed")
                    job.safe_error_message=str(exc) if job.error_code=="unsupported_glyph" else "The export could not be generated."
                job.completed_at=datetime.now(timezone.utc);db.commit()
    def _validate(self,format,path):
        if not path.is_file() or path.stat().st_size<=0:raise ExportError("Empty export.","validation_failed")
        if format=="pdf" and path.read_bytes()[:4]!=b"%PDF":raise ExportError("Invalid PDF.","pdf_validation_failed")
        if format=="docx":
            if not zipfile.is_zipfile(path):raise ExportError("Invalid DOCX.","docx_validation_failed")
            with zipfile.ZipFile(path) as archive:
                if not {"[Content_Types].xml","word/document.xml"}.issubset(archive.namelist()):raise ExportError("Invalid DOCX.","docx_validation_failed")
    def artifact(self,job: ExportJob,preview=False)->Path:
        key=job.preview_storage_key if preview else job.storage_key
        if not key:raise ExportError("Export artifact is unavailable.","artifact_unavailable",409)
        path=(self.root/key).resolve()
        if self.root not in path.parents or path.is_symlink() or not path.is_file():raise ExportError("Export artifact is unavailable.","artifact_unavailable",404)
        return path
    def save_to_workspace(self,db:Session,access,job,filename:str|None=None,folder_id:uuid.UUID|None=None)->dict[str,object]:
        if job.status!="ready":raise ExportError("Export is not ready.","export_not_ready",409)
        if job.format not in MIMES:raise ExportError("This export format cannot be saved.","unsupported_export_format",422)
        try:source=self.artifact(job)
        except ExportError as exc:raise ExportError("The completed export artifact is unavailable.","export_artifact_missing",409) from exc
        final_name=validate_workspace_filename(filename,job)
        provenance={"export_job_id":str(job.id),"chat_session_id":str(job.session_id),"chat_message_id":str(job.message_id),"format":job.format,"source_content_hash":job.source_content_hash,"generated_at":job.completed_at.isoformat() if job.completed_at else None}
        try:
            payload=PersonalWorkspaceService(db).save_export_artifact(access,source,final_name,folder_id,provenance)
        except WorkspaceAuthenticationRequired as exc:raise ExportError("My Workspace is unavailable.","workspace_unavailable",401) from exc
        except WorkspaceNotFound as exc:
            if folder_id:raise ExportError("The selected My Workspace folder is unavailable.","workspace_folder_forbidden",404) from exc
            raise ExportError("My Workspace is temporarily unavailable.","workspace_unavailable",503) from exc
        except ValueError as exc:raise ExportError(str(exc),"workspace_save_failed",409) from exc
        except Exception as exc:
            logger.exception("export_save_to_workspace_failed",extra={"export_id":str(job.id),"user_id":str(access.principal.user_id)})
            raise ExportError("The export could not be saved to My Workspace.","workspace_save_failed",503) from exc
        if self.indexing_wakeup is not None and payload.get("indexing_job_id"):
            self.indexing_wakeup(uuid.UUID(str(payload["indexing_job_id"])))
        return {"document_id":payload["id"],"filename":payload["name"],"folder_id":payload.get("folder_id"),"file_type":payload["file_type"],"size_bytes":payload["size_bytes"],"indexing_status":payload["status"],"indexing_job_id":payload.get("indexing_job_id"),"open_url":f"/knowledge/document/{payload['id']}"}
    def cancel(self,db,job):
        if job.status in {"queued","processing"}:job.status="cancelled"; job.progress_stage="cancelled"; db.commit()
        elif job.status=="ready":
            try:shutil.rmtree(self.artifact(job).parent)
            except OSError:pass
            job.status="cancelled"; job.progress_stage="cancelled"; db.commit()
    def cleanup_expired(self,db):
        from sqlalchemy import select
        now=datetime.now(timezone.utc)
        for job in db.scalars(select(ExportJob).where(ExportJob.expires_at<=now,ExportJob.status.notin_(("expired","cancelled")))):
            if job.storage_key:
                try:shutil.rmtree(self.artifact(job).parent)
                except (OSError,ExportError):pass
            job.status="expired"; job.progress_stage="expired"
        db.commit()

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.operations import AuditEvent, IndexingJob
from backend.app.services.export_service import ExportError, ExportService, suggested_workspace_filename, validate_workspace_filename
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound


def job(format="pdf", title="Airport Emergency Response Checklist", status="ready"):
    return SimpleNamespace(id=uuid.uuid4(),user_id=uuid.uuid4(),session_id=uuid.uuid4(),message_id=uuid.uuid4(),format=format,title=title,status=status,source_snapshot={"query":None},source_content_hash="abc123",completed_at=datetime(2026,7,20,12,0,tzinfo=timezone.utc),storage_key=None)


def test_generated_filename_uses_title_date_and_format():
    assert suggested_workspace_filename(job(),datetime(2026,7,20,tzinfo=timezone.utc))=="airport-emergency-response-checklist_2026-07-20.pdf"


def test_generated_filename_uses_question_then_safe_fallback():
    value=job(title="");value.source_snapshot={"query":"How should we respond?"}
    assert suggested_workspace_filename(value,datetime(2026,7,20,tzinfo=timezone.utc))=="how-should-we-respond_2026-07-20.pdf"
    value.source_snapshot={};assert suggested_workspace_filename(value,datetime(2026,7,20,tzinfo=timezone.utc))=="knowledge-os-export_2026-07-20.pdf"


def test_generated_filename_removes_markup_citations_and_unsafe_characters():
    value=job(title='# **Airport** <b>Plan</b> [3] : "A/B"')
    assert suggested_workspace_filename(value,datetime(2026,7,20,tzinfo=timezone.utc))=="airport-plan-a-b_2026-07-20.pdf"


@pytest.mark.parametrize("reserved",["CON","prn","AUX","nul","COM1","LPT9"])
def test_windows_reserved_names_are_prefixed(reserved):
    assert validate_workspace_filename(f"{reserved}.pdf",job())==f"knowledge-os-{reserved.casefold()}.pdf"


def test_long_filename_is_bounded_without_losing_suffix():
    value=suggested_workspace_filename(job(title="Runway "*100),datetime(2026,7,20,tzinfo=timezone.utc))
    assert len(value)<=160 and value.endswith("_2026-07-20.pdf")


def test_user_filename_is_sanitized_and_extension_enforced():
    assert validate_workspace_filename("  My <Great> Export  ",job())=="my-export.pdf"
    with pytest.raises(ExportError,match="extension must be .pdf"):validate_workspace_filename("report.docx",job())


@pytest.mark.parametrize("value",["../report.pdf","folder/report.pdf",r"folder\report.pdf",r"C:\report.pdf",".."])
def test_path_components_are_rejected(value):
    with pytest.raises(ExportError) as error:validate_workspace_filename(value,job())
    assert error.value.code=="invalid_export_filename"


def test_collision_suffix_is_deterministic_without_overwrite():
    class Session:
        def scalars(self,query):return ["report.pdf","report-2.pdf"]
    assert PersonalWorkspaceService(Session())._available_name(uuid.uuid4(),uuid.uuid4(),"report.pdf")=="report-3.pdf"
    requested="r"*156+".pdf"
    bounded=PersonalWorkspaceService(SimpleNamespace(scalars=lambda query:[requested]))._available_name(uuid.uuid4(),uuid.uuid4(),requested)
    assert len(bounded)<=160 and bounded.endswith("-2.pdf")


@pytest.mark.parametrize("format",["pdf","docx"])
def test_ready_export_copies_through_workspace_service_and_remains_ready(monkeypatch,tmp_path:Path,format):
    value=job(format=format);folder=tmp_path/"user"/str(value.id);folder.mkdir(parents=True);artifact=folder/f"source.{format}";artifact.write_bytes(b"artifact");value.storage_key=artifact.relative_to(tmp_path).as_posix()
    captured={}
    class Workspace:
        def __init__(self,db):pass
        def save_export_artifact(self,access,source,filename,folder_id,provenance):
            captured.update(source=source,filename=filename,folder_id=folder_id,provenance=provenance)
            return {"id":str(uuid.uuid4()),"name":filename,"folder_id":None,"file_type":format,"size_bytes":8,"status":"pending","indexing_job_id":str(uuid.uuid4())}
    monkeypatch.setattr("backend.app.services.export_service.PersonalWorkspaceService",Workspace)
    access=SimpleNamespace(principal=SimpleNamespace(user_id=value.user_id));result=ExportService(tmp_path).save_to_workspace(object(),access,value)
    assert result["filename"].endswith(f".{format}") and result["open_url"].startswith("/knowledge/document/")
    assert captured["source"]==artifact and captured["provenance"]["export_job_id"]==str(value.id)
    assert captured["provenance"]["source_content_hash"]==value.source_content_hash and value.status=="ready" and artifact.is_file()


def test_non_ready_and_missing_artifact_return_safe_codes(tmp_path:Path):
    access=SimpleNamespace(principal=SimpleNamespace(user_id=uuid.uuid4()));service=ExportService(tmp_path)
    with pytest.raises(ExportError) as not_ready:service.save_to_workspace(object(),access,job(status="processing"))
    assert not_ready.value.code=="export_not_ready"
    with pytest.raises(ExportError) as missing:service.save_to_workspace(object(),access,job())
    assert missing.value.code=="export_artifact_missing" and str(tmp_path) not in str(missing.value)


def test_folder_outside_workspace_is_classified_without_path_details(monkeypatch,tmp_path:Path):
    value=job();artifact=tmp_path/"source.pdf";artifact.write_bytes(b"pdf");value.storage_key="source.pdf"
    class Workspace:
        def __init__(self,db):pass
        def save_export_artifact(self,*args):raise WorkspaceNotFound("secret folder path")
    monkeypatch.setattr("backend.app.services.export_service.PersonalWorkspaceService",Workspace)
    with pytest.raises(ExportError) as error:ExportService(tmp_path).save_to_workspace(object(),SimpleNamespace(principal=SimpleNamespace(user_id=value.user_id)),value,folder_id=uuid.uuid4())
    assert error.value.code=="workspace_folder_forbidden" and "secret" not in str(error.value)


class CaptureSession:
    def __init__(self,fail_flush=False):self.items=[];self.fail_flush=fail_flush;self.flushes=0;self.commits=0;self.rollbacks=0
    def add(self,item):
        if getattr(item,"id",None) is None:item.id=uuid.uuid4()
        self.items.append(item)
    def flush(self):
        self.flushes+=1
        if self.fail_flush:raise RuntimeError("database failed")
    def commit(self):self.commits+=1
    def rollback(self):self.rollbacks+=1
    def scalar(self,query):return uuid.uuid4()
    def scalars(self,query):return []
    def get(self,model,key):return SimpleNamespace(id=key,department_id=uuid.uuid4())


def workspace_fixture(service,user_id):
    workspace=SimpleNamespace(id=uuid.uuid4(),owner_user_id=user_id);folder=SimpleNamespace(id=uuid.uuid4(),system_key="personal_uploads",document_count=0)
    service.get_or_create=lambda access:workspace;service._ensure_system_folder=lambda *args:folder;service._used_bytes=lambda *args:0
    return workspace,folder


def test_saved_document_version_index_job_and_provenance_are_personal(monkeypatch,tmp_path:Path):
    from backend.app.core.config import settings
    session=CaptureSession();service=PersonalWorkspaceService(session);user_id=uuid.uuid4();organization_id=uuid.uuid4();workspace,folder=workspace_fixture(service,user_id)
    monkeypatch.setattr(settings,"workspace_root",str(tmp_path/"workspace"));source=tmp_path/"export.pdf";source.write_bytes(b"%PDF-export")
    access=SimpleNamespace(principal=SimpleNamespace(is_authenticated=True,user_id=user_id,organization_id=organization_id));provenance={"export_job_id":str(uuid.uuid4()),"source_content_hash":"hash"}
    payload=service.save_export_artifact(access,source,"airport-checklist.pdf",None,provenance)
    document=next(item for item in session.items if isinstance(item,Document));version=next(item for item in session.items if isinstance(item,DocumentVersion));indexing=next(item for item in session.items if isinstance(item,IndexingJob));audit=next(item for item in session.items if isinstance(item,AuditEvent))
    assert document.workspace_id==workspace.id and document.folder_id==folder.id and document.owner_user_id==user_id
    assert document.storage_scope=="personal" and document.visibility=="private" and document.source_type=="system_import"
    assert document.metadata_["source_export"]==provenance and version.storage_key==document.relative_path and document.current_version_id==version.id
    assert indexing.document_id==document.id and indexing.status=="pending" and indexing.metadata_["storage_scope"]=="personal"
    assert audit.action=="export_saved_to_workspace" and payload["indexing_job_id"]==str(indexing.id) and session.commits==1


def test_storage_is_cleaned_when_metadata_creation_fails(monkeypatch,tmp_path:Path):
    from backend.app.core.config import settings
    session=CaptureSession(fail_flush=True);service=PersonalWorkspaceService(session);user_id=uuid.uuid4();workspace_fixture(service,user_id)
    root=tmp_path/"workspace";monkeypatch.setattr(settings,"workspace_root",str(root));source=tmp_path/"export.pdf";source.write_bytes(b"%PDF-export")
    access=SimpleNamespace(principal=SimpleNamespace(is_authenticated=True,user_id=user_id,organization_id=uuid.uuid4()))
    with pytest.raises(RuntimeError):service.save_export_artifact(access,source,"report.pdf",None,{})
    assert session.rollbacks==1 and not [path for path in root.rglob("*") if path.is_file()]


def test_chat_attachment_creates_one_personal_document_version_and_job(monkeypatch,tmp_path:Path):
    from backend.app.core.config import settings
    session=CaptureSession();service=PersonalWorkspaceService(session);user_id=uuid.uuid4();organization_id=uuid.uuid4();workspace,folder=workspace_fixture(service,user_id)
    folder.system_key="chat_uploads";captured=[]
    service._ensure_system_folder=lambda workspace,key,name:(captured.append((key,name)) or folder)
    monkeypatch.setattr(settings,"workspace_root",str(tmp_path/"workspace"))
    access=SimpleNamespace(principal=SimpleNamespace(is_authenticated=True,user_id=user_id,organization_id=organization_id))
    chat_session_id=uuid.uuid4()
    payload=service.upload(access,"brief.txt",__import__('io').BytesIO(b"unique chat attachment"),
        metadata={"chat_session_id":str(chat_session_id)},source_type="chat_upload",
        audit_action="chat.attachment.uploaded",system_folder_key="chat_uploads")
    documents=[item for item in session.items if isinstance(item,Document)]
    versions=[item for item in session.items if isinstance(item,DocumentVersion)]
    jobs=[item for item in session.items if isinstance(item,IndexingJob)]
    assert len(documents)==len(versions)==len(jobs)==1
    assert captured==[("chat_uploads","Chat Uploads")]
    assert documents[0].source_type=="chat_upload" and documents[0].metadata_["chat_session_id"]==str(chat_session_id)
    assert jobs[0].document_version_id==versions[0].id and payload["id"]==str(documents[0].id)


def test_cross_user_export_lookup_is_denied(monkeypatch):
    import backend.app.api.routes.exports as routes
    user_id=uuid.uuid4();request=SimpleNamespace()
    monkeypatch.setattr(routes,"require_authenticated_access_context",lambda request:SimpleNamespace(principal=SimpleNamespace(user_id=user_id)))
    monkeypatch.setattr(routes,"ExportRepository",lambda db:SimpleNamespace(get_for_user=lambda export_id,owner_id:None))
    with pytest.raises(HTTPException) as error:routes._owned(uuid.uuid4(),request,object())
    assert error.value.status_code==404 and error.value.detail["code"]=="export_not_found"

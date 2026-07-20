from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import uuid

import pytest

from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.operations import AuditEvent, IndexingJob
from backend.app.security.access import AccessPrincipal, RequestAccessContext
from backend.app.services.indexing_retry_service import IndexingRetryError, IndexingRetryService


def access(user_id=None, permissions=(), scope="hybrid"):
    user_id = user_id or uuid.uuid4()
    return RequestAccessContext(principal=AccessPrincipal(user_id=user_id, is_authenticated=True,
        permission_names=frozenset(permissions)), scope=scope)


def rows(root: Path, *, storage_scope="personal", status="failed", content=b"retry source"):
    user_id = uuid.uuid4(); relative = "org/user/personal_uploads/retry.txt"
    artifact = root / relative; artifact.parent.mkdir(parents=True, exist_ok=True); artifact.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest(); now = datetime.now(timezone.utc)
    document = Document(id=uuid.uuid4(), organization_id=uuid.uuid4(), department_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        repository_id=f"personal:{user_id}" if storage_scope == "personal" else "enterprise-primary",
        storage_scope=storage_scope, owner_user_id=user_id if storage_scope == "personal" else None,
        name="retry.txt", relative_path=relative, file_type="txt", extension=".txt", mime_type="text/plain",
        visibility="private" if storage_scope == "personal" else "enterprise", size_bytes=len(content), content_hash=digest,
        indexed=False, indexing_status=status, lifecycle_status=status, source_type="user_upload" if storage_scope == "personal" else "corpus_sync",
        metadata_={"indexing_error_code":"RuntimeError","indexing_safe_message":"Preparation failed. You can retry this file.","indexing_retry_allowed":True})
    version = DocumentVersion(id=uuid.uuid4(), document_id=document.id, repository_id=document.repository_id,
        version_number=1, storage_key=relative, content_hash=digest, size_bytes=len(content), mime_type="text/plain",
        status=status, created_at=now)
    document.current_version_id = version.id
    job = IndexingJob(id=uuid.uuid4(), document_id=document.id, document_version_id=version.id, content_hash=digest,
        repository_id=document.repository_id, status="failed", attempts=3, started_at=now, completed_at=now,
        error_detail="RuntimeError", message="Indexing failed.", metadata_={"action":"added","stage":"embedding"})
    return user_id, artifact, document, version, job


class Session:
    def __init__(self, scalars, versions=()):
        self.values=list(scalars); self.versions={item.id:item for item in versions}; self.added=[]; self.commits=0
    def scalar(self, statement): return self.values.pop(0)
    def get(self, model, identity): return self.versions.get(identity)
    def add(self, item): self.added.append(item)
    def flush(self):
        for item in self.added:
            if getattr(item,"id",None) is None: item.id=uuid.uuid4()
    def commit(self): self.commits+=1


def configure_root(monkeypatch, root: Path, storage_scope="personal"):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "workspace_root", str(root))
    monkeypatch.setattr(settings, "corpus_root", str(root))


def test_failed_personal_file_retries_same_version_and_preserves_history(monkeypatch, tmp_path: Path):
    configure_root(monkeypatch,tmp_path);user_id,_,document,version,job=rows(tmp_path)
    session=Session([document,None,job],versions=[version])
    result=IndexingRetryService(session).retry(document.id,access(user_id))
    assert result.job is job and document.current_version_id==version.id
    assert document.indexing_status==version.status==job.status=="pending" and job.attempts==0
    assert job.metadata_["failure_history"][0]["error_code"]=="RuntimeError"
    assert len([item for item in session.added if isinstance(item,AuditEvent)])==1 and session.commits==1


def test_failed_enterprise_file_requires_write_permission(monkeypatch,tmp_path:Path):
    configure_root(monkeypatch,tmp_path);_,_,document,version,job=rows(tmp_path,storage_scope="enterprise")
    denied=Session([document],versions=[version])
    with pytest.raises(IndexingRetryError) as error:IndexingRetryService(denied).retry(document.id,access())
    assert error.value.status_code==404
    allowed=Session([document,None,job],versions=[version])
    result=IndexingRetryService(allowed).retry(document.id,access(permissions={"upload_enterprise_documents"}))
    assert result.job.status=="pending"


def test_cross_user_personal_retry_is_denied_by_scoped_lookup(monkeypatch,tmp_path:Path):
    configure_root(monkeypatch,tmp_path);session=Session([None])
    with pytest.raises(IndexingRetryError) as error:IndexingRetryService(session).retry(uuid.uuid4(),access())
    assert error.value.status_code==404 and error.value.code=="document_not_found"


@pytest.mark.parametrize("state",["indexed","deleted"])
def test_nonfailed_file_is_not_retryable(monkeypatch,tmp_path:Path,state):
    configure_root(monkeypatch,tmp_path);user_id,_,document,version,_=rows(tmp_path,status=state)
    session=Session([document,None],versions=[version])
    with pytest.raises(IndexingRetryError) as error:IndexingRetryService(session).retry(document.id,access(user_id))
    assert error.value.code=="indexing_not_failed"


def test_duplicate_retry_reuses_the_only_active_job(monkeypatch,tmp_path:Path):
    configure_root(monkeypatch,tmp_path);user_id,_,document,version,job=rows(tmp_path,status="pending");job.status="pending"
    result=IndexingRetryService(Session([document,job],versions=[version])).retry(document.id,access(user_id))
    assert result.deduplicated is True and result.job is job


def test_changed_artifact_creates_one_new_version_and_job(monkeypatch,tmp_path:Path):
    configure_root(monkeypatch,tmp_path);user_id,artifact,document,version,_=rows(tmp_path)
    artifact.write_bytes(b"changed source bytes")
    session=Session([document,None,1],versions=[version])
    result=IndexingRetryService(session).retry(document.id,access(user_id))
    versions=[item for item in session.added if isinstance(item,DocumentVersion)]
    jobs=[item for item in session.added if isinstance(item,IndexingJob)]
    assert len(versions)==len(jobs)==1 and result.job is jobs[0]
    assert document.current_version_id==versions[0].id and version.status=="archived"


def test_missing_and_path_escape_artifacts_return_safe_errors(monkeypatch,tmp_path:Path):
    configure_root(monkeypatch,tmp_path);user_id,artifact,document,version,job=rows(tmp_path);artifact.unlink()
    with pytest.raises(IndexingRetryError) as missing:IndexingRetryService(Session([document,None],versions=[version])).retry(document.id,access(user_id))
    assert missing.value.code=="indexing_artifact_missing" and str(tmp_path) not in str(missing.value)
    outside=tmp_path.parent/"outside-retry.txt";outside.write_text("outside");version.storage_key="../outside-retry.txt"
    try:
        with pytest.raises(IndexingRetryError) as escaped:IndexingRetryService(Session([document,None],versions=[version])).retry(document.id,access(user_id))
        assert escaped.value.code=="indexing_retry_not_allowed" and str(outside) not in str(escaped.value)
    finally: outside.unlink(missing_ok=True)

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid
import importlib

import numpy as np
import pytest
from langchain_core.documents import Document as LangchainDocument

from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.operations import IndexingJob
from backend.app.services.chunk_metadata_contract import build_chunk_metadata, validate_chunk_metadata
from backend.app.services.indexing_worker import IndexingMetadataInvalid, IndexingWorker
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


def model_rows(*, personal=True, folder=True):
    now=datetime.now(timezone.utc);owner=uuid.uuid4() if personal else None
    document=Document(id=uuid.uuid4(),organization_id=uuid.uuid4(),department_id=uuid.uuid4(),workspace_id=uuid.uuid4(),
        folder_id=uuid.uuid4() if folder else None,repository_id=f"personal:{owner}" if personal else "enterprise-primary",
        storage_scope="personal" if personal else "enterprise",owner_user_id=owner,name="target.txt",relative_path="org/user/uploads/target.txt" if personal else "target.txt",
        file_type="txt",extension=".txt",mime_type="text/plain",visibility="private" if personal else "enterprise",
        size_bytes=12,content_hash="a"*64,indexed=False,indexing_status="indexing",lifecycle_status="indexing",source_type="user_upload" if personal else "corpus_sync")
    version=DocumentVersion(id=uuid.uuid4(),document_id=document.id,repository_id=document.repository_id,version_number=1,
        storage_key=document.relative_path,content_hash=document.content_hash,size_bytes=12,mime_type="text/plain",status="indexing",created_at=now)
    document.current_version_id=version.id
    return document,version


def test_personal_authorization_payload_is_complete_and_canonical():
    document,version=model_rows(personal=True)
    payload=build_chunk_metadata(document,version)
    assert validate_chunk_metadata(payload).valid
    assert payload["storage_scope"]=="personal" and payload["visibility"]=="private"
    assert payload["owner_user_id"]==str(document.owner_user_id)
    assert payload["document_id"]==str(document.id) and payload["document_version_id"]==str(version.id)
    assert payload["workspace_id"]==str(document.workspace_id) and payload["repository_id"]==document.repository_id


def test_legacy_personal_row_gets_deterministic_owner_repository_identity():
    document,version=model_rows(personal=True);document.repository_id=None;version.repository_id=None
    payload=build_chunk_metadata(document,version)
    assert payload["repository_id"]==f"personal:{document.owner_user_id}"
    assert validate_chunk_metadata(payload).valid


def test_enterprise_null_owner_and_folder_are_allowed_but_keys_remain_present():
    document,version=model_rows(personal=False,folder=False)
    payload=build_chunk_metadata(document,version);validation=validate_chunk_metadata(payload)
    assert validation.valid and payload["owner_user_id"] is None and payload["folder_id"] is None


def test_authorization_metadata_survives_chunk_to_qdrant_payload(tmp_path:Path):
    from cial_knowledge_os.config import KnowledgeOSConfig
    from cial_knowledge_os.vectorstore import create_qdrant_client,ensure_collection,index_chunks,load_document_chunks
    document,version=model_rows();metadata=build_chunk_metadata(document,version);metadata.update({"source":"target.txt","chunk_id":"target:1","chunk_index":0})
    chunk=LangchainDocument(page_content="payload survival",metadata=metadata)
    config=KnowledgeOSConfig(project_root=tmp_path,qdrant_mode="embedded",qdrant_dir=tmp_path/"qdrant",qdrant_collection_name="payload_contract")
    client=create_qdrant_client(config)
    try:
        ensure_collection(client,config,3)
        index_chunks(client,[chunk],np.ones((1,3),dtype=np.float32),config)
        records=load_document_chunks(client,config,document_id=str(document.id),document_version_id=str(version.id))
        assert len(records)==1 and records[0][1].metadata==metadata
        assert validate_chunk_metadata(records[0][1].metadata).valid
    finally:client.close()


class DeleteQuery:
    def filter(self,*args):return self
    def delete(self,**kwargs):return 0


class PersistSession:
    def __init__(self):self.added=[]
    def query(self,*args):return DeleteQuery()
    def add(self,item):self.added.append(item)


def worker_for(pipeline):
    return IndexingWorker(engine=SimpleNamespace(_pipeline=pipeline),runtime_state=SimpleNamespace())


def job_for(document,version):
    return IndexingJob(id=uuid.uuid4(),document_id=document.id,document_version_id=version.id,status="running",
        attempts=1,started_at=datetime.now(timezone.utc),metadata_={"action":"modified"})


def test_verification_scopes_qdrant_to_target_and_ignores_unrelated_legacy(monkeypatch):
    document,version=model_rows();metadata=build_chunk_metadata(document,version);metadata["chunk_id"]="target:1"
    target=LangchainDocument(page_content="target",metadata=metadata)
    legacy=LangchainDocument(page_content="legacy",metadata={"document_id":"legacy","chunk_id":"old"})
    pipeline=SimpleNamespace(client=object(),config=object(),chunks=[legacy,target],
        bm25_retriever=SimpleNamespace(_chunks=[{"text":"legacy","metadata":legacy.metadata},{"text":"target","metadata":metadata}]))
    calls=[]
    vectorstore=importlib.import_module("cial_knowledge_os.vectorstore")
    monkeypatch.setattr(vectorstore,"load_document_chunks",lambda client,config,**filters:(calls.append(filters) or [("point-target",target)]))
    session=PersistSession();worker_for(pipeline)._persist_and_verify(session,job_for(document,version))
    assert calls==[{"document_id":str(document.id),"document_version_id":str(version.id)}]
    assert len(session.added)==1 and session.added[0].document_version_id==version.id


def test_target_metadata_failure_is_classified_with_exact_fields(monkeypatch,caplog):
    document,version=model_rows();metadata=build_chunk_metadata(document,version);metadata.pop("workspace_id");metadata["chunk_id"]="target:1"
    target=LangchainDocument(page_content="target",metadata=metadata)
    pipeline=SimpleNamespace(client=object(),config=object(),chunks=[target],bm25_retriever=SimpleNamespace(_chunks=[{"text":"target","metadata":metadata}]))
    vectorstore=importlib.import_module("cial_knowledge_os.vectorstore")
    monkeypatch.setattr(vectorstore,"load_document_chunks",lambda *args,**kwargs:[("point-target",target)])
    with pytest.raises(IndexingMetadataInvalid):worker_for(pipeline)._persist_and_verify(PersistSession(),job_for(document,version))
    assert "index_target_metadata_invalid" in caplog.text
    assert any(getattr(record,"affected_points",None)==[{"point_id":"point-target","missing":["workspace_id"],"invalid":[]}] for record in caplog.records)


class MetadataSession:
    def __init__(self,document,version):self.document=document;self.version=version
    def __enter__(self):return self
    def __exit__(self,*args):return None
    def get(self,model,identity):return self.document if model is Document else self.version


def test_targeted_indexing_reuses_models_client_and_processes_one_artifact(monkeypatch,tmp_path:Path):
    from backend.app.core.config import settings
    document,version=model_rows();artifact=tmp_path/document.relative_path;artifact.parent.mkdir(parents=True);artifact.write_text("unique target content")
    monkeypatch.setattr(settings,"workspace_root",str(tmp_path))
    config=SimpleNamespace(chunk_size=80,chunk_overlap=10,embedding_batch_size=2,bm25_k1=1.5,bm25_b=.75,
        bm25_cache_dir=tmp_path/"bm25",bm25_cache_filename="index.pkl",rrf_k=60,dense_weight=1.0,bm25_weight=1.0,
        dense_top_k=5,bm25_top_k=5,parallel_retrieval=False,document_manifest_path=tmp_path/"manifest.json",
        knowledge_root=tmp_path,qdrant_collection_name="test",repository_id=None)
    embedding_model=object();client=object();dense=SimpleNamespace(name="dense")
    unrelated=LangchainDocument(page_content="stable",metadata={"document_id":str(uuid.uuid4()),"chunk_id":"stable:1","relative_path":"stable.txt"})
    pipeline=SimpleNamespace(is_ready_for_answering=True,config=config,embedding_model=embedding_model,client=client,
        chunks=[unrelated],documents=[],embeddings=None,bm25_retriever=SimpleNamespace(allowed_relative_paths=None),
        _retrievers={"dense":dense},hybrid_retriever=None,execution_manager=None,
        _ensure_retrievers=lambda:None,_dense_search=lambda query,top_k:[])
    service=KnowledgeEngineService();service.set_pipeline(pipeline)
    monkeypatch.setattr("backend.app.services.knowledge_engine_service.SessionLocal",lambda:MetadataSession(document,version))
    loaders=importlib.import_module("cial_knowledge_os.loaders");embeddings_module=importlib.import_module("cial_knowledge_os.embeddings")
    vectorstore=importlib.import_module("cial_knowledge_os.vectorstore");incremental=importlib.import_module("cial_knowledge_os.incremental_index")
    monkeypatch.setattr(loaders,"load_pdf_paths",lambda paths,**kwargs:[LangchainDocument(page_content="unique target content",metadata={"source":str(paths[0]),"file_name":"target.txt","relative_path":document.relative_path})])
    encoded=[]
    monkeypatch.setattr(embeddings_module,"embed_texts",lambda model,texts,**kwargs:(encoded.append((model,list(texts))) or np.ones((len(texts),3),dtype=np.float32)))
    replaced=[]
    monkeypatch.setattr(vectorstore,"replace_document_chunks",lambda qclient,chunks,embeddings,cfg,**kwargs:(replaced.append((qclient,chunks,kwargs)) or 0))
    manifests=[]
    monkeypatch.setattr(incremental,"update_manifest_entry",lambda **kwargs:manifests.append(kwargs))
    result=service.prepare_document_version(document.id,version.id)
    assert result["documents_indexed"]==1 and encoded==[(embedding_model,["unique target content"])]
    assert replaced[0][0] is client and replaced[0][2]["document_id"]==str(document.id)
    assert {chunk.metadata["document_id"] for chunk in pipeline.chunks}=={unrelated.metadata["document_id"],str(document.id)}
    assert len(manifests)==1 and service._pipeline is pipeline and service._retired_pipelines==[]


def test_deterministic_metadata_and_oom_failures_do_not_auto_retry():
    assert IndexingWorker._is_transient(IndexingMetadataInvalid("bad")) is False
    oom=RuntimeError("CUDA out of memory")
    assert IndexingWorker._error_code(oom)=="resource_exhausted" and IndexingWorker._is_transient(oom) is False


def test_broad_refresh_injects_loaded_models_and_bounds_retired_snapshots(monkeypatch):
    service=KnowledgeEngineService();embedding=object();reranker=SimpleNamespace(load=lambda:None);llm=object()
    active=SimpleNamespace(embedding_model=embedding,reranker=reranker,llm=llm,is_ready_for_answering=True,close=lambda:None)
    service.set_pipeline(active);captured=[]
    class Candidate:
        def __init__(self,config,**shared):
            captured.append(shared);self.config=config;self.embedding_model=shared.get("embedding_model");self.reranker=shared.get("reranker");self.llm=shared.get("llm")
            self.client=object();self.documents=[];self.chunks=[];self.indexing_plan=None;self.is_ready_for_answering=True
        def load(self):return []
        def chunk(self):return []
        def embed(self):return np.empty((0,3))
        def index(self):return self.client
        def close(self):self.client=None
    monkeypatch.setattr(service,"_phase4_pipeline_cls",Candidate)
    monkeypatch.setattr(service,"build_config",lambda **kwargs:SimpleNamespace(qdrant_mode="embedded",force_rebuild_index=False,incremental_indexing_enabled=True,force_reindex_paths=()))
    monkeypatch.setattr("backend.app.services.knowledge_engine_service._server_collection_requires_rebuild",lambda config:False)
    service.prepare_pipeline(force_rebuild_index=False)
    service.prepare_pipeline(force_rebuild_index=False)
    assert all(item=={"embedding_model":embedding,"llm":llm,"reranker":reranker} for item in captured)
    assert len(service._retired_pipelines)==1

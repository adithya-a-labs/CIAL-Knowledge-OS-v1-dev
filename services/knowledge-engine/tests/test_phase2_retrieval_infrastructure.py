from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
import time

import numpy as np
import torch

from backend.app.security.access import AccessPrincipal, RequestAccessContext
from backend.app.services.knowledge_engine_service import (
    KnowledgeEngineService,
    SelectedContextScope,
)
from cial_knowledge_os.citations import build_citations
from cial_knowledge_os.config import KnowledgeOSConfig
from cial_knowledge_os.embeddings import resolve_embedding_device
from cial_knowledge_os.retrieval import search_similar_chunks
from cial_knowledge_os.retrieval_cache import RetrievalResultCache


class _EmbeddingModel:
    device = "cuda:0"

    def parameters(self):
        yield torch.zeros(1, dtype=torch.float32)


def _candidate(identifier: str) -> dict:
    return {
        "id": identifier,
        "score": 0.75,
        "text": f"evidence {identifier}",
        "source": "manual.pdf",
        "page_number": 4,
        "chunk_id": identifier,
        "metadata": {
            "document_id": "document-1",
            "document_version_id": "version-1",
            "relative_path": "workspace/manual.pdf",
            "file_name": "manual.pdf",
            "page_number": 4,
            "chunk_id": identifier,
        },
    }


def test_query_embedding_and_filtered_qdrant_telemetry(monkeypatch, tmp_path):
    events = []
    captured = {}

    def query_points(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    id="chunk-1",
                    score=0.9,
                    payload={
                        "text": "grounded evidence",
                        "metadata": {
                            "relative_path": "workspace/manual.pdf",
                            "document_version_id": "version-1",
                            "file_name": "manual.pdf",
                            "chunk_id": "chunk-1",
                        },
                    },
                )
            ]
        )

    retrieval_module = import_module("cial_knowledge_os.retrieval")
    monkeypatch.setattr(
        retrieval_module,
        "embed_texts",
        lambda model, texts: np.ones((1, 3), dtype=np.float32),
    )
    results = search_similar_chunks(
        SimpleNamespace(query_points=query_points),
        "Where is the manual?",
        _EmbeddingModel(),
        KnowledgeOSConfig(project_root=tmp_path),
        allowed_relative_paths={"workspace/manual.pdf"},
        allowed_document_version_ids={"version-1"},
        telemetry_callback=lambda stage, status, metrics: events.append(
            (stage, status, metrics)
        ),
        query_embedding_model_state="warmed",
        qdrant_index_status="ready",
    )

    assert [item["chunk_id"] for item in results] == ["chunk-1"]
    assert captured["query_filter"] is not None
    embedding = next(
        metrics
        for stage, status, metrics in events
        if stage == "query_embedding" and status == "completed"
    )
    assert embedding["query_embedding_completed"] is True
    assert embedding["query_embedding_device"] == "cuda:0"
    assert embedding["query_embedding_dtype"] == "torch.float32"
    assert embedding["query_embedding_model_state"] == "warmed"
    assert embedding["query_embedding_cache_status"] == "model_reused"
    assert embedding["query_embedding_duration_ms"] >= 0
    qdrant = next(
        metrics
        for stage, status, metrics in events
        if stage == "qdrant_search" and status == "completed"
    )
    assert qdrant["qdrant_index_status"] == "ready"
    assert qdrant["qdrant_filter_latency_ms"] is None
    assert qdrant["qdrant_search_latency_ms"] >= 0
    assert set(qdrant["qdrant_filter_fields"]) == {
        "metadata.relative_path",
        "metadata.document_version_id",
    }


def test_query_embedding_auto_uses_cuda_when_available(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    assert resolve_embedding_device("auto") == "cuda:0"


def test_query_embedding_auto_falls_back_only_when_cuda_unavailable(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_embedding_device("auto") == "cpu"


def test_retrieval_cache_hit_miss_and_generation_invalidation():
    cache = RetrievalResultCache(max_entries=2)
    cache.activate_generation(7)
    assert cache.lookup("key")["hit"] is False

    payload = {
        "results": [_candidate("chunk-1"), _candidate("chunk-2")],
        "rankings": {"fused": [_candidate("chunk-1"), _candidate("chunk-2")]},
    }
    cache.store(
        "key",
        payload,
        generation=7,
        principal_id="user-1",
        permission_boundary="permissions-a",
    )
    lookup_started = time.perf_counter()
    hit = cache.lookup("key")
    cache_latency_ms = (time.perf_counter() - lookup_started) * 1000
    assert hit["hit"] is True
    assert [item["chunk_id"] for item in hit["results"]] == [
        "chunk-1",
        "chunk-2",
    ]
    assert hit["generation"] == 7
    assert hit["created_at"]
    assert cache_latency_ms < 500

    cache.activate_generation(8)
    miss = cache.lookup("key")
    assert miss["hit"] is False
    assert miss["invalidation_reason"] == "published_generation_changed"


def test_retrieval_cache_permission_invalidation_and_citation_preservation():
    cache = RetrievalResultCache()
    cache.activate_generation(3)
    candidates = [_candidate("chunk-1"), _candidate("chunk-2")]
    original_citations = build_citations(candidates)
    cache.observe_permission_boundary("user-1", "permissions-a")
    cache.store(
        "key-a",
        {"results": candidates, "rankings": {"fused": candidates}},
        generation=3,
        principal_id="user-1",
        permission_boundary="permissions-a",
    )

    assert cache.observe_permission_boundary("user-1", "permissions-b") is True
    miss = cache.lookup("key-a")
    assert miss["hit"] is False
    assert miss["invalidation_reason"] == "permission_boundary_changed"

    cache.store(
        "key-b",
        {"results": candidates, "rankings": {"fused": candidates}},
        generation=3,
        principal_id="user-1",
        permission_boundary="permissions-b",
    )
    cached_candidates = cache.lookup("key-b")["results"]
    assert build_citations(cached_candidates) == original_citations


def test_cache_identity_changes_with_workspace_and_permission_boundaries():
    selected = SelectedContextScope(False, frozenset())
    base = RequestAccessContext(
        principal=AccessPrincipal(
            user_id=None,
            permission_names=frozenset({"view_enterprise_documents"}),
        ),
        scope="enterprise",
    )
    changed_permission = RequestAccessContext(
        principal=AccessPrincipal(
            user_id=None,
            permission_names=frozenset({"manage_enterprise_documents"}),
        ),
        scope="enterprise",
    )
    first = KnowledgeEngineService._retrieval_cache_identity(
        "  Same   Query ",
        generation=5,
        access_context=base,
        selected_scope=selected,
        effective_relative_paths=frozenset({"a.pdf"}),
    )
    normalized = KnowledgeEngineService._retrieval_cache_identity(
        "same query",
        generation=5,
        access_context=base,
        selected_scope=selected,
        effective_relative_paths=frozenset({"a.pdf"}),
    )
    different_workspace = KnowledgeEngineService._retrieval_cache_identity(
        "same query",
        generation=5,
        access_context=base,
        selected_scope=selected,
        effective_relative_paths=frozenset({"b.pdf"}),
    )
    different_permission = KnowledgeEngineService._retrieval_cache_identity(
        "same query",
        generation=5,
        access_context=changed_permission,
        selected_scope=selected,
        effective_relative_paths=frozenset({"a.pdf"}),
    )

    assert first[0] == normalized[0]
    assert first[0] != different_workspace[0]
    assert first[0] != different_permission[0]

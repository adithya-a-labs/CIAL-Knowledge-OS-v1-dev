from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from cial_knowledge_os.config import Phase4Config
from cial_knowledge_os.llm import GenerationFailedError
from cial_knowledge_os.phase3_pipeline import Phase3RAGPipeline
from cial_knowledge_os.phase4_pipeline import Phase4RAGPipeline
from cial_knowledge_os.retrieval import search_similar_chunks


def test_generation_discovery_is_scheduled_without_blocking_chat(monkeypatch):
    engine = KnowledgeEngineService()
    entered = Event()
    release = Event()

    def slow_refresh():
        entered.set()
        release.wait(1)
        return False

    monkeypatch.setattr(engine, "refresh_query_runtime_if_needed", slow_refresh)
    started = time.perf_counter()
    engine.request_generation_refresh()

    assert time.perf_counter() - started < 0.1
    assert entered.wait(0.5)
    assert engine.chat_debug_snapshot()["generation_refresh_running"] is True
    release.set()


def test_query_path_does_not_read_indexing_queue_or_wait_for_generation():
    source = (
        __import__(
            "backend.app.services.knowledge_engine_service",
            fromlist=["KnowledgeEngineService"],
        )
        .__file__
    )
    text = open(source, encoding="utf-8").read()
    answer_body = text.split("def answer_question(", 1)[1].split(
        "def rebuild_index(", 1
    )[0]

    assert "request_generation_refresh()" in answer_body
    assert "refresh_query_runtime_if_needed()" not in answer_body
    assert "DurableIndexQueue" not in answer_body
    assert ".sleep(" not in answer_body


class _SlowReranker:
    device = "cpu"

    def rerank(self, question, candidates):
        time.sleep(0.05)
        return SimpleNamespace(candidates=tuple(candidates), latency_seconds=0.05)


def test_reranker_timeout_is_controlled(monkeypatch, tmp_path):
    config = Phase4Config(
        project_root=tmp_path,
        reranker_timeout_seconds=0.01,
        reranker_candidate_top_k=2,
    )
    pipeline = Phase4RAGPipeline(config=config, reranker=_SlowReranker())
    candidate = {
        "text": "bounded evidence",
        "metadata": {"relative_path": "public/example.txt"},
    }
    monkeypatch.setattr(
        Phase3RAGPipeline,
        "retrieve",
        lambda self, question: [candidate],
    )

    with pytest.raises(TimeoutError, match="Reranking exceeded"):
        pipeline.retrieve("question")


class _SlowStream:
    def stream(self, prompt):
        time.sleep(0.03)
        yield "late"


def test_generation_timeout_is_controlled(tmp_path):
    config = Phase4Config(
        project_root=tmp_path,
        generation_timeout_seconds=0.01,
        generation_retries=0,
    )
    pipeline = Phase4RAGPipeline(config=config, llm=_SlowStream())
    pipeline.token_callback = lambda token: None

    with pytest.raises(GenerationFailedError, match="configured time limit"):
        pipeline._generate_grounded_answer("question", "evidence")


def test_chat_debug_snapshot_never_exposes_prompt_or_document_content():
    engine = KnowledgeEngineService()
    snapshot = engine.chat_debug_snapshot()

    assert snapshot["current_index_generation"] == 0
    assert "question" not in snapshot
    assert "documents" not in snapshot


@pytest.mark.parametrize(
    ("generation", "expected"),
    [
        (None, False),
        (
            SimpleNamespace(
                generation=0,
                published_at=datetime.now(timezone.utc),
                qdrant_collection="cial_phase4",
            ),
            False,
        ),
        (
            SimpleNamespace(
                generation=7,
                published_at=None,
                qdrant_collection="cial_phase4",
            ),
            False,
        ),
        (
            SimpleNamespace(
                generation=7,
                published_at=datetime.now(timezone.utc),
                qdrant_collection="other",
            ),
            False,
        ),
        (
            SimpleNamespace(
                generation=6,
                published_at=datetime.now(timezone.utc),
                qdrant_collection="cial_phase4",
            ),
            True,
        ),
    ],
)
def test_only_valid_published_generation_is_queryable(generation, expected):
    assert (
        KnowledgeEngineService._published_generation_valid(
            generation, "cial_phase4"
        )
        is expected
    )


def test_pending_and_failed_jobs_do_not_change_generation_validity():
    published = SimpleNamespace(
        generation=4,
        published_at=datetime.now(timezone.utc),
        qdrant_collection="cial_phase4",
    )

    for indexing_job_status in ("pending", "embedding", "retry_wait", "failed"):
        assert indexing_job_status  # job state is intentionally not an input
        assert KnowledgeEngineService._published_generation_valid(
            published, "cial_phase4"
        )


def test_dense_query_is_pinned_to_published_asset_versions(monkeypatch):
    captured = {}
    client = SimpleNamespace(
        query_points=lambda **kwargs: (
            captured.update(kwargs)
            or SimpleNamespace(points=[])
        )
    )
    config = SimpleNamespace(
        top_k=5,
        repository_id=None,
        qdrant_collection_name="cial_phase4",
        qdrant_query_timeout_seconds=3,
        qdrant_query_retry_attempts=1,
        qdrant_retry_backoff_seconds=0,
    )
    monkeypatch.setattr(
        "cial_knowledge_os.retrieval.embed_texts",
        lambda model, texts: np.ones((1, 3), dtype=np.float32),
    )

    search_similar_chunks(
        client,
        "question",
        SimpleNamespace(),
        config,
        allowed_relative_paths={"public/a.pdf"},
        allowed_document_version_ids={"version-1"},
        allowed_note_revisions={("note-1", 4)},
    )

    must = captured["query_filter"].must
    version_filter, path_filter = must
    assert len(version_filter.should) == 2
    assert version_filter.should[0].match.value == "version-1"
    assert version_filter.should[1].must[0].match.value == "note-1"
    assert version_filter.should[1].must[1].match.value == 4
    assert path_filter.should[0].match.value == "public/a.pdf"
    assert captured["timeout"] == 3

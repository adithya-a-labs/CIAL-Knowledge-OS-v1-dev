from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from threading import Event, Lock, RLock
from types import SimpleNamespace

import numpy as np
import pytest

from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from cial_knowledge_os.config import Phase4Config
from cial_knowledge_os.llm import GenerationFailedError
from cial_knowledge_os.phase3_pipeline import Phase3RAGPipeline
from cial_knowledge_os.phase4_pipeline import Phase4RAGPipeline
from cial_knowledge_os.retrieval import search_similar_chunks
from backend.app.schemas.chat import ChatRequest
from backend.app.services.knowledge_engine_service import SelectedContextScope


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
    assert answer_body.index("refresh_published_query_identities()") < answer_body.index(
        "snapshot_context = self.acquire_snapshot()"
    )
    assert answer_body.index("snapshot_context = self.acquire_snapshot()") < answer_body.index(
        "self.request_generation_refresh()"
    )
    assert "refresh_query_runtime_if_needed()" not in answer_body
    assert "DurableIndexQueue" not in answer_body
    assert ".sleep(" not in answer_body
    assert "pipeline.run(" not in answer_body
    assert "_answer_loaded_pipeline(" in answer_body


def test_publication_refresh_defers_heavy_work_while_query_reader_is_active():
    service = KnowledgeEngineService.__new__(KnowledgeEngineService)
    service._lock = RLock()
    service._active_query_readers = 1
    service._pending_publication_activation = False

    assert service.refresh_query_runtime_if_needed() is False
    assert service._pending_publication_activation is True


def test_corpus_scale_bm25_hot_reload_is_deferred_until_controlled_restart(
    monkeypatch,
    tmp_path,
):
    import backend.app.services.knowledge_engine_service as engine_module
    import cial_knowledge_os.bm25_snapshot as snapshot_module

    snapshot_path = tmp_path / "large-current.json"
    snapshot_path.write_bytes(b"oversized")
    generation = SimpleNamespace(
        generation=12,
        bm25_generation=9,
        bm25_snapshot_path=str(snapshot_path),
    )

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args):
            return generation

        def scalars(self, *args):
            return [uuid.UUID("81f02834-f2ac-4a6f-968a-d5df19e19c44")]

        def execute(self, *args):
            return [(uuid.UUID("80a074aa-3af4-47ae-a468-e39ac88a41a1"), 3)]

    activated = []
    service = KnowledgeEngineService.__new__(KnowledgeEngineService)
    service._lock = RLock()
    service._generation_refresh_lock = Lock()
    service._active_query_readers = 0
    service._pending_publication_activation = False
    service._pipeline = SimpleNamespace(
        published_document_version_ids=frozenset({"old-version"}),
        published_note_revisions=frozenset({("old-note", 1)}),
    )
    service._loaded_generation = 11
    service._loaded_bm25_generation = 8
    service._retrieval_cache = SimpleNamespace(
        activate_generation=lambda value: activated.append(value)
    )
    service._bm25_snapshot_metrics = {"bm25_runtime_state": "ready"}
    service._published_generation_valid = lambda *args: True

    monkeypatch.setattr(engine_module, "SessionLocal", Session)
    monkeypatch.setattr(engine_module.settings, "bm25_hot_reload_max_bytes", 1)
    monkeypatch.setattr(
        snapshot_module,
        "load_bm25_snapshot",
        lambda *args: pytest.fail("oversized snapshot must not load in-process"),
    )

    assert service.refresh_query_runtime_if_needed() is True
    assert service._loaded_generation == 12
    assert service._loaded_bm25_generation == 8
    assert activated == [12]
    assert service._pipeline.published_document_version_ids == frozenset(
        {"81f02834-f2ac-4a6f-968a-d5df19e19c44"}
    )
    assert service._pipeline.published_note_revisions == frozenset(
        {("80a074aa-3af4-47ae-a468-e39ac88a41a1", 3)}
    )
    assert service._bm25_snapshot_metrics["bm25_runtime_state"] == (
        "deferred_until_restart"
    )
    assert service._bm25_snapshot_metrics["bm25_pending_generation"] == 9


def test_published_query_runtime_never_enters_batch_bootstrap():
    calls = []

    class PublishedPipeline:
        def answer(self, question):
            calls.append(("answer", question))
            return {"answer": "grounded"}

        def run(self, question):
            raise AssertionError("batch bootstrap must not run during chat")

    result = KnowledgeEngineService._answer_loaded_pipeline(
        PublishedPipeline(),
        "question",
    )

    assert result == {"answer": "grounded"}
    assert calls == [("answer", "question")]


def test_query_runtime_warms_reranker_before_serving_queries():
    calls = []
    pipeline = SimpleNamespace(
        config=SimpleNamespace(reranker_enabled=True),
        reranker=SimpleNamespace(load=lambda: calls.append("load")),
    )

    KnowledgeEngineService._load_reranker(pipeline)

    assert calls == ["load"]


def test_production_query_never_rebuilds_missing_bm25_snapshot(tmp_path):
    class Retriever:
        def __init__(self, name, *, indexed=True):
            self.name = name
            self.is_indexed = indexed

        def retrieve(self, query, *, top_k):
            return []

        def index(self, chunks):
            raise AssertionError("query-time BM25 rebuild is prohibited")

    pipeline = Phase3RAGPipeline(
        config=Phase4Config(
            project_root=tmp_path,
            require_authorization_metadata=True,
        ),
        retrievers={
            "dense": Retriever("dense"),
            "bm25": Retriever("bm25", indexed=False),
        },
    )

    with pytest.raises(RuntimeError, match="Query-time snapshot rebuilding"):
        pipeline._search("question")


def test_actual_answer_path_enriches_retrieval_stage_telemetry(monkeypatch):
    service = KnowledgeEngineService()
    events = []
    conversation_id = __import__("uuid").uuid4()

    class Pipeline:
        is_ready_for_answering = True
        config = SimpleNamespace()
        token_callback = None
        cancel_event = None
        telemetry_callback = None

        def answer(self, question):
            self.telemetry_callback("generation", "started", {})
            time.sleep(0.005)
            self.telemetry_callback(
                "generation",
                "completed",
                {
                    "duration_ms": 1_758_803,
                    "first_token_ms": 1_758_803,
                    "model_load_ms": -1,
                    "tokens_per_second": float("inf"),
                },
            )
            self.telemetry_callback("dense_retrieval", "started", {})
            self.telemetry_callback(
                "dense_retrieval",
                "completed",
                {
                    "duration_ms": 7,
                    "candidate_count": 2,
                    "error_state": None,
                },
            )
            return {
                "retrieved": [],
                "selected_evidence": [],
                "citations": [],
            }

    pipeline = Pipeline()
    monkeypatch.setattr(service, "request_generation_refresh", lambda: None)
    monkeypatch.setattr(service, "_ready_pipeline", lambda *args, **kwargs: pipeline)
    monkeypatch.setattr(
        service,
        "_resolve_selected_context",
        lambda *args, **kwargs: SelectedContextScope(
            applied=False,
            allowed_relative_paths=frozenset(),
        ),
    )
    monkeypatch.setattr(
        service,
        "_accessible_relative_paths",
        lambda *args, **kwargs: None,
    )
    result = SimpleNamespace(citations=[])
    monkeypatch.setattr(
        service,
        "_to_chat_response",
        lambda *args, **kwargs: result,
    )

    returned = service.answer_question(
        ChatRequest(
            session_id=conversation_id,
            question="question",
        ),
        progress_callback=lambda stage, status, metrics: events.append(
            (stage, status, metrics)
        ),
        request_id="request-1",
    )

    assert returned is result
    dense_completed = next(
        metrics
        for stage, status, metrics in events
        if stage == "dense_retrieval" and status == "completed"
    )
    assert dense_completed["request_id"] == "request-1"
    assert dense_completed["conversation_id"] == str(conversation_id)
    assert dense_completed["stage"] == "dense_retrieval"
    assert dense_completed["status"] == "completed"
    assert dense_completed["duration_ms"] == 7
    assert dense_completed["candidate_count"] == 2
    assert dense_completed["error_state"] is None
    assert dense_completed["timeout_state"] == "not_timed_out"
    assert dense_completed["timestamp"].endswith("+00:00")
    generation_completed = next(
        metrics
        for stage, status, metrics in events
        if stage == "generation" and status == "completed"
    )
    assert 5 <= generation_completed["duration_ms"] < 1_000
    assert generation_completed["first_token_ms"] is None
    assert generation_completed["model_load_ms"] is None
    assert generation_completed["tokens_per_second"] is None


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

    selected = pipeline.retrieve("question")

    assert selected
    assert pipeline.last_reranked_candidates[0]["text"] == "bounded evidence"
    telemetry = pipeline.last_retrieval_telemetry["reranking"]
    assert telemetry["stage_started"] is True
    assert telemetry["stage_completed"] is True
    assert telemetry["candidate_count"] == 1
    assert telemetry["error_state"] == "timeout"
    assert telemetry["duration_ms"] >= 10


class _SlowEvidenceSelector:
    def select(self, candidates):
        time.sleep(0.05)
        raise AssertionError("late selector result must be ignored")


def test_evidence_selection_timeout_returns_safe_empty_selection(
    monkeypatch,
    tmp_path,
):
    config = Phase4Config(
        project_root=tmp_path,
        reranker_enabled=False,
        evidence_selection_timeout_seconds=0.01,
        reranker_candidate_top_k=2,
    )
    pipeline = Phase4RAGPipeline(
        config=config,
        evidence_selector=_SlowEvidenceSelector(),
    )
    candidate = {
        "text": "bounded evidence",
        "score": 0.9,
        "metadata": {"relative_path": "public/example.txt"},
    }
    monkeypatch.setattr(
        Phase3RAGPipeline,
        "retrieve",
        lambda self, question: [candidate],
    )

    selected = pipeline.retrieve("question")

    assert selected == []
    assert pipeline.last_discarded_chunks[0]["discard_reason"] == (
        "evidence_selection_timeout"
    )
    telemetry = pipeline.last_retrieval_telemetry["evidence_selection"]
    assert telemetry["error_state"] == "timeout"
    assert telemetry["stage_completed"] is True


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
    events = []
    pipeline.telemetry_callback = (
        lambda stage, status, metrics: events.append((stage, status, metrics))
    )

    with pytest.raises(GenerationFailedError, match="configured time limit"):
        pipeline._generate_grounded_answer("question", "evidence")
    failed = next(
        metrics
        for stage, status, metrics in events
        if stage == "generation" and status == "failed"
    )
    assert failed["error_state"] == "generation_timeout"
    assert failed["prompt_tokens"] >= failed["context_tokens"]


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
    assert version_filter.should[0].match.any == ["version-1"]
    assert version_filter.should[1].must[0].match.value == "note-1"
    assert version_filter.should[1].must[1].match.value == 4
    assert path_filter.should[0].match.any == ["public/a.pdf"]
    assert captured["timeout"] == 3

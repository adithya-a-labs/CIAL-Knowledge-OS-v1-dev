from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

from backend.app.services.knowledge_engine_service import KnowledgeEngineService


class _RequestPipeline:
    def __init__(
        self,
        config,
        *,
        embedding_model,
        llm,
        query_transformer,
        tokenizer,
        retrievers,
        reranker,
    ) -> None:
        self.config = config
        self.embedding_model = embedding_model
        self.llm = llm
        self.query_transformer = query_transformer
        self._provided_tokenizer = tokenizer
        self.bm25_retriever = (retrievers or {}).get("bm25")
        self.reranker = reranker
        self.token_callback = None
        self.cancel_event = None
        self.telemetry_callback = None


def _base_pipeline() -> _RequestPipeline:
    lexical = SimpleNamespace(
        allowed_relative_paths={"published/base.pdf"},
        last_search_metrics={"old": True},
        _authorized_lock=RLock(),
        _authorized_indexes={"shared": object()},
    )
    pipeline = _RequestPipeline(
        SimpleNamespace(answer_profile="base"),
        embedding_model=object(),
        llm=object(),
        query_transformer=object(),
        tokenizer=object(),
        retrievers={"bm25": lexical},
        reranker=object(),
    )
    pipeline.client = object()
    pipeline.documents = [object()]
    pipeline.chunks = [object()]
    pipeline.embeddings = object()
    pipeline.published_document_version_ids = frozenset({"version-1"})
    pipeline.published_note_revisions = {"note-1": 2}
    return pipeline


def test_request_pipeline_clones_mutable_state_and_shares_heavy_resources() -> None:
    service = KnowledgeEngineService.__new__(KnowledgeEngineService)
    service._phase4_pipeline_cls = _RequestPipeline

    def apply_profile(config, response_length, *, profile, max_answer_words):
        config.answer_profile = profile or response_length
        config.max_answer_words = max_answer_words

    service._apply_response_profile = apply_profile
    base = _base_pipeline()

    concise = service._request_pipeline(
        base,
        "concise",
        profile=None,
        max_answer_words=120,
    )
    detailed = service._request_pipeline(
        base,
        "detailed",
        profile="technical",
        max_answer_words=800,
    )

    assert concise is not detailed
    assert concise.config is not detailed.config
    assert concise.config.answer_profile == "concise"
    assert detailed.config.answer_profile == "technical"
    assert base.config.answer_profile == "base"
    assert concise.bm25_retriever is not detailed.bm25_retriever
    assert concise.bm25_retriever is not base.bm25_retriever
    assert concise.bm25_retriever.allowed_relative_paths is None
    assert detailed.bm25_retriever.allowed_relative_paths is None
    assert concise.bm25_retriever.last_search_metrics == {}
    assert concise.embedding_model is base.embedding_model
    assert concise.llm is base.llm
    assert concise.reranker is base.reranker
    assert concise.client is base.client
    assert concise.documents is base.documents
    assert concise.chunks is base.chunks

    concise.token_callback = object()
    concise.bm25_retriever.allowed_relative_paths = {"only/a.pdf"}
    assert detailed.token_callback is None
    assert detailed.bm25_retriever.allowed_relative_paths is None
    assert base.bm25_retriever.allowed_relative_paths == {"published/base.pdf"}


def test_publication_reader_lease_keeps_snapshot_stable_across_atomic_swap() -> None:
    service = KnowledgeEngineService.__new__(KnowledgeEngineService)
    service._query_lock = RLock()
    service._lock = RLock()
    service._pipeline = None
    service._retired_pipelines = []
    service._active_query_readers = 0
    service._pending_publication_activation = False
    service._loaded_generation = 7
    service._loaded_bm25_generation = 6
    refreshes: list[bool] = []
    service.request_generation_refresh = lambda: refreshes.append(True)
    first = SimpleNamespace(
        is_ready_for_answering=True,
        config=SimpleNamespace(qdrant_collection_name="generation-7"),
    )
    second = SimpleNamespace(
        is_ready_for_answering=True,
        config=SimpleNamespace(qdrant_collection_name="generation-8"),
    )
    service.set_pipeline(first)

    lease = service.acquire_snapshot()
    snapshot = lease.__enter__()
    try:
        assert snapshot.pipeline is first
        assert service.publication_reader_snapshot()[
            "active_query_runtime_reader_count"
        ] == 1
        service.set_pipeline(second)
        assert snapshot.pipeline is first
        assert service._pipeline is second
        service._pending_publication_activation = True
    finally:
        lease.__exit__(None, None, None)

    readers = service.publication_reader_snapshot()
    assert readers["active_query_runtime_reader_count"] == 0
    assert readers["pending_publication_activation"] is False
    assert refreshes == [True]

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import time
import uuid

import numpy as np

from backend.app.api.routes.indexing import router as indexing_router
from backend.app.core.runtime_state import RuntimeState
from backend.app.models.knowledge import DocumentChunk
from backend.app.models.operations import IndexGeneration, IndexerWorker, IndexingJob
from backend.app.services.continuous_indexer import (
    AdaptiveBatchController,
    ClaimedTarget,
    ChunkEnvelope,
    ContinuousIndexer,
    CrossDocumentBatcher,
)
from backend.app.services.indexing_queue import (
    ACTIVE_JOB_STATUSES,
    STAGE_TRANSITIONS,
)
from backend.app.services.knowledge_engine_service import KnowledgeEngineService
from backend.app.services.startup_service import StartupService
from cial_knowledge_os.bm25_snapshot import load_bm25_snapshot, write_bm25_snapshot
from cial_knowledge_os.retrievers import BM25Retriever
from cial_knowledge_os.retrieval import search_similar_chunks


def envelope(asset_id: uuid.UUID, text: str) -> ChunkEnvelope:
    return ChunkEnvelope(
        job_id=uuid.uuid4(),
        asset_id=asset_id,
        chunk=SimpleNamespace(page_content=text),
        token_count=CrossDocumentBatcher.estimate_tokens(text),
    )


def test_cross_document_batch_contains_multiple_assets() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    batcher = CrossDocumentBatcher(max_chunks=3, max_tokens=1000, max_wait_ms=50)
    assert batcher.add(envelope(first, "a" * 20)) is None
    assert batcher.add(envelope(first, "b" * 20)) is None
    batch = batcher.add(envelope(second, "c" * 20))
    assert batch is not None
    assert {item.asset_id for item in batch} == {first, second}


def test_batch_flushes_before_token_limit_is_exceeded() -> None:
    batcher = CrossDocumentBatcher(max_chunks=100, max_tokens=5, max_wait_ms=50)
    first = envelope(uuid.uuid4(), "a" * 16)
    second = envelope(uuid.uuid4(), "b" * 16)
    assert batcher.add(first) is None
    batch = batcher.add(second)
    assert batch == [first]
    assert batcher.flush() == [second]


def test_batch_time_deadline_is_observable() -> None:
    batcher = CrossDocumentBatcher(max_chunks=10, max_tokens=100, max_wait_ms=10)
    batcher.add(envelope(uuid.uuid4(), "text"), now=5.0)
    assert not batcher.due(now=5.005)
    assert batcher.due(now=5.011)


def test_adaptive_batch_grows_on_healthy_full_batches_and_shrinks_on_oom() -> None:
    controller = AdaptiveBatchController(
        minimum=64,
        current=64,
        maximum=256,
        latency_tolerance=1.15,
        vram_target_ratio=0.85,
    )
    assert controller.record_success(
        batch_size=64,
        duration_seconds=1,
        vram_ratio=0.5,
    ) == 128
    assert controller.record_success(
        batch_size=128,
        duration_seconds=2,
        vram_ratio=0.7,
    ) == 256
    assert controller.record_oom(attempted_batch_size=256) == 128
    assert controller.oom_count == 1


def test_qdrant_writer_is_a_dedicated_bounded_stage() -> None:
    indexer = ContinuousIndexer(engine=MagicMock())
    try:
        assert indexer._writer_pool._max_workers == 1
        assert indexer._write_futures == set()
    finally:
        indexer._writer_pool.shutdown(wait=True)


def test_ocr_assets_are_routed_away_from_the_normal_extraction_pool() -> None:
    base = {
        "job_id": uuid.uuid4(),
        "asset_type": "document",
        "operation": "upsert_version",
        "document_id": uuid.uuid4(),
        "document_version_id": uuid.uuid4(),
        "note_id": None,
        "note_version_id": None,
    }
    assert ContinuousIndexer._is_ocr_target(
        ClaimedTarget(**base, metadata={"relative_path": "scans/page.TIFF"})
    )
    assert not ContinuousIndexer._is_ocr_target(
        ClaimedTarget(**base, metadata={"relative_path": "manuals/runbook.pdf"})
    )


def test_indexer_status_service_alias_preserves_existing_endpoint() -> None:
    paths = {route.path for route in indexing_router.routes}
    assert {"/index/status", "/indexer/status"}.issubset(paths)


def test_atomic_bm25_snapshot_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "bm25" / "current.json"
    write_bm25_snapshot(
        path,
        generation=7,
        chunks=[{"text": "private text", "metadata": {"owner_user_id": "u1"}}],
    )
    snapshot = load_bm25_snapshot(path)
    assert snapshot is not None
    assert snapshot.generation == 7
    assert snapshot.chunks[0]["metadata"]["owner_user_id"] == "u1"
    assert not list(path.parent.glob("*.tmp"))


def test_queue_model_has_target_lease_and_retry_contract() -> None:
    expected = {
        "asset_type",
        "operation",
        "document_id",
        "document_version_id",
        "note_id",
        "note_version_id",
        "priority",
        "available_at",
        "attempts",
        "max_attempts",
        "claimed_by",
        "lease_expires_at",
        "heartbeat_at",
        "error_code",
    }
    assert expected.issubset(IndexingJob.__table__.columns.keys())
    assert {"claimed", "extracting", "embedding", "writing", "verifying", "retry_wait"}.issubset(
        ACTIVE_JOB_STATUSES
    )
    assert "embedding" in STAGE_TRANSITIONS["chunked"]


def test_worker_and_generation_control_tables_are_declared() -> None:
    assert IndexerWorker.__tablename__ == "indexer_workers"
    assert IndexGeneration.__tablename__ == "index_generations"


def test_api_startup_never_invokes_indexing_pipeline() -> None:
    engine = MagicMock()
    engine.engine_available = True
    engine.build_config.return_value = SimpleNamespace()
    engine.check_ollama_model.return_value = (True, "ready")
    engine.prepare_query_runtime.return_value = {
        "retrieval_ready": True,
        "message": "loaded",
    }
    runtime = RuntimeState()
    service = StartupService(engine=engine, runtime_state=runtime)
    service.validate_corpus_root = MagicMock()
    service.ensure_required_folders = MagicMock()
    with (
        patch(
            "backend.app.services.startup_service.check_database_health",
            return_value=SimpleNamespace(database_ready=False),
        ),
        patch.object(service, "check_qdrant", return_value=(True, "ready")),
    ):
        service.run_startup()
    engine.prepare_query_runtime.assert_called_once_with()
    engine.prepare_pipeline.assert_not_called()
    assert runtime.api_ready is True
    assert runtime.retrieval_ready is True


def test_fastapi_composition_root_does_not_own_indexer_worker() -> None:
    source = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "IndexingWorker" not in source
    assert "CorpusWatcher" not in source
    assert "indexing_worker.start()" not in source


def test_indexer_entrypoint_exists_and_is_separate() -> None:
    source = Path("backend/indexer_main.py").read_text(encoding="utf-8")
    assert "ContinuousIndexer" in source
    assert "uvicorn" not in source
    launcher = Path("../../scripts/launch_all.bat").read_text(encoding="utf-8")
    assert "Launch-CIAL-Knowledge-OS.bat" in launcher


def test_migration_extends_actual_head() -> None:
    source = Path("alembic/versions/20260724_0016_continuous_indexing.py").read_text(
        encoding="utf-8"
    )
    assert 'down_revision = "20260724_0015"' in source
    assert "uq_indexing_jobs_active_note_operation" in source
    assert "indexer_workers" in source
    assert "index_generations" in source


def test_chunk_reuse_migration_is_the_new_head() -> None:
    source = Path(
        "alembic/versions/20260725_0017_chunk_incremental_reuse.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20260724_0016"' in source
    assert {
        "chunk_hash",
        "embedding_model_version",
        "chunking_version",
    }.issubset(DocumentChunk.__table__.columns.keys())


def test_chunk_hash_changes_only_when_chunk_text_changes() -> None:
    first = KnowledgeEngineService.chunk_hash("stable chunk")
    assert first == KnowledgeEngineService.chunk_hash("stable chunk")
    assert first != KnowledgeEngineService.chunk_hash("changed chunk")


def test_cuda_oom_reduces_batch_recursively() -> None:
    calls: list[int] = []

    def embed(chunks, *, batch_size):
        calls.append(len(chunks))
        if len(chunks) > 2:
            raise RuntimeError("CUDA out of memory")
        return np.ones((len(chunks), 3), dtype=np.float32)

    indexer = ContinuousIndexer.__new__(ContinuousIndexer)
    indexer.engine = SimpleNamespace(embed_chunk_batch=embed)
    batch = [envelope(uuid.uuid4(), f"chunk-{index}") for index in range(5)]
    vectors = indexer._embed_with_oom_reduction(batch)
    assert vectors.shape == (5, 3)
    assert calls[0] == 5
    assert max(calls[1:]) < 5


def test_embedding_call_uses_the_live_adaptive_batch_limit() -> None:
    observed: list[int] = []

    def embed(chunks, *, batch_size):
        observed.append(batch_size)
        return np.ones((len(chunks), 3), dtype=np.float32)

    indexer = ContinuousIndexer.__new__(ContinuousIndexer)
    indexer.engine = SimpleNamespace(embed_chunk_batch=embed)
    indexer._batch_controller = AdaptiveBatchController(
        minimum=1,
        current=128,
        maximum=256,
    )
    batch = [envelope(uuid.uuid4(), f"chunk-{index}") for index in range(100)]
    assert indexer._embed_with_oom_reduction(batch).shape == (100, 3)
    assert observed == [100]


def test_bm25_debounce_flushes_before_idle(monkeypatch) -> None:
    indexer = ContinuousIndexer.__new__(ContinuousIndexer)
    indexer._bm25_dirty_since = time.monotonic()
    indexer.publish_bm25_generation = MagicMock()
    assert indexer._flush_bm25_if_due() is False
    assert indexer._flush_bm25_if_due(force=True) is True
    indexer.publish_bm25_generation.assert_called_once_with()
    assert indexer._bm25_dirty_since is None


def test_note_replacement_uses_filtered_delete_without_scroll() -> None:
    source = Path("backend/app/services/note_indexing_service.py").read_text(
        encoding="utf-8"
    )
    assert "FilterSelector" in source
    assert ".scroll(" not in source


def test_query_runtime_has_hot_generation_reload() -> None:
    source = Path("backend/app/services/knowledge_engine_service.py").read_text(
        encoding="utf-8"
    )
    assert "refresh_query_runtime_if_needed" in source
    assert "bm25_generation_reloaded" in source


def test_empty_authorization_scope_denies_all_bm25_candidates() -> None:
    retriever = BM25Retriever()
    retriever.index(
        [
            {
                "text": "private note content",
                "metadata": {"relative_path": "notes/private"},
            }
        ]
    )
    retriever.set_allowed_relative_paths(frozenset())
    assert retriever.retrieve("private", top_k=5) == []


def test_empty_authorization_scope_denies_dense_before_embedding() -> None:
    assert search_similar_chunks(
        MagicMock(),
        "private",
        MagicMock(),
        SimpleNamespace(top_k=5, repository_id=None),
        allowed_relative_paths=frozenset(),
    ) == []

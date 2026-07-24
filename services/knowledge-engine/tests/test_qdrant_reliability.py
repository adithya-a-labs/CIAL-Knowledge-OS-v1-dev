from __future__ import annotations

import logging
from types import SimpleNamespace
import uuid

import httpx
import numpy as np
import pytest
from langchain_core.documents import Document
from qdrant_client.models import Distance, VectorParams

from backend.app.services.indexing_worker import IndexingWorker
from cial_knowledge_os.config import KnowledgeOSConfig
from cial_knowledge_os.vectorstore import (
    execute_qdrant_operation,
    replace_document_chunks,
)


def config(tmp_path, **overrides):
    values = {
        "project_root": tmp_path,
        "qdrant_mode": "server",
        "qdrant_collection_name": "reliability",
        "qdrant_retry_backoff_seconds": 2,
    }
    values.update(overrides)
    return KnowledgeOSConfig(**values)


def chunk(document_id: str, version_id: str, index: int, text: str) -> Document:
    return Document(
        page_content=text,
        metadata={
            "source": "target.txt",
            "document_id": document_id,
            "document_version_id": version_id,
            "chunk_id": f"{document_id}:{version_id}:{index}",
            "chunk_index": index,
            "page_number": index + 1,
        },
    )


def vector_client(*, before: int = 2, after: int = 1):
    client = SimpleNamespace()
    client.get_collection = lambda *args, **kwargs: SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=VectorParams(size=3, distance=Distance.COSINE)
            )
        )
    )
    counts = iter((before, after))
    client.count = lambda *args, **kwargs: SimpleNamespace(count=next(counts))
    client.delete_calls = []
    client.delete = lambda *args, **kwargs: (
        client.delete_calls.append(kwargs)
        or SimpleNamespace(status="completed")
    )
    client.upsert_calls = []
    client.upsert = lambda *args, **kwargs: (
        client.upsert_calls.append(kwargs)
        or SimpleNamespace(status="completed")
    )
    client.scroll_calls = []
    client.scroll = lambda *args, **kwargs: (
        client.scroll_calls.append(kwargs) or ([], None)
    )
    return client


def test_replacement_uses_filtered_delete_without_scroll(tmp_path, caplog):
    document_id, version_id = "document-a", "version-1"
    target = chunk(document_id, version_id, 0, "target replacement text")
    client = vector_client()
    client.retrieve = lambda *args, **kwargs: [
        SimpleNamespace(
            payload={
                "text": target.page_content,
                "metadata": dict(target.metadata),
            }
        )
    ]

    with caplog.at_level(logging.INFO):
        deleted = replace_document_chunks(
            client,
            [target],
            np.ones((1, 3), dtype=np.float32),
            config(tmp_path),
            document_id=document_id,
            document_version_id=version_id,
        )

    assert deleted == 2
    assert client.scroll_calls == []
    selector = client.delete_calls[0]["points_selector"]
    conditions = {
        condition.key: condition.match.value
        for condition in selector.filter.must
    }
    assert conditions == {
        "metadata.document_id": document_id,
        "metadata.document_version_id": version_id,
    }
    verified = next(
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "document_chunk_replacement_verified"
    )
    assert verified.chunks_deleted == 2
    assert verified.chunks_inserted == 1


def test_filtered_delete_cannot_target_another_document(tmp_path):
    document_id, version_id = "document-a", "version-1"
    other_id = "document-b"
    target = chunk(document_id, version_id, 0, "target")
    client = vector_client(before=1, after=1)
    client.retrieve = lambda *args, **kwargs: [
        SimpleNamespace(payload={"metadata": dict(target.metadata)})
    ]

    replace_document_chunks(
        client,
        [target],
        np.ones((1, 3), dtype=np.float32),
        config(tmp_path),
        document_id=document_id,
        document_version_id=version_id,
    )

    selector = client.delete_calls[0]["points_selector"]
    values = {condition.match.value for condition in selector.filter.must}
    assert document_id in values
    assert version_id in values
    assert other_id not in values


def test_transient_timeout_retries_with_exponential_backoff(tmp_path, caplog):
    attempts, delays = [], []

    def operation(timeout):
        attempts.append(timeout)
        if len(attempts) < 3:
            raise httpx.ReadTimeout("temporary")
        return "recovered"

    with caplog.at_level(logging.INFO):
        result = execute_qdrant_operation(
            config(tmp_path),
            "query_points",
            operation,
            sleep_fn=delays.append,
        )

    assert result == "recovered"
    assert attempts == [30, 30, 30]
    assert delays == [2, 4]
    retries = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "qdrant_operation_retry"
    ]
    assert [record.attempt for record in retries] == [2, 3]


def test_permanent_failure_is_not_retried(tmp_path):
    attempts, delays = [], []

    def operation(timeout):
        attempts.append(timeout)
        raise ValueError("invalid payload")

    with pytest.raises(ValueError, match="invalid payload"):
        execute_qdrant_operation(
            config(tmp_path),
            "upsert",
            operation,
            sleep_fn=delays.append,
        )
    assert attempts == [60]
    assert delays == []


def test_timeout_and_retry_configuration_comes_from_environment(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("QDRANT_TIMEOUT_SECONDS", "41")
    monkeypatch.setenv("QDRANT_RETRY_ATTEMPTS", "4")
    monkeypatch.setenv("QDRANT_RETRY_BACKOFF_SECONDS", "1.5")
    monkeypatch.setenv("QDRANT_HEALTH_TIMEOUT_SECONDS", "6")
    monkeypatch.setenv("QDRANT_QUERY_TIMEOUT_SECONDS", "31")
    monkeypatch.setenv("QDRANT_UPSERT_TIMEOUT_SECONDS", "61")
    monkeypatch.setenv("QDRANT_DELETE_TIMEOUT_SECONDS", "62")
    monkeypatch.setenv("QDRANT_COLLECTION_TIMEOUT_SECONDS", "121")

    resolved = KnowledgeOSConfig(project_root=tmp_path)

    assert resolved.qdrant_timeout_seconds == 41
    assert resolved.qdrant_retry_attempts == 4
    assert resolved.qdrant_retry_backoff_seconds == 1.5
    assert resolved.qdrant_health_timeout_seconds == 6
    assert resolved.qdrant_query_timeout_seconds == 31
    assert resolved.qdrant_upsert_timeout_seconds == 61
    assert resolved.qdrant_delete_timeout_seconds == 62
    assert resolved.qdrant_collection_timeout_seconds == 121


def test_replacement_verification_rejects_wrong_count(tmp_path):
    client = vector_client(before=2, after=0)
    target = chunk("document-a", "version-1", 0, "target")
    client.retrieve = lambda *args, **kwargs: []

    with pytest.raises(RuntimeError, match="expected 1 points, found 0"):
        replace_document_chunks(
            client,
            [target],
            np.ones((1, 3), dtype=np.float32),
            config(tmp_path),
            document_id="document-a",
            document_version_id="version-1",
        )


def test_index_worker_classifies_only_transient_qdrant_failures_for_retry():
    timeout = httpx.ReadTimeout("temporary")
    permanent = ValueError("invalid payload")

    assert IndexingWorker._error_code(timeout) == "temporary_qdrant_failure"
    assert IndexingWorker._is_transient(timeout) is True
    assert IndexingWorker._is_transient(permanent) is False


def test_index_worker_reschedules_temporary_qdrant_failure(
    monkeypatch, caplog
):
    from backend.app.models.operations import IndexingJob
    from backend.app.services import indexing_worker as worker_module

    job_id = uuid.uuid4()
    job = SimpleNamespace(
        id=job_id,
        status="running",
        attempts=1,
        metadata_={},
        document_id=None,
        document_version_id=None,
        message="",
        error_detail=None,
        updated_at=None,
        completed_at=None,
    )

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, model, identity):
            return job if model is IndexingJob and identity == job_id else None

        def commit(self):
            return None

    engine = SimpleNamespace(
        prepare_pipeline=lambda **kwargs: (_ for _ in ()).throw(
            httpx.ReadTimeout("temporary")
        ),
        is_ready=lambda: False,
    )
    runtime = SimpleNamespace()
    worker = IndexingWorker(engine=engine, runtime_state=runtime)
    monkeypatch.setattr(worker_module, "SessionLocal", lambda: Session())
    monkeypatch.setattr(worker_module, "sleep", lambda seconds: None)

    with caplog.at_level(logging.INFO):
        worker._process_claimed_job(job_id)

    assert job.status == "pending"
    assert job.completed_at is None
    assert job.error_detail == "temporary_qdrant_failure"
    assert any(
        getattr(record, "event", None) == "temporary_qdrant_failure"
        and record.retry_scheduled is True
        for record in caplog.records
    )


def test_qdrant_logs_do_not_contain_embeddings_or_document_text(
    tmp_path, caplog
):
    secret_text = "private document sentence that must not be logged"
    secret_embedding = "[0.123456789, 0.987654321]"

    with caplog.at_level(logging.INFO):
        execute_qdrant_operation(
            config(tmp_path),
            "upsert",
            lambda timeout: SimpleNamespace(status="completed"),
            affected_count=1,
        )

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_text not in rendered
    assert secret_embedding not in rendered
    assert "qdrant_operation_started" in rendered
    assert "qdrant_operation_completed" in rendered

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import health
from backend.app.core.config import settings
from backend.app.db.health import DatabaseHealth
from backend.app.security import session_tokens
from backend.app.services.system_status_service import SystemStatusService


class _Runtime:
    def snapshot(self):
        return {
            "engine_ready": True,
            "models_ready": True,
            "qdrant_ready": True,
            "latest_index_generation": 7,
            "bm25_generation": 4,
        }


class _Engine:
    @staticmethod
    def is_ready():
        return True

    @staticmethod
    def runtime_diagnostics():
        return {"embedding_ready": True, "embedding_device": "cpu"}


class _Queue:
    def __init__(self, *, depth=0, worker_seen=True, worker_state="watching"):
        self.depth = depth
        self.worker_seen = worker_seen
        self.worker_state = worker_state

    def status(self):
        return {
            "queue_counts": {"queued": self.depth},
            "queue_depth": self.depth,
            "active_jobs": ([{"job_id": "job-1", "status": "queued"}] if self.depth else []),
            "indexer_seen": self.worker_seen,
            "indexer_state": self.worker_state,
            "worker_heartbeat_at": "2026-07-25T09:00:00+00:00",
            "latest_index_generation": 7,
            "bm25_generation": 4,
            "generation_published_at": "2026-07-25T08:55:00+00:00",
            "qdrant_point_count": 42,
            "last_successful_index_at": "2026-07-25T08:55:00+00:00",
            "embedding_device": "cpu",
            "gpu_metrics": {},
        }


def _service(monkeypatch, *, depth=0, worker_seen=True, worker_state="watching"):
    monkeypatch.setattr(
        "backend.app.services.system_status_service.check_database_health",
        lambda: DatabaseHealth(True, True, "Metadata database is available."),
    )
    service = SystemStatusService(
        runtime_state=_Runtime(),
        engine=_Engine(),
        indexing_service=SimpleNamespace(
            queue=_Queue(depth=depth, worker_seen=worker_seen, worker_state=worker_state)
        ),
    )
    monkeypatch.setattr(
        service,
        "_probe_qdrant",
        lambda checked_at: service._component(
            available=True,
            detail="Qdrant is available.",
            checked_at=checked_at,
            latency_ms=1,
        ),
    )
    monkeypatch.setattr(
        service,
        "_probe_ollama",
        lambda checked_at: service._component(
            available=True,
            detail="Ollama model is available.",
            checked_at=checked_at,
            latency_ms=1,
        ),
    )
    return service


def test_system_status_green_when_all_components_are_healthy(monkeypatch):
    payload = _service(monkeypatch).snapshot()

    assert payload["status"] == "green"
    assert payload["label"] == "System ready"
    assert payload["chat_available"] is True
    assert payload["index"]["generation"] == 7
    assert payload["components"]["postgresql"]["available"] is True
    assert payload["latency_ms"]["total"] >= 0


def test_system_status_blue_keeps_chat_available_during_indexing(monkeypatch):
    payload = _service(
        monkeypatch,
        depth=2,
        worker_seen=True,
        worker_state="active",
    ).snapshot()

    assert payload["status"] == "blue"
    assert payload["label"] == "Updating knowledge"
    assert payload["chat_available"] is True
    assert payload["indexing"]["queue_depth"] == 2


def test_system_status_yellow_for_noncritical_worker_degradation(monkeypatch):
    payload = _service(monkeypatch, worker_seen=False, worker_state="unknown").snapshot()

    assert payload["status"] == "yellow"
    assert payload["chat_available"] is True


def test_system_status_red_when_a_chat_critical_component_is_down(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(
        service,
        "_probe_qdrant",
        lambda checked_at: service._component(
            available=False,
            detail="Qdrant is unavailable.",
            checked_at=checked_at,
            latency_ms=1,
        ),
    )

    payload = service.snapshot()

    assert payload["status"] == "red"
    assert payload["label"] == "Unavailable"
    assert payload["chat_available"] is False


def test_system_status_red_when_postgresql_is_down(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(
        "backend.app.services.system_status_service.check_database_health",
        lambda: DatabaseHealth(False, True, "sensitive driver failure"),
    )

    payload = service.snapshot()

    assert payload["status"] == "red"
    assert payload["components"]["postgresql"]["available"] is False
    assert "sensitive" not in payload["components"]["postgresql"]["detail"]


def test_system_status_red_when_ollama_or_model_is_unavailable(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(
        service,
        "_probe_ollama",
        lambda checked_at: service._component(
            available=False,
            detail="Configured Ollama model is unavailable.",
            checked_at=checked_at,
            latency_ms=1,
        ),
    )

    payload = service.snapshot()

    assert payload["status"] == "red"
    assert payload["components"]["ollama"]["available"] is False


def test_system_status_red_without_a_published_generation(monkeypatch):
    service = _service(monkeypatch)
    original_status = service.indexing_service.queue.status

    def without_generation():
        return {
            **original_status(),
            "latest_index_generation": 0,
            "generation_published_at": None,
        }

    monkeypatch.setattr(service.indexing_service.queue, "status", without_generation)

    payload = service.snapshot()

    assert payload["status"] == "red"
    assert payload["components"]["published_generation"]["available"] is False


def test_active_queue_with_stale_worker_is_degraded_not_updating(monkeypatch):
    payload = _service(
        monkeypatch,
        depth=3,
        worker_seen=False,
        worker_state="unknown",
    ).snapshot()

    assert payload["status"] == "yellow"
    assert payload["indexing_active"] is True
    assert payload["chat_available"] is True


def test_system_status_route_is_authenticated(monkeypatch):
    app = FastAPI()
    app.state.system_status_service = SimpleNamespace(snapshot=lambda: {"status": "green"})
    app.include_router(health.router, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/system/status").status_code == 401

    app.dependency_overrides[health.require_system_status_access] = lambda: object()
    response = client.get("/api/system/status")
    assert response.status_code == 200
    assert response.json() == {"status": "green"}


def test_signed_session_can_observe_postgresql_outage(monkeypatch):
    test_settings = replace(
        settings,
        auth_secret_key="system-status-route-secret",
        auth_cookie_name="cial_system_status_test",
    )
    monkeypatch.setattr(session_tokens, "settings", test_settings)
    app = FastAPI()
    app.state.system_status_service = SimpleNamespace(
        snapshot=lambda: {
            "status": "red",
            "components": {"postgresql": {"available": False}},
        }
    )
    app.include_router(health.router, prefix="/api")
    client = TestClient(app)
    token = session_tokens.issue_session_token(uuid.uuid4(), ttl_seconds=60)
    client.cookies.set(test_settings.auth_cookie_name, token)

    response = client.get("/api/system/status")

    assert response.status_code == 200
    assert response.json()["components"]["postgresql"]["available"] is False

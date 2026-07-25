from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.routes import admin_system
from backend.app.security.access import AccessPrincipal, RequestAccessContext
from backend.app.services.admin_system_monitor_service import (
    AdminSystemMonitorService,
)


def _component(available=True):
    return {
        "status": "available" if available else "unavailable",
        "available": available,
        "detail": "Live component telemetry.",
        "checked_at": "2026-07-25T09:00:00+00:00",
        "latency_ms": 2,
    }


class _Status:
    def snapshot(self):
        generated_at = datetime.now(timezone.utc).isoformat()
        return {
            "status": "green",
            "label": "System ready",
            "components": {
                "backend": _component(),
                "postgresql": _component(),
                "qdrant": _component(),
                "ollama": _component() | {"loaded_models": ["llama3.1:8b"]},
            },
            "timestamps": {"generated_at": generated_at},
            "latency_ms": {"total": 7},
        }


class _Engine:
    def runtime_diagnostics(self):
        return {
            "embedding_ready": True,
            "embedding_device": "cuda:0",
            "reranker_ready": True,
        }

    def chat_debug_snapshot(self):
        return {
            "status": "completed",
            "validation_latency": 3,
            "retrieval_latency": 20,
            "reranker_latency": 8,
            "generation_latency": 40,
            "total_latency": 74,
            "last_error": None,
        }


class _Queue:
    def __init__(self, *, stale=False):
        heartbeat = datetime.now(timezone.utc)
        if stale:
            heartbeat -= timedelta(minutes=10)
        self.payload = {
            "indexer_state": "active",
            "indexer_seen": not stale,
            "worker_heartbeat_at": heartbeat.isoformat(),
            "active_workers": 1,
            "queue_counts": {
                "pending": 2,
                "embedding": 1,
                "completed": 9,
                "failed": 1,
            },
            "queue_by_operation": {"upsert_version": 3},
            "queue_depth": 3,
            "active_jobs": [
                {
                    "job_id": "job-1",
                    "asset_type": "document",
                    "operation": "upsert_version",
                    "status": "embedding",
                }
            ],
            "recent_errors": [{"job_id": "failed-1", "error_code": "qdrant"}],
            "latest_index_generation": 12,
            "bm25_generation": 12,
            "generation_published_at": "2026-07-25T08:59:00+00:00",
            "index_fresh": False,
            "embedding_device": "cuda:0",
            "embedding_precision": "float16",
            "active_batch_limit": 64,
            "throughput": {
                "documents_per_hour": 120.0,
                "chunks_per_minute": 900.0,
            },
            "internal_queue_depths": {"embedding": 20},
            "gpu_metrics": {
                "utilization_percent": 75.0,
                "memory_used_mb": 4096.0,
                "memory_total_mb": 8192.0,
            },
            "cpu_metrics": {"utilization_percent": 33.0},
        }

    def status(self):
        return self.payload


def _service(*, stale=False, queue=None):
    return AdminSystemMonitorService(
        system_status_service=_Status(),
        runtime_state=SimpleNamespace(),
        engine=_Engine(),
        indexing_service=SimpleNamespace(queue=queue or _Queue(stale=stale)),
    )


def _access(*permissions):
    return RequestAccessContext(
        principal=AccessPrincipal(
            is_authenticated=True,
            permission_names=frozenset(permissions),
        )
    )


def test_admin_monitor_snapshot_reuses_live_runtime_telemetry():
    payload = _service().snapshot()

    assert payload["status"] == "green"
    assert payload["indexing"]["queue_depth"] == 3
    assert payload["indexing"]["completed_jobs"] == 9
    assert payload["indexing"]["active_published_generation"] == 12
    assert payload["gpu"]["utilization_percent"] == 75.0
    assert payload["gpu"]["embedding_throughput_chunks_per_minute"] == 900.0
    assert payload["query"]["retrieval_latency_ms"] == 20
    assert payload["models"]["loaded_models"] == ["llama3.1:8b"]


def test_monitor_records_real_chat_activity_and_completion():
    service = _service()

    service.chat_started("request-1")
    running = service.snapshot()
    service.chat_completed("request-1", succeeded=True, latency_ms=42)
    completed = service.snapshot()

    assert running["query"]["active_chat_requests"] == 1
    assert completed["query"]["active_chat_requests"] == 0
    event_types = [event["type"] for event in completed["events"]]
    assert event_types[0] == "chat_completed"
    assert "chat_started" in event_types


def test_stale_worker_heartbeat_is_reported_without_fabricating_health():
    payload = _service(stale=True).snapshot()

    assert payload["stale"] is True
    assert payload["indexing"]["worker_stale"] is True
    assert payload["indexing"]["worker_heartbeat_age_seconds"] >= 500


def test_component_failure_degrades_only_the_failed_telemetry_source():
    class BrokenQueue:
        def status(self):
            raise RuntimeError("database password must never escape")

    payload = _service(queue=BrokenQueue()).snapshot()

    assert payload["indexing"]["queue_depth"] == 0
    assert payload["events"][0]["type"] == "service_failed"
    assert "password" not in payload["events"][0]["message"]
    assert payload["events"][0]["metadata"]["error_type"] == "RuntimeError"


def test_monitor_permission_accepts_admin_and_dedicated_monitor_grants(monkeypatch):
    for permission in ("manage_settings", "monitor_system"):
        monkeypatch.setattr(
            admin_system,
            "require_authenticated_access_context",
            lambda request, permission=permission: _access(permission),
        )
        assert admin_system.require_admin_monitor_access(object()).principal.is_authenticated


def test_authenticated_user_without_monitor_permission_receives_403(monkeypatch):
    monkeypatch.setattr(
        admin_system,
        "require_authenticated_access_context",
        lambda request: _access("view_enterprise_documents"),
    )

    try:
        admin_system.require_admin_monitor_access(object())
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected a 403 response.")


def test_monitor_endpoint_requires_authorization_and_returns_snapshot():
    app = FastAPI()
    app.state.admin_system_monitor_service = SimpleNamespace(
        snapshot=lambda: {"status": "green", "generated_at": "now"}
    )
    app.include_router(admin_system.router, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/admin/system/monitor").status_code == 401

    app.dependency_overrides[admin_system.require_admin_monitor_access] = (
        lambda: _access("manage_settings")
    )
    response = client.get("/api/admin/system/monitor")
    assert response.status_code == 200
    assert response.json()["status"] == "green"


def test_stream_endpoint_emits_sse_monitor_frames():
    class Request:
        def __init__(self):
            self.app = SimpleNamespace(
                state=SimpleNamespace(
                    admin_system_monitor_service=SimpleNamespace(
                        snapshot=lambda: {
                            "status": "green",
                            "connection_hint_seconds": 60,
                        }
                    )
                )
            )

        async def is_disconnected(self):
            return False

    async def read_first_frame():
        response = await admin_system.monitor_stream(
            Request(),
            _access("manage_settings"),
        )
        frame = await response.body_iterator.__anext__()
        await response.body_iterator.aclose()
        return response, frame

    response, frame = asyncio.run(read_first_frame())
    assert response.media_type == "text/event-stream"
    assert "event: monitor" in frame
    assert '"status":"green"' in frame

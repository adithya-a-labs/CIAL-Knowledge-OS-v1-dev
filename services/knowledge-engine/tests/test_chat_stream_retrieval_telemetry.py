from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import chat
from backend.app.schemas.chat import ChatMetadata, ChatResponse
from backend.app.security.access import AccessPrincipal, RequestAccessContext
from backend.app.services.chat_concurrency import ChatConcurrencyController


class _Database:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


class _Repository:
    def __init__(self, database):
        self.database = database

    def get_session_for_user(self, session_id, user_id):
        return None

    def add_session(self, session):
        return session

    def add_message(self, message):
        if message.id is None:
            message.id = uuid.uuid4()
        return message


class _Runtime:
    def snapshot(self):
        return {"engine_ready": True, "index_fresh": True}

    def chat_unavailable_detail(self):
        return "unavailable"


class _Engine:
    def answer_question(
        self,
        request,
        *,
        progress_callback=None,
        token_callback=None,
        **_,
    ):
        if progress_callback is not None:
            progress_callback(
                "dense_retrieval",
                "started",
                {
                    "request_id": "server-request",
                    "conversation_id": str(request.session_id)
                    if request.session_id
                    else None,
                    "stage": "dense_retrieval",
                    "status": "started",
                    "duration_ms": 0,
                    "candidate_count": 0,
                    "error_state": None,
                    "timeout_state": "not_timed_out",
                    "timestamp": "2026-07-25T00:00:00+00:00",
                },
            )
            progress_callback(
                "dense_retrieval",
                "completed",
                {
                    "request_id": "server-request",
                    "conversation_id": str(request.session_id)
                    if request.session_id
                    else None,
                    "stage": "dense_retrieval",
                    "status": "completed",
                    "duration_ms": 8,
                    "candidate_count": 2,
                    "error_state": None,
                    "timeout_state": "not_timed_out",
                    "timestamp": "2026-07-25T00:00:00+00:00",
                },
            )
        if token_callback is not None:
            token_callback("Grounded")
        return ChatResponse(
            answer="Grounded answer.",
            citations=[],
            sources=[],
            metadata=ChatMetadata(),
        )


def test_chat_stream_delivers_actual_retrieval_stage_events(monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setattr(chat, "SessionLocal", _Database)
    monkeypatch.setattr(chat, "ChatRepository", _Repository)
    monkeypatch.setattr(
        chat,
        "require_authenticated_access_context",
        lambda request: RequestAccessContext(
            principal=AccessPrincipal(
                user_id=user_id,
                is_authenticated=True,
            )
        ),
    )
    monkeypatch.setattr(
        chat.ConversationService,
        "enforce",
        staticmethod(lambda session, payload: payload),
    )

    app = FastAPI()
    app.state.runtime_state = _Runtime()
    app.state.knowledge_engine = _Engine()
    app.state.admin_system_monitor_service = None
    app.include_router(chat.router, prefix="/api")

    response = TestClient(app).post(
        "/api/chat/stream",
        json={
            "question": "What is documented?",
            "selected_document_ids": [],
        },
    )

    assert response.status_code == 200
    events = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]
    dense_events = [
        event
        for event in events
        if event.get("stage_id") == "dense_retrieval"
    ]
    assert [event["status"] for event in dense_events] == [
        "started",
        "completed",
    ]
    assert dense_events[-1]["metrics"]["candidate_count"] == 2
    assert dense_events[-1]["metrics"]["timeout_state"] == "not_timed_out"
    assert any(event["type"] == "token" for event in events)
    assert events[-1]["type"] == "result"


def _chat_client(monkeypatch, *, permissions=frozenset(), debug_enabled=False):
    user_id = uuid.uuid4()
    monkeypatch.setattr(chat, "SessionLocal", _Database)
    monkeypatch.setattr(chat, "ChatRepository", _Repository)
    monkeypatch.setattr(chat.settings, "chat_debug", debug_enabled)
    monkeypatch.setattr(
        chat,
        "require_authenticated_access_context",
        lambda request: RequestAccessContext(
            principal=AccessPrincipal(
                user_id=user_id,
                organization_id=uuid.uuid4(),
                permission_names=frozenset(permissions),
                is_authenticated=True,
            )
        ),
    )
    monkeypatch.setattr(
        chat.ConversationService,
        "enforce",
        staticmethod(lambda session, payload: payload),
    )
    controller = ChatConcurrencyController()
    controller.start()
    app = FastAPI()
    app.state.runtime_state = _Runtime()
    app.state.knowledge_engine = _Engine()
    app.state.admin_system_monitor_service = None
    app.state.chat_concurrency = controller
    app.include_router(chat.router, prefix="/api")
    return TestClient(app), controller


def _assert_chat_succeeded(path: str, response) -> None:
    assert response.status_code == 200
    if path.endswith("/stream"):
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        assert events[-1]["type"] == "result"
        assert events[-1]["payload"]["answer"] == "Grounded answer."
    else:
        assert response.json()["answer"] == "Grounded answer."


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_ordinary_viewer_chat_omits_diagnostics_and_succeeds(monkeypatch, path):
    client, controller = _chat_client(monkeypatch)
    try:
        response = client.post(path, json={"question": "What is documented?"})
    finally:
        controller.close()

    _assert_chat_succeeded(path, response)


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_explicit_diagnostics_remain_denied_to_ordinary_viewer(monkeypatch, path):
    client, controller = _chat_client(monkeypatch, debug_enabled=True)
    try:
        response = client.post(
            path,
            json={"question": "What is documented?", "include_debug": True},
        )
    finally:
        controller.close()

    assert response.status_code == 403
    assert response.json() == {"detail": "Chat diagnostics are not available."}


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_monitor_diagnostics_still_require_server_enablement(monkeypatch, path):
    client, controller = _chat_client(
        monkeypatch,
        permissions={"monitor_system"},
        debug_enabled=False,
    )
    try:
        response = client.post(
            path,
            json={"question": "What is documented?", "include_debug": True},
        )
    finally:
        controller.close()

    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_authorized_monitor_can_explicitly_request_enabled_diagnostics(monkeypatch, path):
    client, controller = _chat_client(
        monkeypatch,
        permissions={"monitor_system"},
        debug_enabled=True,
    )
    try:
        response = client.post(
            path,
            json={"question": "What is documented?", "include_debug": True},
        )
    finally:
        controller.close()

    _assert_chat_succeeded(path, response)

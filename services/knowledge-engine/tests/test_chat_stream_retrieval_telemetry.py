from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import chat
from backend.app.schemas.chat import ChatMetadata, ChatResponse
from backend.app.security.access import AccessPrincipal, RequestAccessContext


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
        return {"engine_ready": True}

    def chat_unavailable_detail(self):
        return "unavailable"


class _Engine:
    def answer_question(
        self,
        request,
        *,
        progress_callback,
        token_callback,
        **_,
    ):
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

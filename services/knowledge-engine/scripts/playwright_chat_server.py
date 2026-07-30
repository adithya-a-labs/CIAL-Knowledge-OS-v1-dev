"""Deterministic FastAPI browser fixture backed by the production chat scheduler.

This is a verification-only server. It intentionally avoids PostgreSQL,
Qdrant, and Ollama so browser concurrency tests are repeatable.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.services.chat_concurrency import (  # noqa: E402
    ChatCapacityError,
    ChatConcurrencyController,
)


settings.chat_multi_request_enabled = True
settings.chat_executor_workers = 4
settings.chat_max_active_global = 4
settings.chat_max_active_per_user = 2
settings.chat_max_queued_global = 16
settings.chat_max_queued_per_user = 8
settings.chat_query_embedding_concurrency = 1
settings.chat_retrieval_concurrency = 2
settings.chat_rerank_concurrency = 1
settings.chat_generation_concurrency = 2
settings.chat_queue_wait_timeout_seconds = 10
settings.chat_request_timeout_seconds = 30
settings.chat_event_queue_size = 32
settings.chat_token_flush_ms = 20
settings.chat_token_flush_chars = 32

controller = ChatConcurrencyController()


@asynccontextmanager
async def lifespan(_: FastAPI):
    controller.start()
    try:
        yield
    finally:
        controller.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


@app.get("/api/auth/me")
def auth_me() -> dict[str, Any]:
    return {
        "user": {
            "id": DEMO_USER_ID,
            "email": "playwright@localhost.invalid",
            "display_name": "Playwright Verifier",
            "initials": "PV",
            "organization_name": "CIAL",
            "department_name": "Verification",
            "role_names": ["viewer"],
            "permission_names": ["read_documents", "use_assistant"],
            "notifications_count": 0,
        },
        "message": "Authenticated deterministic browser fixture.",
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ready",
        "service": "deterministic-playwright-chat",
        "api_ready": True,
        "engine_ready": True,
        "retrieval_ready": True,
    }


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "status": "green",
        "label": "System ready",
        "chat_available": True,
        "indexing_active": False,
        "components": {},
        "index": {
            "generation": 1,
            "bm25_generation": 1,
            "published_at": now,
            "point_count": 2,
        },
        "indexing": {
            "worker_state": "watching",
            "worker_seen": True,
            "worker_heartbeat_at": now,
            "queue_depth": 0,
            "queue_counts": {},
            "active_jobs": [],
            "last_successful_index_at": now,
        },
        "models": {
            "ollama": "deterministic-playwright-model",
            "embedding": "deterministic",
            "embedding_device": "cpu",
            "embedding_ready": True,
        },
        "gpu": {
            "available": False,
            "requested": False,
            "device": "cpu",
            "utilization_percent": None,
            "memory_used_mb": None,
            "memory_total_mb": None,
        },
        "timestamps": {
            "generated_at": now,
            "worker_heartbeat_at": now,
            "generation_published_at": now,
            "last_successful_index_at": now,
        },
        "latency_ms": {},
    }


@app.get("/api/chat/sessions")
def chat_sessions() -> dict[str, Any]:
    return {"sessions": []}


@app.get("/api/corpus/tree")
def corpus_tree() -> dict[str, Any]:
    return {
        "root": {
            "id": None,
            "parent_id": None,
            "name": "CIAL Knowledge",
            "relative_path": "",
            "depth": 0,
            "document_count": 0,
            "subfolder_count": 0,
            "last_scanned_at": None,
            "children": [],
            "documents": [],
        },
        "folders_count": 0,
        "documents_count": 0,
    }


def _event_delay(question: str) -> float:
    if "CANCEL-ME" in question:
        return 1.5
    if "SURVIVOR" in question:
        return 0.20
    if "FIRST-SLOW" in question:
        return 0.22
    if "SECOND-FAST" in question:
        return 0.06
    return 0.10


@app.post("/api/chat/stream")
async def chat_stream(payload: dict[str, Any], request: Request):
    question = str(payload.get("question") or "").strip()
    session_id = str(payload.get("session_id") or uuid.uuid4())
    client_request_id = str(payload.get("client_request_id") or uuid.uuid4())

    def execute(record) -> None:
        record.emit(
            {
                "type": "stage",
                "stage_id": "request.validating",
                "status": "started",
            }
        )
        time.sleep(_event_delay(question))
        record.raise_if_cancelled()
        record.emit(
            {
                "type": "stage",
                "stage_id": "retrieval.searching",
                "status": "started",
            }
        )
        with controller.gate("retrieval", record):
            time.sleep(_event_delay(question))
        record.emit(
            {
                "type": "stage",
                "stage_id": "reranking",
                "status": "completed",
            }
        )
        answer = (
            f"Completed {question}. "
            "This deterministic response verifies independent request state."
        )
        with controller.gate("generation", record):
            for token in answer.split(" "):
                record.raise_if_cancelled()
                record.emit_token(token + " ")
                time.sleep(_event_delay(question))
        response = {
            "session_id": session_id,
            "user_message_id": str(uuid.uuid4()),
            "assistant_message_id": str(uuid.uuid4()),
            "answer": answer,
            "citations": [],
            "sources": [],
            "metadata": {
                "retrieval_mode": "deterministic",
                "phase": "playwright",
                "latency_ms": int(
                    (time.monotonic() - record.created_at) * 1000
                ),
                "model": "deterministic-playwright-model",
                "profile": payload.get("profile")
                or payload.get("response_length")
                or "standard",
                "retrieved_count": 0,
                "selected_evidence_count": 0,
                "index_fresh": True,
            },
            "debug": None,
        }
        record.stage = "completed"
        record.emit_terminal("result", response)

    try:
        record = controller.submit(
            user_key=DEMO_USER_ID,
            work=execute,
            client_request_id=client_request_id,
        )
    except ChatCapacityError as exc:
        return JSONResponse(
            status_code=429,
            content={"detail": exc.detail()},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    controller.cancel(record.request_id)
                    break
                try:
                    item = await asyncio.to_thread(record.events.get, 0.25)
                except TimeoutError:
                    continue
                if item is None:
                    break
                yield json.dumps(item, separators=(",", ":")) + "\n"
        finally:
            if not record.cleanup_complete:
                controller.cancel(record.request_id)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Request-ID": record.request_id},
    )


@app.get("/api/chat/debug")
def chat_debug() -> dict[str, Any]:
    return controller.snapshot()

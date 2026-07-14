"""Chat route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
import logging

from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.security.access import resolve_access_context
from backend.app.services.knowledge_engine_service import (
    KnowledgeEngineInvalidRequest,
    KnowledgeEngineUnavailable,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    runtime_state = request.app.state.runtime_state
    if not runtime_state.snapshot()["engine_ready"]:
        current = runtime_state.snapshot()
        logger.info(
            "chat_rejected_engine_not_ready",
            extra={
                "event": "chat_readiness",
                "current_status": current["status"],
                "current_stage": current["stage"],
                "ready": current["engine_ready"],
                "request_id": request.headers.get("x-request-id"),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=runtime_state.chat_unavailable_detail(),
        )
    access_context = resolve_access_context(request)
    try:
        response = request.app.state.knowledge_engine.answer_question(
            payload,
            access_context=access_context,
        )
        response.metadata.index_fresh = bool(
            runtime_state.snapshot().get("index_fresh")
        )
        return response
    except KnowledgeEngineInvalidRequest as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except KnowledgeEngineUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                **runtime_state.chat_unavailable_detail(),
                "message": str(exc),
            },
        ) from exc

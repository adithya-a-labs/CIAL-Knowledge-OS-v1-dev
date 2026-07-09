"""Chat route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.security.access import resolve_access_context
from backend.app.services.knowledge_engine_service import (
    KnowledgeEngineInvalidRequest,
    KnowledgeEngineUnavailable,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    runtime_state = request.app.state.runtime_state
    if not runtime_state.snapshot()["engine_ready"]:
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

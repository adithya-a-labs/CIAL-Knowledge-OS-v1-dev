"""Chat route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.knowledge_engine_service import KnowledgeEngineUnavailable

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    runtime_state = request.app.state.runtime_state
    if not runtime_state.snapshot()["engine_ready"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=runtime_state.chat_unavailable_detail(),
        )
    try:
        return request.app.state.knowledge_engine.answer_question(payload)
    except KnowledgeEngineUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                **runtime_state.chat_unavailable_detail(),
                "message": str(exc),
            },
        ) from exc

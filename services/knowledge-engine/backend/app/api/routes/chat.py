"""Chat route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.models.conversations import ChatMessage, ChatSession
from backend.app.repositories.chats import ChatRepository
from backend.app.schemas.chat import ChatMessageRecord, ChatRequest, ChatResponse, ChatSessionList, ChatSessionRecord, MessageExportRequest, MessageExportResponse, MessageFeedbackRequest, MessageFeedbackResponse, MessageTransformRequest
from backend.app.services.chat_action_service import ChatActionError, ChatActionService
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.knowledge_engine_service import (
    KnowledgeEngineInvalidRequest,
    KnowledgeEngineUnavailable,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _record(session: ChatSession, repository: ChatRepository) -> ChatSessionRecord:
    return ChatSessionRecord(
        id=session.id,
        title=session.title or "New conversation",
        messages=[
            ChatMessageRecord(
                id=message.id, role=message.role, content=message.content,
                citations=message.citations or [], sources=message.sources or [],
                metadata=message.metadata_ or {}, created_at=message.created_at,
                feedback=(repository.get_feedback(message.id, session.user_id).metadata_ or {}).get("categories", []) if repository.get_feedback(message.id, session.user_id) else [],
            )
            for message in repository.list_messages_for_user(session.id, session.user_id)
        ],
        created_at=session.created_at, updated_at=session.updated_at,
    )


@router.get("/chat/sessions", response_model=ChatSessionList)
def list_chat_sessions(request: Request, db: Session = Depends(get_db_session)) -> ChatSessionList:
    access = require_authenticated_access_context(request)
    repository = ChatRepository(db)
    return ChatSessionList(sessions=[_record(item, repository) for item in repository.list_sessions_for_user(access.principal.user_id)])


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionRecord)
def get_chat_session(session_id: uuid.UUID, request: Request, db: Session = Depends(get_db_session)) -> ChatSessionRecord:
    access = require_authenticated_access_context(request)
    repository = ChatRepository(db)
    item = repository.get_session_for_user(session_id, access.principal.user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return _record(item, repository)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db_session)) -> ChatResponse:
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
    access_context = require_authenticated_access_context(request)
    user_id = access_context.principal.user_id
    repository = ChatRepository(db)
    chat_session = repository.get_session_for_user(payload.session_id, user_id) if payload.session_id else None
    if payload.session_id and chat_session is None:
        # A client-generated UUID is accepted only for a new session; an id owned by
        # another user remains indistinguishable from a missing id.
        if db.get(ChatSession, payload.session_id) is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if chat_session is None:
        chat_session = repository.add_session(ChatSession(id=payload.session_id or uuid.uuid4(), user_id=user_id, title=payload.question.strip()[:72]))
    try:
        response = request.app.state.knowledge_engine.answer_question(
            payload,
            access_context=access_context,
        )
        response.metadata.index_fresh = bool(
            runtime_state.snapshot().get("index_fresh")
        )
        user_message = repository.add_message(ChatMessage(
            session_id=chat_session.id, user_id=user_id, role="user", content=payload.question,
            metadata_={"selected_document_ids": payload.selected_document_ids, "selected_folder_ids": payload.selected_folder_ids, "profile": payload.profile or payload.response_length, "response_length": payload.response_length, "max_answer_words": payload.max_answer_words},
        ))
        assistant_message = repository.add_message(ChatMessage(
            session_id=chat_session.id, user_id=user_id, role="assistant", content=response.answer,
            citations=[item.model_dump(mode="json") for item in response.citations],
            sources=[item.model_dump(mode="json") for item in response.sources],
            metadata_={**response.metadata.model_dump(mode="json"), "generation_request": payload.model_dump(mode="json", exclude={"question", "session_id", "include_debug"}), "user_message_id": str(user_message.id)},
        ))
        chat_session.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        response.session_id = chat_session.id
        response.user_message_id = user_message.id
        response.assistant_message_id = assistant_message.id
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


def _actions(request: Request, db: Session) -> ChatActionService:
    return ChatActionService(db, request.app.state.knowledge_engine, request.app.state.export_service)


@router.post("/chat/messages/{message_id}/regenerate", response_model=ChatResponse)
def regenerate_message(message_id: uuid.UUID, request: Request, db: Session = Depends(get_db_session)) -> ChatResponse:
    access = require_authenticated_access_context(request)
    try:
        return _actions(request, db).regenerate(message_id, access)
    except ChatActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/chat/messages/{message_id}/transform", response_model=ChatMessageRecord)
def transform_message(message_id: uuid.UUID, payload: MessageTransformRequest, request: Request, db: Session = Depends(get_db_session)) -> ChatMessageRecord:
    access = require_authenticated_access_context(request)
    try:
        message = _actions(request, db).transform(message_id, payload.operation, access)
        return ChatMessageRecord(id=message.id, role="assistant", content=message.content, citations=message.citations or [], sources=message.sources or [], metadata=message.metadata_ or {}, created_at=message.created_at)
    except ChatActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.put("/chat/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
def update_feedback(message_id: uuid.UUID, payload: MessageFeedbackRequest, request: Request, db: Session = Depends(get_db_session)) -> MessageFeedbackResponse:
    access = require_authenticated_access_context(request)
    try:
        return MessageFeedbackResponse(active=_actions(request, db).toggle_feedback(message_id, payload.feedback, access))
    except ChatActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/chat/messages/{message_id}/export", response_model=MessageExportResponse)
def export_message(message_id: uuid.UUID, payload: MessageExportRequest, request: Request, db: Session = Depends(get_db_session)) -> MessageExportResponse:
    access = require_authenticated_access_context(request)
    try:
        name, url = _actions(request, db).export(message_id, payload, access)
        return MessageExportResponse(filename=name, download_url=url)
    except ChatActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc

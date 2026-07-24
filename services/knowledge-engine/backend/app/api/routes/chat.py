"""Chat route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.db.session import get_db_session
from backend.app.models.conversations import ChatMessage, ChatSession
from backend.app.models.knowledge import Document
from backend.app.models.workspace_content import Note, SummaryConversationBinding
from backend.app.repositories.chats import ChatRepository
from backend.app.schemas.chat import ChatAttachmentResponse, ChatMessageRecord, ChatRequest, ChatResponse, ChatSessionCreate, ChatSessionList, ChatSessionRecord, MessageFeedbackRequest, MessageFeedbackResponse, MessageTransformRequest
from backend.app.services.chat_action_service import ChatActionError, ChatActionService
from backend.app.services.message_transformation_service import MessageTransformationError, MessageTransformationService
from backend.app.security.access import require_authenticated_access_context
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound
from backend.app.services.knowledge_engine_service import (
    KnowledgeEngineDocumentsNotReady,
    KnowledgeEngineInvalidRequest,
    KnowledgeEngineUnavailable,
)
from backend.app.services.conversation_service import ConversationService

router = APIRouter()
logger = logging.getLogger(__name__)


class _StreamCancelled(RuntimeError):
    pass


def _apply_summary_binding(payload: ChatRequest, db: Session, user_id: uuid.UUID) -> ChatRequest:
    if payload.session_id is None: return payload
    binding=db.query(SummaryConversationBinding).filter(SummaryConversationBinding.chat_session_id==payload.session_id,SummaryConversationBinding.owner_user_id==user_id).one_or_none()
    if binding is None: return payload
    document_ids=[];note_ids=[]
    for source in binding.source_binding:
        source_type=source.get("source_type");source_id=source.get("source_id")
        if source_type=="document" and source_id:
            document=db.get(Document,uuid.UUID(source_id))
            if document is None or (binding.mode=="original_versions" and str(document.current_version_id)!=str(source.get("document_version_id"))): raise WorkspaceNotFound("Source version unavailable.")
            document_ids.append(source_id)
        elif source_type=="note" and source_id:
            note=db.get(Note,uuid.UUID(source_id))
            version_id=source.get("note_version_id")
            if note is None or note.deleted_at is not None or not version_id: raise WorkspaceNotFound("Source version unavailable.")
            from backend.app.models.workspace_content import NoteVersion
            version=db.get(NoteVersion,uuid.UUID(version_id))
            if version is None or version.note_id!=note.id or (binding.mode=="original_versions" and version.revision!=note.revision): raise WorkspaceNotFound("Source version unavailable.")
            note_ids.append(source_id)
        elif source_type in {"conversation","pasted_text"}: raise WorkspaceNotFound("Source version unavailable for grounded follow-up.")
    return payload.model_copy(update={"selected_document_ids":document_ids,"selected_folder_ids":[],"selected_note_ids":note_ids})


@router.post("/chat/attachments", response_model=ChatAttachmentResponse, status_code=status.HTTP_201_CREATED)
def upload_chat_attachment(request: Request, file: UploadFile = File(...), session_id: uuid.UUID | None = Form(default=None), db: Session = Depends(get_db_session)) -> ChatAttachmentResponse:
    access = require_authenticated_access_context(request)
    if session_id is not None:
        existing = ChatRepository(db).get_session_for_user(session_id, access.principal.user_id)
        if existing is None and db.get(ChatSession, session_id) is not None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    try:
        payload = PersonalWorkspaceService(db).upload(
            access, file.filename or "upload", file.file, metadata={"chat_session_id": str(session_id) if session_id else None},
            source_type="chat_upload", audit_action="chat.attachment.uploaded", system_folder_key="chat_uploads",
        )
    except WorkspaceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ChatAttachmentResponse(document_id=payload["id"], document_version_id=payload["document_version_id"],
        name=payload["name"], size_bytes=payload["size_bytes"], mime_type=payload.get("mime_type"),
        indexing_status=payload["status"], indexing_job_id=payload["indexing_job_id"],
        indexing_safe_message="Queued for preparation.")


def _public_metadata(value: dict | None) -> dict:
    metadata = dict(value or {})
    metadata.pop("evidence_snapshot", None)
    metadata.pop("generation_request", None)
    return metadata


def _record(session: ChatSession, repository: ChatRepository) -> ChatSessionRecord:
    return ChatSessionRecord(
        id=session.id,
        title=session.title or "New conversation",
        messages=[
            ChatMessageRecord(
                id=message.id, role=message.role, content=message.content,
                citations=message.citations or [], sources=message.sources or [],
                metadata=_public_metadata(message.metadata_), created_at=message.created_at,
                feedback=(repository.get_feedback(message.id, session.user_id).metadata_ or {}).get("categories", []) if repository.get_feedback(message.id, session.user_id) else [],
            )
            for message in repository.list_messages_for_user(session.id, session.user_id)
        ],
        created_at=session.created_at, updated_at=session.updated_at,
        origin=session.origin, created_from_document=session.created_from_document,
        context_scope=session.context_scope, selected_document_ids=list(session.selected_document_ids or []),
        selected_note_ids=list(session.selected_note_ids or []), context_snapshot=list(session.context_snapshot or []),
    )


@router.post("/chat/stream")
def stream_chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db_session)):
    """Stream actual pipeline boundary events and one final compatible result."""
    runtime_state=request.app.state.runtime_state
    if not runtime_state.snapshot()["engine_ready"]:
        raise HTTPException(503,detail=runtime_state.chat_unavailable_detail())
    access=require_authenticated_access_context(request); user_id=access.principal.user_id
    request_id=str(uuid.uuid4()); events:queue.Queue=queue.Queue(); cancelled=threading.Event(); started=time.monotonic()
    def progress(stage_id,status_value,metrics):
        if cancelled.is_set(): raise _StreamCancelled()
        events.put({"request_id":request_id,"type":"stage","stage_id":stage_id,"status":status_value,"elapsed_ms":int((time.monotonic()-started)*1000),"metrics":metrics})
    def token(delta):
        if cancelled.is_set(): raise _StreamCancelled()
        events.put({"request_id":request_id,"type":"token","stage_id":"generation","status":"started","elapsed_ms":int((time.monotonic()-started)*1000),"delta":delta})
    def run():
        repository=ChatRepository(db)
        try:
            bound_payload=_apply_summary_binding(payload,db,user_id)
            chat_session=repository.get_session_for_user(payload.session_id,user_id) if payload.session_id else None
            if payload.session_id and chat_session is None and db.get(ChatSession,payload.session_id) is not None: raise WorkspaceNotFound("Conversation not found.")
            if chat_session is None: chat_session=repository.add_session(ChatSession(id=payload.session_id or uuid.uuid4(),user_id=user_id,title=payload.question.strip()[:72]))
            bound_payload=ConversationService.enforce(chat_session,bound_payload)
            response=request.app.state.knowledge_engine.answer_question(bound_payload,access_context=access,progress_callback=progress,token_callback=token,cancel_event=cancelled)
            if cancelled.is_set(): raise _StreamCancelled()
            progress("persistence.saving","started",{})
            user_message=repository.add_message(ChatMessage(session_id=chat_session.id,user_id=user_id,role="user",content=bound_payload.question,metadata_={"selected_document_ids":bound_payload.selected_document_ids,"selected_folder_ids":bound_payload.selected_folder_ids,"selected_note_ids":bound_payload.selected_note_ids,"profile":bound_payload.profile or bound_payload.response_length,"response_length":bound_payload.response_length,"max_answer_words":bound_payload.max_answer_words}))
            assistant_message=repository.add_message(ChatMessage(session_id=chat_session.id,user_id=user_id,role="assistant",content=response.answer,citations=[item.model_dump(mode="json") for item in response.citations],sources=[item.model_dump(mode="json") for item in response.sources],metadata_={**response.metadata.model_dump(mode="json"),"generation_request":bound_payload.model_dump(mode="json",exclude={"question","session_id","include_debug"}),"user_message_id":str(user_message.id),"evidence_snapshot":response.evidence_snapshot}))
            chat_session.updated_at=datetime.now(timezone.utc); db.commit(); response.session_id=chat_session.id; response.user_message_id=user_message.id; response.assistant_message_id=assistant_message.id
            progress("persistence.saving","completed",{}); events.put({"request_id":request_id,"type":"result","stage_id":"complete","status":"completed","elapsed_ms":response.metadata.latency_ms,"payload":jsonable_encoder(response)})
        except _StreamCancelled:
            db.rollback(); events.put({"request_id":request_id,"type":"cancelled","stage_id":"complete","status":"failed","elapsed_ms":int((time.monotonic()-started)*1000),"metrics":{}})
        except WorkspaceNotFound as exc:
            db.rollback(); events.put({"request_id":request_id,"type":"error","stage_id":"complete","status":"failed","elapsed_ms":int((time.monotonic()-started)*1000),"payload":{"message":str(exc)}})
        except Exception:
            if cancelled.is_set():
                db.rollback(); events.put({"request_id":request_id,"type":"cancelled","stage_id":"complete","status":"failed","elapsed_ms":int((time.monotonic()-started)*1000),"metrics":{}}); return
            logger.exception("chat_stream_failed", extra={"request_id": request_id})
            db.rollback(); events.put({"request_id":request_id,"type":"error","stage_id":"complete","status":"failed","elapsed_ms":int((time.monotonic()-started)*1000),"payload":{"message":"The assistant could not complete this request."}})
        finally: events.put(None)
    threading.Thread(target=run,name=f"chat-{request_id}",daemon=True).start()
    def body():
        try:
            while True:
                item=events.get()
                if item is None: break
                yield json.dumps(item,separators=(",",":"))+"\n"
        finally: cancelled.set()
    return StreamingResponse(body(),media_type="application/x-ndjson",headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})


@router.get("/chat/sessions", response_model=ChatSessionList)
def list_chat_sessions(request: Request, db: Session = Depends(get_db_session)) -> ChatSessionList:
    access = require_authenticated_access_context(request)
    repository = ChatRepository(db)
    return ChatSessionList(sessions=[_record(item, repository) for item in repository.list_sessions_for_user(access.principal.user_id)])


@router.post("/chat/sessions", response_model=ChatSessionRecord, status_code=201)
def create_chat_session(payload: ChatSessionCreate, request: Request, db: Session = Depends(get_db_session)) -> ChatSessionRecord:
    access = require_authenticated_access_context(request)
    try:
        item = ConversationService(db).create(access, payload)
    except WorkspaceNotFound as exc:
        raise HTTPException(status_code=404, detail="Selected context was not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _record(item, ChatRepository(db))


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
    try: payload=_apply_summary_binding(payload,db,user_id)
    except WorkspaceNotFound as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    repository = ChatRepository(db)
    chat_session = repository.get_session_for_user(payload.session_id, user_id) if payload.session_id else None
    if payload.session_id and chat_session is None:
        # A client-generated UUID is accepted only for a new session; an id owned by
        # another user remains indistinguishable from a missing id.
        if db.get(ChatSession, payload.session_id) is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if chat_session is None:
        chat_session = repository.add_session(ChatSession(id=payload.session_id or uuid.uuid4(), user_id=user_id, title=payload.question.strip()[:72]))
    payload = ConversationService.enforce(chat_session, payload)
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
            metadata_={"selected_document_ids": payload.selected_document_ids, "selected_folder_ids": payload.selected_folder_ids, "selected_note_ids": payload.selected_note_ids, "profile": payload.profile or payload.response_length, "response_length": payload.response_length, "max_answer_words": payload.max_answer_words},
        ))
        assistant_message = repository.add_message(ChatMessage(
            session_id=chat_session.id, user_id=user_id, role="assistant", content=response.answer,
            citations=[item.model_dump(mode="json") for item in response.citations],
            sources=[item.model_dump(mode="json") for item in response.sources],
            metadata_={**response.metadata.model_dump(mode="json"), "generation_request": payload.model_dump(mode="json", exclude={"question", "session_id", "include_debug"}), "user_message_id": str(user_message.id), "evidence_snapshot": response.evidence_snapshot},
        ))
        chat_session.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        response.session_id = chat_session.id
        response.user_message_id = user_message.id
        response.assistant_message_id = assistant_message.id
        return response
    except KnowledgeEngineDocumentsNotReady as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "documents_not_ready", "message": str(exc), "documents": exc.documents,
        }) from exc
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
    return ChatActionService(db, request.app.state.knowledge_engine)


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
        if payload.operation == "explain_simpler":
            message = MessageTransformationService(db, request.app.state.transformation_generator).explain_simpler(message_id, access)
        elif payload.operation == "create_checklist":
            message = MessageTransformationService(db, request.app.state.transformation_generator).create_checklist(message_id, access)
        else:
            message = _actions(request, db).transform(message_id, payload.operation, access)
        return ChatMessageRecord(id=message.id, role="assistant", content=message.content, citations=message.citations or [], sources=message.sources or [], metadata=_public_metadata(message.metadata_), created_at=message.created_at)
    except (ChatActionError, MessageTransformationError) as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.put("/chat/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
def update_feedback(message_id: uuid.UUID, payload: MessageFeedbackRequest, request: Request, db: Session = Depends(get_db_session)) -> MessageFeedbackResponse:
    access = require_authenticated_access_context(request)
    try:
        return MessageFeedbackResponse(active=_actions(request, db).toggle_feedback(message_id, payload.feedback, access))
    except ChatActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc

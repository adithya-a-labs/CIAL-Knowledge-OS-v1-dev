"""Owned, transactional actions on persisted assistant messages."""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatMessage, ConversationFeedback
from backend.app.repositories.chats import ChatRepository
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.security.access import RequestAccessContext


class ChatActionError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code, self.status_code = code, status_code


class ChatActionService:
    def __init__(self, db: Session, engine) -> None:
        self.db, self.repository, self.engine = db, ChatRepository(db), engine

    def _assistant(self, message_id: uuid.UUID, access: RequestAccessContext) -> ChatMessage:
        item = self.repository.get_message_for_user(message_id, access.principal.user_id)
        if item is None or item.role != "assistant":
            raise ChatActionError("Assistant response not found.", code="message_not_found", status_code=404)
        return item

    def regenerate(self, message_id: uuid.UUID, access: RequestAccessContext) -> ChatResponse:
        original = self._assistant(message_id, access)
        submitted_order = time.time_ns()
        metadata = original.metadata_ or {}
        try:
            user_id = uuid.UUID(str(metadata["user_message_id"]))
            user_message = self.repository.get_message_for_user(user_id, access.principal.user_id)
        except (KeyError, ValueError):
            user_message = None
        if user_message is None or user_message.role != "user":
            raise ChatActionError("The original question is unavailable.", code="missing_generation_context", status_code=409)
        settings = dict(metadata.get("generation_request") or {})
        if not settings:
            raise ChatActionError("Persisted generation settings are unavailable.", code="missing_generation_context", status_code=409)
        payload = ChatRequest(session_id=original.session_id, question=user_message.content, **settings)
        try:
            response = self.engine.answer_question(payload, access_context=access)
        except Exception as exc:
            raise ChatActionError("Regeneration failed; the original response was retained.", code="generation_failed", status_code=503) from exc
        replacement = ChatMessage(
            session_id=original.session_id, user_id=access.principal.user_id, role="assistant",
            turn_sequence=submitted_order, role_sequence=1,
            content=response.answer, citations=[x.model_dump(mode="json") for x in response.citations],
            sources=[x.model_dump(mode="json") for x in response.sources],
            metadata_={**response.metadata.model_dump(mode="json"), "generation_request": settings,
                       "user_message_id": str(user_message.id), "regenerated_from": str(original.id),
                       "evidence_snapshot": response.evidence_snapshot},
        )
        self.repository.add_message(replacement)
        self.db.commit(); self.db.refresh(replacement)
        response.session_id, response.user_message_id, response.assistant_message_id = original.session_id, user_message.id, replacement.id
        return response

    def transform(self, message_id: uuid.UUID, operation: str, access: RequestAccessContext) -> ChatMessage:
        source = self._assistant(message_id, access)
        submitted_order = time.time_ns()
        if not source.sources or not source.citations:
            raise ChatActionError("Persisted evidence is insufficient for this transformation.", code="missing_persisted_evidence", status_code=409)
        if operation == "create_checklist":
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source.content) if s.strip()]
            actionable = [s for s in sentences if re.search(r"\b(must|should|shall|required|ensure|verify|check|maintain|record|report|review)\b", s, re.I)]
            content = "\n".join(f"- [ ] {s}" for s in actionable)
            if not content:
                raise ChatActionError("No evidence-supported actions were found.", code="no_actionable_content", status_code=409)
        else:
            content = re.sub(r"\b(utilize|commence|terminate|subsequent|prior to|in order to)\b", lambda m: {"utilize":"use","commence":"start","terminate":"end","subsequent":"next","prior to":"before","in order to":"to"}[m.group(0).lower()], source.content, flags=re.I)
        item = ChatMessage(session_id=source.session_id, user_id=access.principal.user_id, role="assistant",
                           turn_sequence=submitted_order, role_sequence=1, content=content,
                           citations=source.citations, sources=source.sources,
                           metadata_={**(source.metadata_ or {}), "transform_operation": operation, "source_message_id": str(source.id)})
        self.repository.add_message(item); self.db.commit(); self.db.refresh(item)
        return item

    def toggle_feedback(self, message_id: uuid.UUID, category: str, access: RequestAccessContext) -> list[str]:
        self._assistant(message_id, access)
        item = self.repository.get_feedback(message_id, access.principal.user_id)
        if item is None:
            item = self.repository.add_feedback(ConversationFeedback(message_id=message_id, user_id=access.principal.user_id, metadata_={"categories": []}))
        active = set((item.metadata_ or {}).get("categories", []))
        if category in active: active.remove(category)
        else:
            active.add(category)
            if category == "helpful": active.discard("not_helpful")
            elif category == "not_helpful": active.discard("helpful")
        negative = {"not_helpful", "incorrect", "missing_sources", "hallucination"}
        item.rating = 1 if "helpful" in active else (-1 if active.intersection(negative) else None)
        item.metadata_ = {**(item.metadata_ or {}), "categories": sorted(active), "updated_at": datetime.now(timezone.utc).isoformat()}
        self.db.commit()
        return sorted(active)

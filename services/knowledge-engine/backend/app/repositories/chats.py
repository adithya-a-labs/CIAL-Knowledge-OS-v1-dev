"""Conversation metadata repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatMessage, ChatSession, ConversationFeedback, SavedContext


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_session_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession | None:
        return self.session.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )

    def list_sessions_for_user(self, user_id: uuid.UUID | None) -> list[ChatSession]:
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc())
        if user_id is None:
            statement = statement.where(ChatSession.user_id.is_(None))
        else:
            statement = statement.where(ChatSession.user_id == user_id)
        return list(self.session.scalars(statement))

    def list_messages_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatMessage]:
        return list(
            self.session.scalars(
                select(ChatMessage).join(ChatSession)
                .where(ChatMessage.session_id == session_id, ChatSession.user_id == user_id)
                .order_by(ChatMessage.created_at)
            )
        )

    def add_session(self, chat_session: ChatSession) -> ChatSession:
        self.session.add(chat_session)
        return chat_session

    def add_message(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        return message

    def add_saved_context(self, context: SavedContext) -> SavedContext:
        self.session.add(context)
        return context

    def add_feedback(self, feedback: ConversationFeedback) -> ConversationFeedback:
        self.session.add(feedback)
        return feedback

    def get_message_for_user(self, message_id: uuid.UUID, user_id: uuid.UUID) -> ChatMessage | None:
        return self.session.scalar(
            select(ChatMessage).join(ChatSession).where(
                ChatMessage.id == message_id, ChatSession.user_id == user_id
            )
        )

    def get_feedback(self, message_id: uuid.UUID, user_id: uuid.UUID) -> ConversationFeedback | None:
        return self.session.scalar(
            select(ConversationFeedback)
            .where(ConversationFeedback.message_id == message_id, ConversationFeedback.user_id == user_id)
            .order_by(ConversationFeedback.created_at.desc())
        )

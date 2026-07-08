"""Conversation metadata repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatMessage, ChatSession, ConversationFeedback, SavedContext


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_session(self, session_id: uuid.UUID) -> ChatSession | None:
        return self.session.get(ChatSession, session_id)

    def list_sessions_for_user(self, user_id: uuid.UUID | None) -> list[ChatSession]:
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc())
        if user_id is None:
            statement = statement.where(ChatSession.user_id.is_(None))
        else:
            statement = statement.where(ChatSession.user_id == user_id)
        return list(self.session.scalars(statement))

    def list_messages(self, session_id: uuid.UUID) -> list[ChatMessage]:
        return list(
            self.session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
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


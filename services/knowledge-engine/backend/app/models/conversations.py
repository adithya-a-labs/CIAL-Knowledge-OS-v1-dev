"""Conversation metadata models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user_id", "user_id"),
        CheckConstraint("origin in ('assistant','homepage','knowledge_center','global_search','saved_knowledge')", name="ck_chat_sessions_origin"),
        CheckConstraint("context_scope in ('all_accessible','selected_documents','selected_context')", name="ck_chat_sessions_context_scope"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(Text)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"))
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default="assistant")
    created_from_document: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"))
    context_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="all_accessible")
    selected_document_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    selected_note_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    context_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    messages: Mapped[list[ChatMessage]] = relationship(back_populates="session")
    summaries: Mapped[list[ConversationSummary]] = relationship(back_populates="session")


class ChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_session_id", "session_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class SavedContext(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_contexts"

    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str | None] = mapped_column(Text)
    selected_document_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    selected_folder_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class ConversationFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversation_feedback"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConversationSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (
        Index("ix_conversation_summaries_chat_session_id", "chat_session_id"),
        CheckConstraint(
            "summary_type in ('running', 'final', 'topic', 'handoff')",
            name="ck_conversation_summaries_summary_type",
        ),
    )

    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    summary_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

    session: Mapped[ChatSession] = relationship(back_populates="summaries")

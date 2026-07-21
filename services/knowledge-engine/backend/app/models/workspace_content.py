"""Durable private notes and immutable generated summary artifacts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Note(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notes"
    __table_args__ = (
        Index("ix_notes_owner_workspace_updated", "owner_user_id", "workspace_id", "updated_at"),
        Index("ix_notes_owner_pinned", "owner_user_id", postgresql_where=text("is_pinned = true and deleted_at is null")),
        Index("ix_notes_owner_archived", "owner_user_id", postgresql_where=text("is_archived = true and deleted_at is null")),
        CheckConstraint("revision >= 1", name="ck_notes_revision"),
        CheckConstraint("length(trim(content_format)) > 0", name="ck_notes_content_format"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="Untitled")
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    content_format: Mapped[str] = mapped_column(Text, nullable=False, server_default="markdown")
    plain_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class NoteVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "note_versions"
    __table_args__ = (UniqueConstraint("note_id", "revision", name="uq_note_versions_note_revision"), Index("ix_note_versions_note_id", "note_id"))
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class NoteTag(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "note_tags"
    __table_args__ = (UniqueConstraint("owner_user_id", "normalized_name", name="uq_note_tags_owner_name"), Index("ix_note_tags_workspace_owner", "workspace_id", "owner_user_id"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NoteTagLink(Base):
    __tablename__ = "note_tag_links"
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("note_tags.id", ondelete="CASCADE"), primary_key=True)


class NoteDocumentLink(Base):
    __tablename__ = "note_document_links"
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SummaryArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "summary_artifacts"
    __table_args__ = (
        Index("ix_summary_artifacts_owner_status_created", "owner_user_id", "status", "created_at"),
        CheckConstraint("summary_type in ('executive','detailed','key_points','action_items')", name="ck_summary_artifacts_type"),
        CheckConstraint("summary_length in ('brief','standard','detailed')", name="ck_summary_artifacts_length"),
        CheckConstraint("multi_document_mode in ('together','separate','compare')", name="ck_summary_artifacts_mode"),
        CheckConstraint("status in ('pending','running','completed','failed','cancelled')", name="ck_summary_artifacts_status"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_summary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary_length: Mapped[str] = mapped_column(Text, nullable=False)
    multi_document_mode: Mapped[str] = mapped_column(Text, nullable=False)
    custom_instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    content_markdown: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prompt_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text)
    source_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message_safe: Mapped[str | None] = mapped_column(Text)


class SummarySource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "summary_sources"
    __table_args__ = (UniqueConstraint("summary_id", "ordinal", name="uq_summary_sources_ordinal"),)
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="RESTRICT"))
    note_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("note_versions.id", ondelete="RESTRICT"))
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SummaryCitation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "summary_citations"
    __table_args__ = (UniqueConstraint("summary_id", "citation_id", name="uq_summary_citations_id"),)
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False)
    citation_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_sources.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"))
    note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="SET NULL"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    chunk_id: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

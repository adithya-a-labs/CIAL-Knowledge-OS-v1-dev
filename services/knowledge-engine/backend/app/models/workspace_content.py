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


class NoteIndexState(Base):
    __tablename__ = "note_index_states"
    __table_args__ = (CheckConstraint("status in ('pending','indexing','indexed','failed','removed')", name="ck_note_index_states_status"),)
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    indexed_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    content_hash: Mapped[str | None] = mapped_column(Text)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SavedKnowledgeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_knowledge_items"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "summary_id", name="uq_saved_knowledge_owner_summary"),
        Index("ix_saved_knowledge_owner_created", "owner_user_id", "created_at"),
        CheckConstraint("item_type in ('summary','answer')", name="ck_saved_knowledge_item_type"),
        CheckConstraint("visibility in ('private','restricted')", name="ck_saved_knowledge_visibility"),
        CheckConstraint("state in ('active','archived')", name="ck_saved_knowledge_state"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="summary")
    summary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="SET NULL"))
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    original_question: Mapped[str | None] = mapped_column(Text)
    citation_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    selected_document_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    context_scope: Mapped[str | None] = mapped_column(Text)
    profile: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    collection: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="private")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    provenance_hash: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedKnowledgeVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saved_knowledge_versions"
    __table_args__ = (UniqueConstraint("saved_knowledge_id", "version", name="uq_saved_knowledge_versions_item_version"),)
    saved_knowledge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_knowledge_items.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    citation_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class SummaryConversationBinding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "summary_conversation_bindings"
    __table_args__ = (UniqueConstraint("summary_id", "chat_session_id", name="uq_summary_conversation_binding"), CheckConstraint("mode in ('original_versions','latest_versions')", name="ck_summary_conversation_binding_mode"))
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False)
    chat_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="original_versions")
    source_binding: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SummaryArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "summary_artifacts"
    __table_args__ = (
        Index("ix_summary_artifacts_owner_status_created", "owner_user_id", "status", "created_at"),
        Index("ix_summary_artifacts_document_version_created", "document_version_id", "created_at"),
        Index("ix_summary_artifacts_reuse_key", "reuse_key"),
        Index(
            "uq_summary_artifacts_active_document_analysis",
            "reuse_key",
            unique=True,
            postgresql_where=text("reuse_key is not null and status in ('queued','running') and deleted_at is null"),
        ),
        CheckConstraint("summary_type in ('executive','overview','detailed','key_points','action_items')", name="ck_summary_artifacts_type"),
        CheckConstraint("summary_length in ('brief','standard','detailed')", name="ck_summary_artifacts_length"),
        CheckConstraint("multi_document_mode in ('together','separate','compare')", name="ck_summary_artifacts_mode"),
        CheckConstraint("status in ('pending','queued','running','completed','failed','cancelled','stale')", name="ck_summary_artifacts_status"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"))
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="RESTRICT"))
    parent_summary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary_length: Mapped[str] = mapped_column(Text, nullable=False)
    multi_document_mode: Mapped[str] = mapped_column(Text, nullable=False)
    custom_instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    content_markdown: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    citation_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    prompt_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text)
    source_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    reuse_key: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    generation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    provenance_hash: Mapped[str | None] = mapped_column(Text)
    source_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    source_token_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    map_group_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message_safe: Mapped[str | None] = mapped_column(Text)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="SET NULL"))


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
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="RESTRICT"))
    note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="SET NULL"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    chunk_id: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    ordering: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class SummaryMapResult(UUIDPrimaryKeyMixin, Base):
    """Immutable checkpoint for one completed map or recursive-reduce group."""

    __tablename__ = "summary_map_results"
    __table_args__ = (
        UniqueConstraint("summary_id", "stage", "level", "group_index", name="uq_summary_map_results_group"),
        Index("ix_summary_map_results_summary_stage", "summary_id", "stage", "level", "group_index"),
        CheckConstraint("stage in ('map','reduce')", name="ck_summary_map_results_stage"),
        CheckConstraint("status in ('running','completed','failed')", name="ck_summary_map_results_status"),
    )
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    child_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    prompt_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    schema_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    model_name: Mapped[str | None] = mapped_column(Text)
    budgets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="completed")
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    output_token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

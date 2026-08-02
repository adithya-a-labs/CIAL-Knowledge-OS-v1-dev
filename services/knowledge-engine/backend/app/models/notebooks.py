"""Persistent notebook metadata and references around existing CIAL domains."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notebook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notebooks"
    __table_args__ = (
        Index("ix_notebooks_owner_updated", "owner_user_id", "updated_at"),
        Index("ix_notebooks_workspace", "workspace_id"),
        CheckConstraint("visibility = 'private'", name="ck_notebooks_personal_private"),
        CheckConstraint("lifecycle_status in ('active','archived','deleted')", name="ck_notebooks_lifecycle"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="private")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sources: Mapped[list[NotebookSource]] = relationship(back_populates="notebook", cascade="all, delete-orphan")
    session_binding: Mapped[NotebookSession | None] = relationship(back_populates="notebook", uselist=False, cascade="all, delete-orphan")
    artifacts: Mapped[list[NotebookArtifact]] = relationship(back_populates="notebook", cascade="all, delete-orphan")


class NotebookSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notebook_sources"
    __table_args__ = (
        Index("ix_notebook_sources_notebook_position", "notebook_id", "position"),
        Index("uq_notebook_sources_document", "notebook_id", "document_id", unique=True, postgresql_where=text("document_id is not null")),
        Index("uq_notebook_sources_note", "notebook_id", "note_id", unique=True, postgresql_where=text("note_id is not null")),
        Index("uq_notebook_sources_summary", "notebook_id", "summary_artifact_id", unique=True, postgresql_where=text("summary_artifact_id is not null")),
        CheckConstraint("source_type in ('document','note','summary')", name="ck_notebook_sources_type"),
        CheckConstraint("position >= 0", name="ck_notebook_sources_position"),
        CheckConstraint("num_nonnulls(document_id,note_id,summary_artifact_id) = 1", name="ck_notebook_sources_one_target"),
        CheckConstraint("(source_type='document') = (document_id is not null)", name="ck_notebook_sources_document_target"),
        CheckConstraint("(source_type='note') = (note_id is not null)", name="ck_notebook_sources_note_target"),
        CheckConstraint("(source_type='summary') = (summary_artifact_id is not null)", name="ck_notebook_sources_summary_target"),
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"))
    summary_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="CASCADE"))
    attached_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_default_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notebook: Mapped[Notebook] = relationship(back_populates="sources")


class NotebookSession(Base):
    __tablename__ = "notebook_sessions"
    notebook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), primary_key=True)
    chat_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notebook: Mapped[Notebook] = relationship(back_populates="session_binding")


class NotebookArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notebook_artifacts"
    __table_args__ = (
        Index("ix_notebook_artifacts_notebook_created", "notebook_id", "created_at"),
        Index("uq_notebook_artifacts_summary", "notebook_id", "summary_artifact_id", unique=True, postgresql_where=text("summary_artifact_id is not null")),
        CheckConstraint("artifact_type in ('executive','detailed','key_points','action_items','comparison')", name="ck_notebook_artifacts_type"),
        CheckConstraint("status in ('pending','queued','running','completed','failed','cancelled')", name="ck_notebook_artifacts_status"),
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    summary_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("summary_artifacts.id", ondelete="SET NULL"))
    note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="SET NULL"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    error_code: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    notebook: Mapped[Notebook] = relationship(back_populates="artifacts")

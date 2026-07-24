"""Operational metadata models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UUIDPrimaryKeyMixin


class IngestionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_repository_id", "repository_id"),
    )

    repository_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    files_indexed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    files_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    message: Mapped[str | None] = mapped_column(Text)
    started_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class IndexingJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "indexing_jobs"
    __table_args__ = (
        Index("ix_indexing_jobs_status", "status"),
        Index(
            "ix_indexing_jobs_claim_order",
            "status",
            "available_at",
            "priority",
            "created_at",
        ),
        Index("ix_indexing_jobs_lease_recovery", "lease_expires_at", "status"),
        Index("ix_indexing_jobs_document_id", "document_id"),
        Index("ix_indexing_jobs_document_version_id", "document_version_id"),
        Index("ix_indexing_jobs_note_id", "note_id"),
        Index("ix_indexing_jobs_note_version_id", "note_version_id"),
        Index("ix_indexing_jobs_content_hash", "content_hash"),
        Index("ix_indexing_jobs_repository_id", "repository_id"),
        Index(
            "uq_indexing_jobs_active_document_operation",
            "document_version_id",
            "operation",
            unique=True,
            postgresql_where=text(
                "document_version_id IS NOT NULL AND status IN "
                "('pending','claimed','extracting','chunked','embedding','writing','verifying','retry_wait')"
            ),
        ),
        Index(
            "uq_indexing_jobs_active_note_operation",
            "note_version_id",
            "operation",
            unique=True,
            postgresql_where=text(
                "note_version_id IS NOT NULL AND status IN "
                "('pending','claimed','extracting','chunked','embedding','writing','verifying','retry_wait')"
            ),
        ),
        CheckConstraint(
            "status in ('pending','claimed','extracting','chunked','embedding',"
            "'writing','verifying','completed','retry_wait','failed',"
            "'superseded','cancelled')",
            name="ck_indexing_jobs_status",
        ),
        CheckConstraint(
            "operation in ('upsert_version','delete_asset','refresh_metadata',"
            "'reprocess_version','rebuild_scope')",
            name="ck_indexing_jobs_operation",
        ),
        CheckConstraint(
            "(operation = 'rebuild_scope') OR "
            "(asset_type = 'document' AND document_id IS NOT NULL "
            "AND note_id IS NULL AND note_version_id IS NULL) OR "
            "(asset_type = 'note' AND note_id IS NOT NULL "
            "AND document_id IS NULL AND document_version_id IS NULL)",
            name="ck_indexing_jobs_target_family",
        ),
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
    )
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
    )
    asset_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="document")
    note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="SET NULL"),
    )
    note_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("note_versions.id", ondelete="SET NULL"),
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False, server_default="upsert_version")
    content_hash: Mapped[str | None] = mapped_column(Text)
    repository_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    force_rebuild: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class IndexerWorker(Base):
    """Durable heartbeat and safe operational telemetry for an indexer process."""

    __tablename__ = "indexer_workers"

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    service_state: Mapped[str] = mapped_column(Text, nullable=False, server_default="starting")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("indexing_jobs.id", ondelete="SET NULL"),
    )
    reconciliation_state: Mapped[str | None] = mapped_column(Text)
    last_reconciliation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding_device: Mapped[str | None] = mapped_column(Text)
    embedding_precision: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    last_error_code: Mapped[str | None] = mapped_column(Text)


class IndexGeneration(Base):
    """Single-row generation pointer published after verified index commits."""

    __tablename__ = "index_generations"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    bm25_generation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    bm25_snapshot_path: Mapped[str | None] = mapped_column(Text)
    qdrant_collection: Mapped[str | None] = mapped_column(Text)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published_by: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_user_id", "user_id"),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_entity_type_entity_id", "entity_type", "entity_id"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before_state: Mapped[dict[str, Any] | None] = mapped_column("before", JSONB)
    after_state: Mapped[dict[str, Any] | None] = mapped_column("after", JSONB)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RetrievalEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retrieval_events"
    __table_args__ = (
        Index("ix_retrieval_events_user_id", "user_id"),
        Index("ix_retrieval_events_chat_session_id", "chat_session_id"),
        Index("ix_retrieval_events_created_at", "created_at"),
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
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_scope: Mapped[str | None] = mapped_column(Text)
    selected_document_ids: Mapped[list[object] | None] = mapped_column(JSONB)
    selected_folder_ids: Mapped[list[object] | None] = mapped_column(JSONB)
    retrieved_document_ids: Mapped[list[object] | None] = mapped_column(JSONB)
    retrieved_chunk_ids: Mapped[list[object] | None] = mapped_column(JSONB)
    reranker_scores: Mapped[list[object] | None] = mapped_column(JSONB)
    filters_applied: Mapped[dict[str, object] | list[object] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    result_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SearchHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "search_history"
    __table_args__ = (
        Index("ix_search_history_user_updated", "user_id", "updated_at"),
        Index("ix_search_history_user_normalized", "user_id", "normalized_query", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ExportJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_user_id", "user_id"),
        Index("ix_export_jobs_status", "status"),
        Index("ix_export_jobs_created_at", "created_at"),
        Index("ix_export_jobs_expires_at", "expires_at"),
        CheckConstraint("format in ('pdf', 'docx')", name="ck_export_jobs_format"),
        CheckConstraint("status in ('queued','processing','ready','failed','expired','cancelled')", name="ck_export_jobs_status"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    progress_stage: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    output_filename: Mapped[str | None] = mapped_column(Text)
    output_mime_type: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    preview_storage_key: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Text)
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Knowledge metadata models for files, folders, chunks, and permissions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Folder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "folders"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    subfolder_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parent: Mapped[Folder | None] = relationship(remote_side="Folder.id")
    documents: Mapped[list[Document]] = relationship(back_populates="folder")


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_organization_id", "organization_id"),
        Index("ix_documents_department_id", "department_id"),
        Index("ix_documents_content_hash", "content_hash"),
        Index("ix_documents_folder_id", "folder_id"),
        Index("ix_documents_owner_user_id", "owner_user_id"),
        Index("ix_documents_storage_scope", "storage_scope"),
        Index("ix_documents_visibility", "visibility"),
        Index("ix_documents_lifecycle_status", "lifecycle_status"),
        CheckConstraint(
            "storage_scope in ('enterprise', 'personal')",
            name="ck_documents_storage_scope",
        ),
        CheckConstraint(
            "visibility in ('private', 'department', 'enterprise', 'restricted')",
            name="ck_documents_visibility",
        ),
        CheckConstraint(
            "lifecycle_status in ('pending', 'indexing', 'indexed', 'failed', 'archived', 'deleted')",
            name="ck_documents_lifecycle_status",
        ),
        CheckConstraint(
            "source_type in ('corpus_sync', 'user_upload', 'system_import', 'backup_sync')",
            name="ck_documents_source_type",
        ),
        CheckConstraint(
            "(storage_scope <> 'personal') or owner_user_id is not null",
            name="ck_documents_personal_owner_required",
        ),
        CheckConstraint(
            "(storage_scope <> 'personal') or visibility = 'private'",
            name="ck_documents_personal_private_visibility",
        ),
        CheckConstraint(
            "department_id is not null",
            name="ck_documents_department_required",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
    )
    storage_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="enterprise")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="enterprise")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(Text)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    indexing_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page_count: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="corpus_sync")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    delete_reason: Mapped[str | None] = mapped_column(Text)

    folder: Mapped[Folder | None] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document",
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version_number",
    )
    current_version: Mapped[DocumentVersion | None] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document")


class DocumentVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
        Index("ix_document_versions_document_id", "document_id"),
        CheckConstraint(
            "status in ('pending', 'indexing', 'indexed', 'failed', 'archived')",
            name="ck_document_versions_status",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text)
    extracted_text_path: Mapped[str | None] = mapped_column(Text)
    preview_artifact_path: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document: Mapped[Document] = relationship(back_populates="versions", foreign_keys=[document_id])


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_document_version_id", "document_version_id"),
        Index("ix_document_chunks_chunk_id", "chunk_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
    )
    chunk_id: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    qdrant_point_id: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    text_preview: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class FolderPermission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "folder_permissions"
    __table_args__ = (
        CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null",
            name="ck_folder_permissions_principal",
        ),
    )

    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"))
    permission: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentPermission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null",
            name="ck_document_permissions_principal",
        ),
        CheckConstraint(
            "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department') and subject_id is not null)",
            name="ck_document_permissions_subject",
        ),
        CheckConstraint(
            "permission in ('view', 'edit', 'manage', 'delete')",
            name="ck_document_permissions_permission",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"))
    subject_type: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    permission: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

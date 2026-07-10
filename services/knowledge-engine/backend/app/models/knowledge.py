"""Knowledge metadata models for files, folders, chunks, and permissions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        Index("ix_workspaces_organization_id", "organization_id"),
        Index("ix_workspaces_workspace_type", "workspace_type"),
        Index("ix_workspaces_owner_user_id", "owner_user_id"),
        Index("ix_workspaces_department_id", "department_id"),
        UniqueConstraint("organization_id", "slug", name="uq_workspaces_organization_slug"),
        CheckConstraint(
            "workspace_type in ('enterprise', 'personal', 'department', 'project', 'external', 'system')",
            name="ck_workspaces_workspace_type",
        ),
        CheckConstraint(
            "visibility in ('private', 'department', 'enterprise', 'restricted')",
            name="ck_workspaces_visibility",
        ),
        CheckConstraint(
            "(workspace_type <> 'personal') or owner_user_id is not null",
            name="ck_workspaces_personal_owner_required",
        ),
        CheckConstraint(
            "(workspace_type <> 'personal') or visibility = 'private'",
            name="ck_workspaces_personal_private_visibility",
        ),
        CheckConstraint(
            "(workspace_type <> 'department') or department_id is not null",
            name="ck_workspaces_department_required",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    folders: Mapped[list[Folder]] = relationship(back_populates="workspace")
    documents: Mapped[list[Document]] = relationship(back_populates="workspace")
    permissions: Mapped[list[WorkspacePermission]] = relationship(back_populates="workspace")


class Folder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "folders"
    __table_args__ = (
        Index("ix_folders_workspace_id", "workspace_id"),
        Index("ix_folders_repository_id", "repository_id"),
        UniqueConstraint("repository_id", "relative_path", name="uq_folders_repository_relative_path"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
    )
    repository_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    subfolder_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parent: Mapped[Folder | None] = relationship(remote_side="Folder.id")
    workspace: Mapped[Workspace] = relationship(back_populates="folders")
    documents: Mapped[list[Document]] = relationship(back_populates="folder")


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_organization_id", "organization_id"),
        Index("ix_documents_department_id", "department_id"),
        Index("ix_documents_repository_id", "repository_id"),
        Index("ix_documents_content_hash", "content_hash"),
        Index("ix_documents_folder_id", "folder_id"),
        Index("ix_documents_workspace_id", "workspace_id"),
        Index("ix_documents_owner_user_id", "owner_user_id"),
        Index("ix_documents_storage_scope", "storage_scope"),
        Index("ix_documents_visibility", "visibility"),
        Index("ix_documents_lifecycle_status", "lifecycle_status"),
        UniqueConstraint("repository_id", "relative_path", name="uq_documents_repository_relative_path"),
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
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
    )
    repository_id: Mapped[str | None] = mapped_column(Text)
    storage_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="enterprise")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
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
    workspace: Mapped[Workspace] = relationship(back_populates="documents")
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
        Index("ix_document_versions_repository_id", "repository_id"),
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
    repository_id: Mapped[str | None] = mapped_column(Text)
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
        Index("ix_folder_permissions_folder_id", "folder_id"),
        Index("ix_folder_permissions_subject_type_subject_id", "subject_type", "subject_id"),
        CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null or group_id is not null",
            name="ck_folder_permissions_principal",
        ),
        CheckConstraint(
            "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department', 'group') and subject_id is not null)",
            name="ck_folder_permissions_subject",
        ),
        CheckConstraint(
            "permission in ('view', 'edit', 'manage', 'delete')",
            name="ck_folder_permissions_permission",
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
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
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


class DocumentPermission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        Index("ix_document_permissions_document_id", "document_id"),
        Index("ix_document_permissions_subject_type_subject_id", "subject_type", "subject_id"),
        CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null or group_id is not null",
            name="ck_document_permissions_principal",
        ),
        CheckConstraint(
            "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department', 'group') and subject_id is not null)",
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
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
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


class WorkspacePermission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspace_permissions"
    __table_args__ = (
        Index("ix_workspace_permissions_workspace_id", "workspace_id"),
        Index("ix_workspace_permissions_subject_type_subject_id", "subject_type", "subject_id"),
        CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null or group_id is not null",
            name="ck_workspace_permissions_principal",
        ),
        CheckConstraint(
            "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department', 'group') and subject_id is not null)",
            name="ck_workspace_permissions_subject",
        ),
        CheckConstraint(
            "permission in ('view', 'edit', 'manage', 'delete')",
            name="ck_workspace_permissions_permission",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"))
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
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

    workspace: Mapped[Workspace] = relationship(back_populates="permissions")


class DocumentRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_relationships"
    __table_args__ = (
        Index("ix_document_relationships_source_document_id", "source_document_id"),
        Index("ix_document_relationships_target_document_id", "target_document_id"),
        Index("ix_document_relationships_relationship_type", "relationship_type"),
        UniqueConstraint(
            "organization_id",
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationships_pair_type",
        ),
        CheckConstraint(
            "relationship_type in ('related', 'references', 'supersedes', 'duplicate', 'derived_from', 'translation_of', 'attachment_of')",
            name="ck_document_relationships_relationship_type",
        ),
        CheckConstraint(
            "source_document_id <> target_document_id",
            name="ck_document_relationships_distinct_documents",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )


class DocumentSearchMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_search_metadata"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_search_metadata_document_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[object]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    entities: Mapped[list[object]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    topics: Mapped[list[object]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    language: Mapped[str | None] = mapped_column(Text)
    ocr_quality: Mapped[float | None] = mapped_column(Float)
    classification: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)

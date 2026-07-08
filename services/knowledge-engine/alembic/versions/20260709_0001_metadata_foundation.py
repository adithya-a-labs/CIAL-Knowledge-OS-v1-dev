"""metadata foundation

Revision ID: 20260709_0001
Revises:
Create Date: 2026-07-09
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260709_0001"
down_revision = None
branch_labels = None
depends_on = None


UUID_TYPE = postgresql.UUID(as_uuid=True)
JSONB_TYPE = postgresql.JSONB(astext_type=sa.Text())

ORG_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SYSTEM_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
ROLE_IDS = {
    "Super Admin": uuid.UUID("00000000-0000-4000-8000-000000000010"),
    "Knowledge Admin": uuid.UUID("00000000-0000-4000-8000-000000000011"),
    "Department Admin": uuid.UUID("00000000-0000-4000-8000-000000000012"),
    "Uploader": uuid.UUID("00000000-0000-4000-8000-000000000013"),
    "Reviewer": uuid.UUID("00000000-0000-4000-8000-000000000014"),
    "Viewer": uuid.UUID("00000000-0000-4000-8000-000000000015"),
}


def id_column() -> sa.Column:
    return sa.Column("id", UUID_TYPE, primary_key=True, nullable=False)


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def created_at_column() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "organizations",
        id_column(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("code", name="uq_organizations_code"),
    )

    op.create_table(
        "departments",
        id_column(),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamp_columns(),
    )

    op.create_table(
        "designations",
        id_column(),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamp_columns(),
    )

    op.create_table(
        "users",
        id_column(),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("designation_id", UUID_TYPE, sa.ForeignKey("designations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employee_id", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("profile_photo_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("employee_id", name="uq_users_employee_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "roles",
        id_column(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("role_id", UUID_TYPE, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    op.create_table(
        "folders",
        id_column(),
        sa.Column("parent_id", UUID_TYPE, sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("document_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("subfolder_count", sa.Integer(), server_default="0", nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("relative_path", name="uq_folders_relative_path"),
    )

    op.create_table(
        "documents",
        id_column(),
        sa.Column("folder_id", UUID_TYPE, sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("indexing_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("relative_path", name="uq_documents_relative_path"),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])

    op.create_table(
        "document_versions",
        id_column(),
        sa.Column("document_id", UUID_TYPE, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
    )

    op.create_table(
        "document_chunks",
        id_column(),
        sa.Column("document_id", UUID_TYPE, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("qdrant_point_id", sa.Text(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("text_preview", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        created_at_column(),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_chunk_id", "document_chunks", ["chunk_id"])

    op.create_table(
        "folder_permissions",
        id_column(),
        sa.Column("folder_id", UUID_TYPE, sa.ForeignKey("folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_id", UUID_TYPE, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("permission", sa.Text(), nullable=False),
        created_at_column(),
        sa.CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null",
            name="ck_folder_permissions_principal",
        ),
    )

    op.create_table(
        "document_permissions",
        id_column(),
        sa.Column("document_id", UUID_TYPE, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_id", UUID_TYPE, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("permission", sa.Text(), nullable=False),
        created_at_column(),
        sa.CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null",
            name="ck_document_permissions_principal",
        ),
    )

    op.create_table(
        "ingestion_runs",
        id_column(),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("files_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("files_indexed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("files_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])

    op.create_table(
        "indexing_jobs",
        id_column(),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("force_rebuild", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
    )
    op.create_index("ix_indexing_jobs_status", "indexing_jobs", ["status"])

    op.create_table(
        "audit_events",
        id_column(),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", UUID_TYPE, nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        created_at_column(),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_entity_type_entity_id", "audit_events", ["entity_type", "entity_id"])

    op.create_table(
        "chat_sessions",
        id_column(),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_table(
        "chat_messages",
        id_column(),
        sa.Column("session_id", UUID_TYPE, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", JSONB_TYPE, nullable=True),
        sa.Column("sources", JSONB_TYPE, nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        created_at_column(),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    op.create_table(
        "saved_contexts",
        id_column(),
        sa.Column("session_id", UUID_TYPE, sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("selected_document_ids", JSONB_TYPE, nullable=True),
        sa.Column("selected_folder_ids", JSONB_TYPE, nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        *timestamp_columns(),
    )

    op.create_table(
        "conversation_feedback",
        id_column(),
        sa.Column("message_id", UUID_TYPE, sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        created_at_column(),
    )

    seed_data()


def seed_data() -> None:
    now = datetime.now(timezone.utc)
    organizations = sa.table(
        "organizations",
        sa.column("id", UUID_TYPE),
        sa.column("name", sa.Text()),
        sa.column("code", sa.Text()),
        sa.column("logo_url", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    roles = sa.table(
        "roles",
        sa.column("id", UUID_TYPE),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    users = sa.table(
        "users",
        sa.column("id", UUID_TYPE),
        sa.column("organization_id", UUID_TYPE),
        sa.column("department_id", UUID_TYPE),
        sa.column("designation_id", UUID_TYPE),
        sa.column("employee_id", sa.Text()),
        sa.column("email", sa.Text()),
        sa.column("display_name", sa.Text()),
        sa.column("phone", sa.Text()),
        sa.column("profile_photo_url", sa.Text()),
        sa.column("status", sa.Text()),
        sa.column("last_login_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        organizations,
        [
            {
                "id": ORG_ID,
                "name": "CIAL",
                "code": "CIAL",
                "logo_url": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": role_id,
                "name": name,
                "description": f"{name} role",
                "created_at": now,
                "updated_at": now,
            }
            for name, role_id in ROLE_IDS.items()
        ],
    )
    op.bulk_insert(
        users,
        [
            {
                "id": SYSTEM_USER_ID,
                "organization_id": ORG_ID,
                "department_id": None,
                "designation_id": None,
                "employee_id": "SYSTEM",
                "email": "system@cial.local",
                "display_name": "System",
                "phone": None,
                "profile_photo_url": None,
                "status": "active",
                "last_login_at": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("conversation_feedback")
    op.drop_table("saved_contexts")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_audit_events_entity_type_entity_id", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_indexing_jobs_status", table_name="indexing_jobs")
    op.drop_table("indexing_jobs")
    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("document_permissions")
    op.drop_table("folder_permissions")
    op.drop_index("ix_document_chunks_chunk_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_folder_id", table_name="documents")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_table("documents")
    op.drop_table("folders")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("designations")
    op.drop_table("departments")
    op.drop_table("organizations")

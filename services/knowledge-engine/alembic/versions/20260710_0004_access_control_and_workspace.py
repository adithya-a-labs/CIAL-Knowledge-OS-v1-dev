"""access control, workspace, and lifecycle schema expansion

Revision ID: 20260710_0004
Revises: 20260709_0003
Create Date: 2026-07-10
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_0004"
down_revision = "20260709_0003"
branch_labels = None
depends_on = None


UUID_TYPE = postgresql.UUID(as_uuid=True)
JSONB_TYPE = postgresql.JSONB(astext_type=sa.Text())

ORG_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_SHARED_DEPARTMENT_ID = uuid.UUID("00000000-0000-4000-8000-000000000020")

PERMISSION_IDS = {
    "manage_users": uuid.UUID("00000000-0000-4000-8000-000000000101"),
    "manage_roles": uuid.UUID("00000000-0000-4000-8000-000000000102"),
    "manage_departments": uuid.UUID("00000000-0000-4000-8000-000000000103"),
    "view_enterprise_documents": uuid.UUID("00000000-0000-4000-8000-000000000104"),
    "view_department_documents": uuid.UUID("00000000-0000-4000-8000-000000000105"),
    "upload_enterprise_documents": uuid.UUID("00000000-0000-4000-8000-000000000106"),
    "manage_enterprise_documents": uuid.UUID("00000000-0000-4000-8000-000000000107"),
    "view_own_documents": uuid.UUID("00000000-0000-4000-8000-000000000108"),
    "upload_own_documents": uuid.UUID("00000000-0000-4000-8000-000000000109"),
    "delete_own_documents": uuid.UUID("00000000-0000-4000-8000-000000000110"),
    "use_ai_assistant": uuid.UUID("00000000-0000-4000-8000-000000000111"),
    "view_audit_logs": uuid.UUID("00000000-0000-4000-8000-000000000112"),
    "manage_settings": uuid.UUID("00000000-0000-4000-8000-000000000113"),
}

ROLE_PERMISSION_MAP = {
    "Super Admin": list(PERMISSION_IDS),
    "Knowledge Admin": [
        "manage_users",
        "manage_roles",
        "manage_departments",
        "view_enterprise_documents",
        "view_department_documents",
        "upload_enterprise_documents",
        "manage_enterprise_documents",
        "view_own_documents",
        "upload_own_documents",
        "delete_own_documents",
        "use_ai_assistant",
        "view_audit_logs",
        "manage_settings",
    ],
    "Department Admin": [
        "manage_departments",
        "view_enterprise_documents",
        "view_department_documents",
        "upload_enterprise_documents",
        "manage_enterprise_documents",
        "view_own_documents",
        "upload_own_documents",
        "delete_own_documents",
        "use_ai_assistant",
        "view_audit_logs",
    ],
    "Uploader": [
        "view_enterprise_documents",
        "view_department_documents",
        "upload_enterprise_documents",
        "view_own_documents",
        "upload_own_documents",
        "delete_own_documents",
        "use_ai_assistant",
    ],
    "Reviewer": [
        "view_enterprise_documents",
        "view_department_documents",
        "view_own_documents",
        "use_ai_assistant",
    ],
    "Viewer": [
        "view_enterprise_documents",
        "view_department_documents",
        "view_own_documents",
        "use_ai_assistant",
    ],
}


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    bind = op.get_bind()

    op.create_table(
        "permissions",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID_TYPE, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("permission_id", UUID_TYPE, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    op.create_table(
        "department_memberships",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "department_id", name="uq_department_memberships_user_department"),
    )

    op.create_table(
        "department_role_assignments",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", UUID_TYPE, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "department_id",
            "role_id",
            name="uq_department_role_assignments_user_department_role",
        ),
    )

    permissions = sa.table(
        "permissions",
        sa.column("id", UUID_TYPE),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "id": permission_id,
                "name": name,
                "description": name.replace("_", " "),
                "created_at": now,
                "updated_at": now,
            }
            for name, permission_id in PERMISSION_IDS.items()
        ],
    )

    for role_name, permission_names in ROLE_PERMISSION_MAP.items():
        in_list = ", ".join(f"'{name}'" for name in permission_names)
        op.execute(
            f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now()
            FROM roles r
            JOIN permissions p ON p.name IN ({in_list})
            WHERE r.name = '{role_name}'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )

    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=True))
    op.add_column("users", sa.Column("auth_provider", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("auth_subject", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("external_directory_id", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("ldap_dn", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_directory_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET is_active = CASE WHEN status = 'inactive' THEN false ELSE true END WHERE is_active IS NULL")
    op.alter_column("users", "is_active", existing_type=sa.Boolean(), nullable=False)
    op.create_unique_constraint("uq_users_auth_provider_subject", "users", ["auth_provider", "auth_subject"])

    bind.execute(
        sa.text(
            """
            INSERT INTO departments (
                id,
                organization_id,
                parent_department_id,
                name,
                code,
                description,
                created_at,
                updated_at
            )
            SELECT
                :department_id,
                :organization_id,
                NULL,
                'Shared Knowledge',
                'shared-knowledge',
                'Default department for enterprise corpus documents without an explicit owner department.',
                now(),
                now()
            WHERE EXISTS (
                SELECT 1 FROM organizations WHERE id = :organization_id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM departments
                WHERE organization_id = :organization_id
                  AND code = 'shared-knowledge'
            )
            """
        ),
        {
            "department_id": DEFAULT_SHARED_DEPARTMENT_ID,
            "organization_id": ORG_ID,
        },
    )

    op.add_column("documents", sa.Column("organization_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("department_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("storage_scope", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("owner_user_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("visibility", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("lifecycle_status", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("source_type", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("updated_by_user_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("current_version_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("deleted_by_user_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("delete_reason", sa.Text(), nullable=True))

    bind.execute(
        sa.text(
            """
            UPDATE documents AS d
            SET organization_id = COALESCE(u.organization_id, :organization_id)
            FROM users AS u
            WHERE d.created_by_user_id = u.id
              AND d.organization_id IS NULL
            """
        ),
        {"organization_id": ORG_ID},
    )
    bind.execute(
        sa.text(
            """
            UPDATE documents
            SET organization_id = :organization_id
            WHERE organization_id IS NULL
            """
        ),
        {"organization_id": ORG_ID},
    )
    bind.execute(
        sa.text(
            """
            UPDATE documents AS d
            SET department_id = COALESCE(
                u.department_id,
                (
                    SELECT id
                    FROM departments
                    WHERE organization_id = :organization_id
                      AND code = 'shared-knowledge'
                    ORDER BY created_at, id
                    LIMIT 1
                ),
                :department_id
            )
            FROM users AS u
            WHERE d.created_by_user_id = u.id
              AND d.department_id IS NULL
            """
        ),
        {
            "department_id": DEFAULT_SHARED_DEPARTMENT_ID,
            "organization_id": ORG_ID,
        },
    )
    bind.execute(
        sa.text(
            """
            UPDATE documents
            SET department_id = COALESCE(
                (
                    SELECT id
                    FROM departments
                    WHERE organization_id = :organization_id
                      AND code = 'shared-knowledge'
                    ORDER BY created_at, id
                    LIMIT 1
                ),
                :department_id
            )
            WHERE department_id IS NULL
            """
        ),
        {
            "department_id": DEFAULT_SHARED_DEPARTMENT_ID,
            "organization_id": ORG_ID,
        },
    )
    op.execute("UPDATE documents SET storage_scope = 'enterprise' WHERE storage_scope IS NULL")
    op.execute("UPDATE documents SET visibility = 'enterprise' WHERE visibility IS NULL")
    op.execute(
        """
        UPDATE documents
        SET lifecycle_status = CASE indexing_status
            WHEN 'running' THEN 'indexing'
            WHEN 'indexed' THEN 'indexed'
            WHEN 'failed' THEN 'failed'
            WHEN 'deleted' THEN 'deleted'
            ELSE 'pending'
        END
        WHERE lifecycle_status IS NULL
        """
    )
    op.execute("UPDATE documents SET source_type = 'corpus_sync' WHERE source_type IS NULL")
    op.execute("UPDATE documents SET updated_by_user_id = created_by_user_id WHERE updated_by_user_id IS NULL")
    op.execute(
        """
        UPDATE documents
        SET deleted_at = COALESCE(deleted_at, updated_at, created_at),
            delete_reason = COALESCE(delete_reason, 'Legacy soft delete backfill')
        WHERE lifecycle_status = 'deleted'
        """
    )

    op.create_foreign_key(
        "fk_documents_organization_id",
        "documents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_documents_department_id",
        "documents",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_documents_owner_user_id",
        "documents",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_updated_by_user_id",
        "documents",
        "users",
        ["updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_deleted_by_user_id",
        "documents",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("document_versions", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("mime_type", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("extracted_text_path", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("preview_artifact_path", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("created_by_user_id", UUID_TYPE, nullable=True))
    op.add_column("document_versions", sa.Column("status", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_document_versions_created_by_user_id",
        "document_versions",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE document_versions AS dv
        SET storage_key = d.relative_path,
            mime_type = d.mime_type,
            created_by_user_id = d.created_by_user_id,
            status = CASE d.lifecycle_status
                WHEN 'indexing' THEN 'indexing'
                WHEN 'indexed' THEN 'indexed'
                WHEN 'failed' THEN 'failed'
                WHEN 'archived' THEN 'archived'
                ELSE 'pending'
            END
        FROM documents AS d
        WHERE dv.document_id = d.id
        """
    )
    op.execute("UPDATE document_versions SET status = 'pending' WHERE status IS NULL")

    op.execute(
        """
        UPDATE documents AS d
        SET current_version_id = latest.id
        FROM (
            SELECT DISTINCT ON (document_id)
                id,
                document_id
            FROM document_versions
            ORDER BY document_id, version_number DESC, created_at DESC, id DESC
        ) AS latest
        WHERE d.id = latest.document_id
          AND d.current_version_id IS NULL
        """
    )
    op.create_foreign_key(
        "fk_documents_current_version_id",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("document_chunks", sa.Column("document_version_id", UUID_TYPE, nullable=True))
    op.add_column("document_chunks", sa.Column("chunk_index", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("section", sa.Text(), nullable=True))
    op.add_column("document_chunks", sa.Column("text", sa.Text(), nullable=True))
    op.add_column("document_chunks", sa.Column("metadata", JSONB_TYPE, nullable=True))
    op.create_foreign_key(
        "fk_document_chunks_document_version_id",
        "document_chunks",
        "document_versions",
        ["document_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (PARTITION BY document_id ORDER BY created_at, id) - 1 AS chunk_index
            FROM document_chunks
        )
        UPDATE document_chunks AS dc
        SET chunk_index = ranked.chunk_index
        FROM ranked
        WHERE dc.id = ranked.id
          AND dc.chunk_index IS NULL
        """
    )
    op.execute(
        """
        UPDATE document_chunks AS dc
        SET document_version_id = d.current_version_id,
            text = COALESCE(dc.text_preview, dc.text),
            metadata = COALESCE(dc.metadata, '{}'::jsonb)
        FROM documents AS d
        WHERE dc.document_id = d.id
        """
    )

    op.add_column("document_permissions", sa.Column("subject_type", sa.Text(), nullable=True))
    op.add_column("document_permissions", sa.Column("subject_id", UUID_TYPE, nullable=True))
    op.add_column("document_permissions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document_permissions", sa.Column("created_by_user_id", UUID_TYPE, nullable=True))
    op.add_column(
        "document_permissions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_permissions_created_by_user_id",
        "document_permissions",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE document_permissions
        SET subject_type = CASE
                WHEN user_id IS NOT NULL THEN 'user'
                WHEN role_id IS NOT NULL THEN 'role'
                WHEN department_id IS NOT NULL THEN 'department'
                ELSE subject_type
            END,
            subject_id = COALESCE(user_id, role_id, department_id),
            updated_at = COALESCE(updated_at, created_at)
        WHERE subject_id IS NULL OR subject_type IS NULL
        """
    )

    op.add_column("indexing_jobs", sa.Column("document_version_id", UUID_TYPE, nullable=True))
    op.add_column("indexing_jobs", sa.Column("attempts", sa.Integer(), nullable=True))
    op.add_column("indexing_jobs", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.add_column("indexing_jobs", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.create_foreign_key(
        "fk_indexing_jobs_document_version_id",
        "indexing_jobs",
        "document_versions",
        ["document_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("DROP INDEX IF EXISTS uq_indexing_jobs_active_document_version")
    op.execute(
        """
        UPDATE indexing_jobs AS j
        SET document_version_id = d.current_version_id,
            attempts = COALESCE(j.attempts, CASE WHEN j.status = 'pending' THEN 0 ELSE 1 END),
            created_at = COALESCE(j.created_at, j.started_at, now()),
            updated_at = COALESCE(j.updated_at, j.completed_at, j.started_at, now())
        FROM documents AS d
        WHERE j.document_id = d.id
        """
    )
    op.execute(
        """
        UPDATE indexing_jobs
        SET attempts = COALESCE(attempts, CASE WHEN status = 'pending' THEN 0 ELSE 1 END),
            created_at = COALESCE(created_at, started_at, now()),
            updated_at = COALESCE(updated_at, completed_at, started_at, now())
        """
    )

    op.add_column("audit_events", sa.Column("actor_user_id", UUID_TYPE, nullable=True))
    op.add_column("audit_events", sa.Column("before", JSONB_TYPE, nullable=True))
    op.add_column("audit_events", sa.Column("after", JSONB_TYPE, nullable=True))
    op.add_column("audit_events", sa.Column("ip_address", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("status", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("error_detail", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_audit_events_actor_user_id",
        "audit_events",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE audit_events
        SET actor_user_id = user_id,
            status = COALESCE(status, 'success')
        WHERE actor_user_id IS NULL OR status IS NULL
        """
    )

    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_department_id", "documents", ["department_id"])
    op.create_index("ix_documents_owner_user_id", "documents", ["owner_user_id"])
    op.create_index("ix_documents_storage_scope", "documents", ["storage_scope"])
    op.create_index("ix_documents_visibility", "documents", ["visibility"])
    op.create_index("ix_documents_lifecycle_status", "documents", ["lifecycle_status"])
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_chunks_document_version_id", "document_chunks", ["document_version_id"])
    op.create_index("ix_indexing_jobs_document_version_id", "indexing_jobs", ["document_version_id"])
    op.create_index("ix_indexing_jobs_content_hash", "indexing_jobs", ["content_hash"])
    op.execute(
        "CREATE UNIQUE INDEX uq_indexing_jobs_active_document_version "
        "ON indexing_jobs (document_version_id) "
        "WHERE document_version_id IS NOT NULL AND status IN ('pending', 'running')"
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])

    op.create_check_constraint(
        "ck_documents_storage_scope",
        "documents",
        "storage_scope in ('enterprise', 'personal')",
    )
    op.create_check_constraint(
        "ck_documents_visibility",
        "documents",
        "visibility in ('private', 'department', 'enterprise', 'restricted')",
    )
    op.create_check_constraint(
        "ck_documents_lifecycle_status",
        "documents",
        "lifecycle_status in ('pending', 'indexing', 'indexed', 'failed', 'archived', 'deleted')",
    )
    op.create_check_constraint(
        "ck_documents_source_type",
        "documents",
        "source_type in ('corpus_sync', 'user_upload', 'system_import', 'backup_sync')",
    )
    op.create_check_constraint(
        "ck_documents_personal_owner_required",
        "documents",
        "(storage_scope <> 'personal') OR owner_user_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_documents_personal_private_visibility",
        "documents",
        "(storage_scope <> 'personal') OR visibility = 'private'",
    )
    op.create_check_constraint(
        "ck_documents_department_required",
        "documents",
        "department_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_document_versions_status",
        "document_versions",
        "status in ('pending', 'indexing', 'indexed', 'failed', 'archived')",
    )
    op.create_check_constraint(
        "ck_document_permissions_subject",
        "document_permissions",
        "(subject_type IS NULL AND subject_id IS NULL) OR (subject_type in ('user', 'role', 'department') AND subject_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_document_permissions_permission",
        "document_permissions",
        "permission in ('view', 'edit', 'manage', 'delete')",
    )
    op.create_check_constraint(
        "ck_indexing_jobs_status",
        "indexing_jobs",
        "status in ('pending', 'running', 'succeeded', 'failed', 'skipped')",
    )

    op.alter_column("documents", "organization_id", existing_type=UUID_TYPE, nullable=False)
    op.alter_column("documents", "department_id", existing_type=UUID_TYPE, nullable=False)
    op.alter_column("documents", "storage_scope", existing_type=sa.Text(), nullable=False)
    op.alter_column("documents", "visibility", existing_type=sa.Text(), nullable=False)
    op.alter_column("documents", "lifecycle_status", existing_type=sa.Text(), nullable=False)
    op.alter_column("documents", "source_type", existing_type=sa.Text(), nullable=False)
    op.alter_column("document_versions", "status", existing_type=sa.Text(), nullable=False)
    op.alter_column("document_permissions", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("indexing_jobs", "attempts", existing_type=sa.Integer(), nullable=False)
    op.alter_column("indexing_jobs", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("indexing_jobs", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    op.drop_constraint("ck_indexing_jobs_status", "indexing_jobs", type_="check")
    op.drop_constraint("ck_document_permissions_permission", "document_permissions", type_="check")
    op.drop_constraint("ck_document_permissions_subject", "document_permissions", type_="check")
    op.drop_constraint("ck_document_versions_status", "document_versions", type_="check")
    op.drop_constraint("ck_documents_department_required", "documents", type_="check")
    op.drop_constraint("ck_documents_personal_private_visibility", "documents", type_="check")
    op.drop_constraint("ck_documents_personal_owner_required", "documents", type_="check")
    op.drop_constraint("ck_documents_source_type", "documents", type_="check")
    op.drop_constraint("ck_documents_lifecycle_status", "documents", type_="check")
    op.drop_constraint("ck_documents_visibility", "documents", type_="check")
    op.drop_constraint("ck_documents_storage_scope", "documents", type_="check")

    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("uq_indexing_jobs_active_document_version", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_content_hash", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_document_version_id", table_name="indexing_jobs")
    op.drop_index("ix_document_chunks_document_version_id", table_name="document_chunks")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_index("ix_documents_lifecycle_status", table_name="documents")
    op.drop_index("ix_documents_visibility", table_name="documents")
    op.drop_index("ix_documents_storage_scope", table_name="documents")
    op.drop_index("ix_documents_owner_user_id", table_name="documents")
    op.drop_index("ix_documents_department_id", table_name="documents")
    op.drop_index("ix_documents_organization_id", table_name="documents")

    op.drop_constraint("fk_audit_events_actor_user_id", "audit_events", type_="foreignkey")
    op.drop_column("audit_events", "error_detail")
    op.drop_column("audit_events", "reason")
    op.drop_column("audit_events", "status")
    op.drop_column("audit_events", "user_agent")
    op.drop_column("audit_events", "ip_address")
    op.drop_column("audit_events", "after")
    op.drop_column("audit_events", "before")
    op.drop_column("audit_events", "actor_user_id")

    op.drop_constraint("fk_indexing_jobs_document_version_id", "indexing_jobs", type_="foreignkey")
    op.drop_column("indexing_jobs", "updated_at")
    op.drop_column("indexing_jobs", "created_at")
    op.drop_column("indexing_jobs", "attempts")
    op.drop_column("indexing_jobs", "document_version_id")
    op.execute(
        "CREATE UNIQUE INDEX uq_indexing_jobs_active_document_version "
        "ON indexing_jobs (document_id, content_hash) "
        "WHERE status IN ('pending', 'running')"
    )

    op.drop_constraint("fk_document_permissions_created_by_user_id", "document_permissions", type_="foreignkey")
    op.drop_column("document_permissions", "updated_at")
    op.drop_column("document_permissions", "created_by_user_id")
    op.drop_column("document_permissions", "expires_at")
    op.drop_column("document_permissions", "subject_id")
    op.drop_column("document_permissions", "subject_type")

    op.drop_constraint("fk_document_chunks_document_version_id", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "metadata")
    op.drop_column("document_chunks", "text")
    op.drop_column("document_chunks", "section")
    op.drop_column("document_chunks", "chunk_index")
    op.drop_column("document_chunks", "document_version_id")

    op.drop_constraint("fk_documents_current_version_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_document_versions_created_by_user_id", "document_versions", type_="foreignkey")
    op.drop_column("document_versions", "status")
    op.drop_column("document_versions", "created_by_user_id")
    op.drop_column("document_versions", "preview_artifact_path")
    op.drop_column("document_versions", "extracted_text_path")
    op.drop_column("document_versions", "mime_type")
    op.drop_column("document_versions", "storage_key")

    op.drop_constraint("fk_documents_deleted_by_user_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_updated_by_user_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_owner_user_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_department_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_organization_id", "documents", type_="foreignkey")
    op.drop_column("documents", "delete_reason")
    op.drop_column("documents", "deleted_by_user_id")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "current_version_id")
    op.drop_column("documents", "updated_by_user_id")
    op.drop_column("documents", "source_type")
    op.drop_column("documents", "lifecycle_status")
    op.drop_column("documents", "visibility")
    op.drop_column("documents", "owner_user_id")
    op.drop_column("documents", "storage_scope")
    op.drop_column("documents", "department_id")
    op.drop_column("documents", "organization_id")

    op.drop_constraint("uq_users_auth_provider_subject", "users", type_="unique")
    op.drop_column("users", "last_directory_sync_at")
    op.drop_column("users", "ldap_dn")
    op.drop_column("users", "external_directory_id")
    op.drop_column("users", "auth_subject")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "is_active")

    op.drop_table("department_role_assignments")
    op.drop_table("department_memberships")
    op.drop_table("role_permissions")
    op.drop_table("permissions")

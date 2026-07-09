"""workspace, groups, search metadata, and observability foundations

Revision ID: 20260710_0005
Revises: 20260710_0004
Create Date: 2026-07-10
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_0005"
down_revision = "20260710_0004"
branch_labels = None
depends_on = None


UUID_TYPE = postgresql.UUID(as_uuid=True)
JSONB_TYPE = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "workspaces",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("workspace_type", sa.Text(), nullable=False),
        sa.Column("owner_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspaces_organization_slug"),
        sa.CheckConstraint(
            "workspace_type in ('enterprise', 'personal', 'department', 'project', 'external', 'system')",
            name="ck_workspaces_workspace_type",
        ),
        sa.CheckConstraint(
            "visibility in ('private', 'department', 'enterprise', 'restricted')",
            name="ck_workspaces_visibility",
        ),
        sa.CheckConstraint(
            "(workspace_type <> 'personal') or owner_user_id is not null",
            name="ck_workspaces_personal_owner_required",
        ),
        sa.CheckConstraint(
            "(workspace_type <> 'personal') or visibility = 'private'",
            name="ck_workspaces_personal_private_visibility",
        ),
        sa.CheckConstraint(
            "(workspace_type <> 'department') or department_id is not null",
            name="ck_workspaces_department_required",
        ),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])
    op.create_index("ix_workspaces_workspace_type", "workspaces", ["workspace_type"])
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])
    op.create_index("ix_workspaces_department_id", "workspaces", ["department_id"])

    op.add_column("folders", sa.Column("workspace_id", UUID_TYPE, nullable=True))
    op.add_column("documents", sa.Column("workspace_id", UUID_TYPE, nullable=True))

    enterprise_workspace_rows = bind.execute(
        sa.text(
            """
            SELECT
                o.id AS organization_id,
                (
                    SELECT d.id
                    FROM departments d
                    WHERE d.organization_id = o.id
                    ORDER BY
                        CASE WHEN d.code = 'shared-knowledge' THEN 0 ELSE 1 END,
                        d.created_at,
                        d.id
                    LIMIT 1
                ) AS department_id
            FROM organizations o
            WHERE NOT EXISTS (
                SELECT 1
                FROM workspaces w
                WHERE w.organization_id = o.id
                  AND w.slug = 'enterprise'
            )
            """
        )
    ).mappings()
    for row in enterprise_workspace_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO workspaces (
                    id,
                    organization_id,
                    name,
                    slug,
                    workspace_type,
                    owner_user_id,
                    department_id,
                    visibility,
                    description,
                    metadata,
                    is_active,
                    created_by_user_id,
                    updated_by_user_id,
                    created_at,
                    updated_at,
                    deleted_at
                ) VALUES (
                    :id,
                    :organization_id,
                    :name,
                    :slug,
                    :workspace_type,
                    NULL,
                    :department_id,
                    :visibility,
                    :description,
                    NULL,
                    true,
                    NULL,
                    NULL,
                    now(),
                    now(),
                    NULL
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "organization_id": row["organization_id"],
                "name": "Enterprise Workspace",
                "slug": "enterprise",
                "workspace_type": "enterprise",
                "department_id": row["department_id"],
                "visibility": "enterprise",
                "description": "Default enterprise workspace for existing knowledge assets.",
            },
        )

    personal_workspace_rows = bind.execute(
        sa.text(
            """
            SELECT
                u.id AS user_id,
                u.organization_id,
                u.department_id,
                u.display_name
            FROM users u
            WHERE EXISTS (
                SELECT 1
                FROM documents d
                WHERE d.organization_id = u.organization_id
                  AND d.storage_scope = 'personal'
                  AND d.owner_user_id = u.id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM workspaces w
                WHERE w.organization_id = u.organization_id
                  AND w.workspace_type = 'personal'
                  AND w.owner_user_id = u.id
            )
            """
        )
    ).mappings()
    for row in personal_workspace_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO workspaces (
                    id,
                    organization_id,
                    name,
                    slug,
                    workspace_type,
                    owner_user_id,
                    department_id,
                    visibility,
                    description,
                    metadata,
                    is_active,
                    created_by_user_id,
                    updated_by_user_id,
                    created_at,
                    updated_at,
                    deleted_at
                ) VALUES (
                    :id,
                    :organization_id,
                    :name,
                    :slug,
                    'personal',
                    :owner_user_id,
                    :department_id,
                    'private',
                    :description,
                    NULL,
                    true,
                    :owner_user_id,
                    :owner_user_id,
                    now(),
                    now(),
                    NULL
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "organization_id": row["organization_id"],
                "name": f"{row['display_name']} Personal Workspace",
                "slug": f"personal-{str(row['user_id']).replace('-', '')}",
                "owner_user_id": row["user_id"],
                "department_id": row["department_id"],
                "description": "Auto-created personal workspace for existing owned personal documents.",
            },
        )

    bind.execute(
        sa.text(
            """
            UPDATE documents d
            SET workspace_id = CASE
                WHEN d.storage_scope = 'personal' AND d.owner_user_id is not null THEN (
                    SELECT w.id
                    FROM workspaces w
                    WHERE w.organization_id = d.organization_id
                      AND w.workspace_type = 'personal'
                      AND w.owner_user_id = d.owner_user_id
                    ORDER BY w.created_at, w.id
                    LIMIT 1
                )
                ELSE (
                    SELECT w.id
                    FROM workspaces w
                    WHERE w.organization_id = d.organization_id
                      AND w.workspace_type = 'enterprise'
                    ORDER BY w.created_at, w.id
                    LIMIT 1
                )
            END
            WHERE d.workspace_id is null
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE folders f
            SET workspace_id = COALESCE(
                (
                    SELECT d.workspace_id
                    FROM documents d
                    WHERE d.folder_id = f.id
                      AND d.workspace_id is not null
                    ORDER BY d.created_at, d.id
                    LIMIT 1
                ),
                (
                    SELECT w.id
                    FROM workspaces w
                    ORDER BY
                        CASE WHEN w.workspace_type = 'enterprise' THEN 0 ELSE 1 END,
                        w.created_at,
                        w.id
                    LIMIT 1
                )
            )
            WHERE f.workspace_id is null
            """
        )
    )
    while True:
        propagated = bind.execute(
            sa.text(
                """
                UPDATE folders AS child
                SET workspace_id = parent.workspace_id
                FROM folders AS parent
                WHERE child.workspace_id is null
                  AND child.parent_id = parent.id
                  AND parent.workspace_id is not null
                """
            )
        )
        if propagated.rowcount is None or propagated.rowcount <= 0:
            break

    bind.execute(
        sa.text(
            """
            UPDATE folders
            SET workspace_id = (
                SELECT w.id
                FROM workspaces w
                WHERE w.organization_id = (
                    SELECT o.id
                    FROM organizations o
                    ORDER BY o.created_at, o.id
                    LIMIT 1
                )
                  AND w.workspace_type = 'enterprise'
                ORDER BY w.created_at, w.id
                LIMIT 1
            )
            WHERE workspace_id is null
              AND (SELECT count(*) FROM organizations) = 1
            """
        )
    )

    remaining_folder_workspaces = bind.execute(
        sa.text("SELECT count(*) FROM folders WHERE workspace_id is null")
    ).scalar_one()
    if remaining_folder_workspaces:
        raise RuntimeError(
            "Unable to backfill workspace_id for all folders safely; "
            f"{remaining_folder_workspaces} folder rows remain unmapped."
        )

    op.create_foreign_key(
        "fk_folders_workspace_id",
        "folders",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_documents_workspace_id",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_folders_workspace_id", "folders", ["workspace_id"])
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.alter_column("folders", "workspace_id", existing_type=UUID_TYPE, nullable=False)
    op.alter_column("documents", "workspace_id", existing_type=UUID_TYPE, nullable=False)

    op.create_table(
        "groups",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("group_type", sa.Text(), nullable=False),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "slug", name="uq_groups_organization_slug"),
        sa.CheckConstraint(
            "group_type in ('team', 'committee', 'shift', 'contractor', 'custom')",
            name="ck_groups_group_type",
        ),
    )
    op.create_index("ix_groups_organization_id", "groups", ["organization_id"])
    op.create_index("ix_groups_department_id", "groups", ["department_id"])

    op.create_table(
        "group_memberships",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("group_id", UUID_TYPE, sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_label", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"])
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])
    op.create_index(
        "uq_group_memberships_active_group_user",
        "group_memberships",
        ["group_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.add_column("folder_permissions", sa.Column("group_id", UUID_TYPE, nullable=True))
    op.add_column("folder_permissions", sa.Column("subject_type", sa.Text(), nullable=True))
    op.add_column("folder_permissions", sa.Column("subject_id", UUID_TYPE, nullable=True))
    op.add_column("folder_permissions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("folder_permissions", sa.Column("created_by_user_id", UUID_TYPE, nullable=True))
    op.add_column(
        "folder_permissions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_foreign_key(
        "fk_folder_permissions_group_id",
        "folder_permissions",
        "groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_folder_permissions_created_by_user_id",
        "folder_permissions",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE folder_permissions
        SET subject_type = CASE
                WHEN user_id is not null THEN 'user'
                WHEN role_id is not null THEN 'role'
                WHEN department_id is not null THEN 'department'
                WHEN group_id is not null THEN 'group'
                ELSE subject_type
            END,
            subject_id = COALESCE(user_id, role_id, department_id, group_id),
            updated_at = COALESCE(updated_at, created_at)
        WHERE subject_type is null OR subject_id is null OR updated_at is null
        """
    )
    op.alter_column("folder_permissions", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.drop_constraint("ck_folder_permissions_principal", "folder_permissions", type_="check")
    op.create_check_constraint(
        "ck_folder_permissions_principal",
        "folder_permissions",
        "user_id is not null or department_id is not null or role_id is not null or group_id is not null",
    )
    op.create_check_constraint(
        "ck_folder_permissions_subject",
        "folder_permissions",
        "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department', 'group') and subject_id is not null)",
    )
    op.create_check_constraint(
        "ck_folder_permissions_permission",
        "folder_permissions",
        "permission in ('view', 'edit', 'manage', 'delete')",
    )

    op.add_column("document_permissions", sa.Column("group_id", UUID_TYPE, nullable=True))
    op.create_foreign_key(
        "fk_document_permissions_group_id",
        "document_permissions",
        "groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        UPDATE document_permissions
        SET subject_type = CASE
                WHEN user_id is not null THEN 'user'
                WHEN role_id is not null THEN 'role'
                WHEN department_id is not null THEN 'department'
                WHEN group_id is not null THEN 'group'
                ELSE subject_type
            END,
            subject_id = COALESCE(user_id, role_id, department_id, group_id)
        WHERE subject_type is null OR subject_id is null
        """
    )
    op.drop_constraint("ck_document_permissions_principal", "document_permissions", type_="check")
    op.drop_constraint("ck_document_permissions_subject", "document_permissions", type_="check")
    op.create_check_constraint(
        "ck_document_permissions_principal",
        "document_permissions",
        "user_id is not null or department_id is not null or role_id is not null or group_id is not null",
    )
    op.create_check_constraint(
        "ck_document_permissions_subject",
        "document_permissions",
        "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department', 'group') and subject_id is not null)",
    )

    op.create_table(
        "workspace_permissions",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("workspace_id", UUID_TYPE, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("department_id", UUID_TYPE, sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_id", UUID_TYPE, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("group_id", UUID_TYPE, sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True),
        sa.Column("subject_type", sa.Text(), nullable=True),
        sa.Column("subject_id", UUID_TYPE, nullable=True),
        sa.Column("permission", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "user_id is not null or department_id is not null or role_id is not null or group_id is not null",
            name="ck_workspace_permissions_principal",
        ),
        sa.CheckConstraint(
            "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department', 'group') and subject_id is not null)",
            name="ck_workspace_permissions_subject",
        ),
        sa.CheckConstraint(
            "permission in ('view', 'edit', 'manage', 'delete')",
            name="ck_workspace_permissions_permission",
        ),
    )

    op.create_table(
        "document_relationships",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", UUID_TYPE, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_document_id", UUID_TYPE, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        sa.Column("created_by_user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationships_pair_type",
        ),
        sa.CheckConstraint(
            "relationship_type in ('related', 'references', 'supersedes', 'duplicate', 'derived_from', 'translation_of', 'attachment_of')",
            name="ck_document_relationships_relationship_type",
        ),
        sa.CheckConstraint(
            "source_document_id <> target_document_id",
            name="ck_document_relationships_distinct_documents",
        ),
    )
    op.create_index("ix_document_relationships_source_document_id", "document_relationships", ["source_document_id"])
    op.create_index("ix_document_relationships_target_document_id", "document_relationships", ["target_document_id"])
    op.create_index("ix_document_relationships_relationship_type", "document_relationships", ["relationship_type"])

    op.create_table(
        "document_search_metadata",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("document_id", UUID_TYPE, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("keywords", JSONB_TYPE, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("entities", JSONB_TYPE, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("topics", JSONB_TYPE, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("ocr_quality", sa.Float(), nullable=True),
        sa.Column("classification", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("document_id", name="uq_document_search_metadata_document_id"),
    )
    search_metadata_rows = bind.execute(
        sa.text(
            """
            SELECT
                d.id AS document_id,
                d.organization_id,
                d.name
            FROM documents d
            WHERE NOT EXISTS (
                SELECT 1
                FROM document_search_metadata m
                WHERE m.document_id = d.id
            )
            """
        )
    ).mappings()
    for row in search_metadata_rows:
        normalized_title = " ".join(str(row["name"]).lower().replace("-", " ").replace("_", " ").split())
        bind.execute(
            sa.text(
                """
                INSERT INTO document_search_metadata (
                    id,
                    document_id,
                    organization_id,
                    title,
                    normalized_title,
                    summary,
                    keywords,
                    entities,
                    topics,
                    language,
                    ocr_quality,
                    classification,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :document_id,
                    :organization_id,
                    :title,
                    :normalized_title,
                    NULL,
                    '[]'::jsonb,
                    '[]'::jsonb,
                    '[]'::jsonb,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    now(),
                    now()
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "document_id": row["document_id"],
                "organization_id": row["organization_id"],
                "title": row["name"],
                "normalized_title": normalized_title,
            },
        )

    op.create_table(
        "retrieval_events",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chat_session_id", UUID_TYPE, sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieval_scope", sa.Text(), nullable=True),
        sa.Column("selected_document_ids", JSONB_TYPE, nullable=True),
        sa.Column("selected_folder_ids", JSONB_TYPE, nullable=True),
        sa.Column("retrieved_document_ids", JSONB_TYPE, nullable=True),
        sa.Column("retrieved_chunk_ids", JSONB_TYPE, nullable=True),
        sa.Column("reranker_scores", JSONB_TYPE, nullable=True),
        sa.Column("filters_applied", JSONB_TYPE, nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_retrieval_events_user_id", "retrieval_events", ["user_id"])
    op.create_index("ix_retrieval_events_chat_session_id", "retrieval_events", ["chat_session_id"])
    op.create_index("ix_retrieval_events_created_at", "retrieval_events", ["created_at"])

    op.create_table(
        "conversation_summaries",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column("chat_session_id", UUID_TYPE, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID_TYPE, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary_type", sa.Text(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "summary_type in ('running', 'final', 'topic', 'handoff')",
            name="ck_conversation_summaries_summary_type",
        ),
    )
    op.create_index("ix_conversation_summaries_chat_session_id", "conversation_summaries", ["chat_session_id"])


def downgrade() -> None:
    op.drop_index("ix_conversation_summaries_chat_session_id", table_name="conversation_summaries")
    op.drop_table("conversation_summaries")

    op.drop_index("ix_retrieval_events_created_at", table_name="retrieval_events")
    op.drop_index("ix_retrieval_events_chat_session_id", table_name="retrieval_events")
    op.drop_index("ix_retrieval_events_user_id", table_name="retrieval_events")
    op.drop_table("retrieval_events")

    op.drop_table("document_search_metadata")

    op.drop_index("ix_document_relationships_relationship_type", table_name="document_relationships")
    op.drop_index("ix_document_relationships_target_document_id", table_name="document_relationships")
    op.drop_index("ix_document_relationships_source_document_id", table_name="document_relationships")
    op.drop_table("document_relationships")

    op.drop_table("workspace_permissions")

    op.drop_constraint("ck_document_permissions_subject", "document_permissions", type_="check")
    op.drop_constraint("ck_document_permissions_principal", "document_permissions", type_="check")
    op.create_check_constraint(
        "ck_document_permissions_principal",
        "document_permissions",
        "user_id is not null or department_id is not null or role_id is not null",
    )
    op.create_check_constraint(
        "ck_document_permissions_subject",
        "document_permissions",
        "(subject_type is null and subject_id is null) or (subject_type in ('user', 'role', 'department') and subject_id is not null)",
    )
    op.drop_constraint("fk_document_permissions_group_id", "document_permissions", type_="foreignkey")
    op.drop_column("document_permissions", "group_id")

    op.drop_constraint("ck_folder_permissions_permission", "folder_permissions", type_="check")
    op.drop_constraint("ck_folder_permissions_subject", "folder_permissions", type_="check")
    op.drop_constraint("ck_folder_permissions_principal", "folder_permissions", type_="check")
    op.create_check_constraint(
        "ck_folder_permissions_principal",
        "folder_permissions",
        "user_id is not null or department_id is not null or role_id is not null",
    )
    op.drop_constraint("fk_folder_permissions_created_by_user_id", "folder_permissions", type_="foreignkey")
    op.drop_constraint("fk_folder_permissions_group_id", "folder_permissions", type_="foreignkey")
    op.drop_column("folder_permissions", "updated_at")
    op.drop_column("folder_permissions", "created_by_user_id")
    op.drop_column("folder_permissions", "expires_at")
    op.drop_column("folder_permissions", "subject_id")
    op.drop_column("folder_permissions", "subject_type")
    op.drop_column("folder_permissions", "group_id")

    op.drop_index("uq_group_memberships_active_group_user", table_name="group_memberships")
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")
    op.drop_table("group_memberships")

    op.drop_index("ix_groups_department_id", table_name="groups")
    op.drop_index("ix_groups_organization_id", table_name="groups")
    op.drop_table("groups")

    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_constraint("fk_documents_workspace_id", "documents", type_="foreignkey")
    op.drop_column("documents", "workspace_id")

    op.drop_index("ix_folders_workspace_id", table_name="folders")
    op.drop_constraint("fk_folders_workspace_id", "folders", type_="foreignkey")
    op.drop_column("folders", "workspace_id")

    op.drop_index("ix_workspaces_department_id", table_name="workspaces")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_index("ix_workspaces_workspace_type", table_name="workspaces")
    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_table("workspaces")

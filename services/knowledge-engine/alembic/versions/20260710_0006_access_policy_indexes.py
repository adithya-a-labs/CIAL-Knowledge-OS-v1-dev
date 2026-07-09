"""access policy support indexes

Revision ID: 20260710_0006
Revises: 20260710_0005
Create Date: 2026-07-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_0006"
down_revision = "20260710_0005"
branch_labels = None
depends_on = None


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    folder_permission_indexes = _index_names("folder_permissions")
    if "ix_folder_permissions_folder_id" not in folder_permission_indexes:
        op.create_index("ix_folder_permissions_folder_id", "folder_permissions", ["folder_id"])
    if "ix_folder_permissions_subject_type_subject_id" not in folder_permission_indexes:
        op.create_index(
            "ix_folder_permissions_subject_type_subject_id",
            "folder_permissions",
            ["subject_type", "subject_id"],
        )

    document_permission_indexes = _index_names("document_permissions")
    if "ix_document_permissions_document_id" not in document_permission_indexes:
        op.create_index("ix_document_permissions_document_id", "document_permissions", ["document_id"])
    if "ix_document_permissions_subject_type_subject_id" not in document_permission_indexes:
        op.create_index(
            "ix_document_permissions_subject_type_subject_id",
            "document_permissions",
            ["subject_type", "subject_id"],
        )

    workspace_permission_indexes = _index_names("workspace_permissions")
    if "ix_workspace_permissions_workspace_id" not in workspace_permission_indexes:
        op.create_index("ix_workspace_permissions_workspace_id", "workspace_permissions", ["workspace_id"])
    if "ix_workspace_permissions_subject_type_subject_id" not in workspace_permission_indexes:
        op.create_index(
            "ix_workspace_permissions_subject_type_subject_id",
            "workspace_permissions",
            ["subject_type", "subject_id"],
        )


def downgrade() -> None:
    workspace_permission_indexes = _index_names("workspace_permissions")
    if "ix_workspace_permissions_subject_type_subject_id" in workspace_permission_indexes:
        op.drop_index("ix_workspace_permissions_subject_type_subject_id", table_name="workspace_permissions")
    if "ix_workspace_permissions_workspace_id" in workspace_permission_indexes:
        op.drop_index("ix_workspace_permissions_workspace_id", table_name="workspace_permissions")

    document_permission_indexes = _index_names("document_permissions")
    if "ix_document_permissions_subject_type_subject_id" in document_permission_indexes:
        op.drop_index("ix_document_permissions_subject_type_subject_id", table_name="document_permissions")
    if "ix_document_permissions_document_id" in document_permission_indexes:
        op.drop_index("ix_document_permissions_document_id", table_name="document_permissions")

    folder_permission_indexes = _index_names("folder_permissions")
    if "ix_folder_permissions_subject_type_subject_id" in folder_permission_indexes:
        op.drop_index("ix_folder_permissions_subject_type_subject_id", table_name="folder_permissions")
    if "ix_folder_permissions_folder_id" in folder_permission_indexes:
        op.drop_index("ix_folder_permissions_folder_id", table_name="folder_permissions")

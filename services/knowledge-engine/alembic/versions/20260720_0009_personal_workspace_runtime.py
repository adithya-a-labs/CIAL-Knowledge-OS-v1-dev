"""personal workspace runtime metadata

Revision ID: 20260720_0009
Revises: 20260710_0008
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260720_0009"
down_revision = "20260710_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("folders", sa.Column("system_key", sa.Text(), nullable=True))
    op.create_index("ix_folders_workspace_system_key", "folders", ["workspace_id", "system_key"], unique=True, postgresql_where=sa.text("system_key IS NOT NULL"))
    op.add_column("documents", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.drop_constraint("ck_documents_source_type", "documents", type_="check")
    op.create_check_constraint("ck_documents_source_type", "documents", "source_type in ('corpus_sync', 'user_upload', 'chat_upload', 'system_import', 'backup_sync')")
    op.create_table(
        "workspace_user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user_preferences_workspace_user"),
    )
    op.create_index("ix_workspace_user_preferences_user_id", "workspace_user_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_user_preferences_user_id", table_name="workspace_user_preferences")
    op.drop_table("workspace_user_preferences")
    op.drop_constraint("ck_documents_source_type", "documents", type_="check")
    op.create_check_constraint("ck_documents_source_type", "documents", "source_type in ('corpus_sync', 'user_upload', 'system_import', 'backup_sync')")
    op.drop_column("documents", "metadata")
    op.drop_index("ix_folders_workspace_system_key", table_name="folders")
    op.drop_column("folders", "system_key")

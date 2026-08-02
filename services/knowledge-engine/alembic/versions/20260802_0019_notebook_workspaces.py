"""persistent personal notebook workspaces

Revision ID: 20260802_0019
Revises: 20260729_0018
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260802_0019"
down_revision = "20260729_0018"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "notebooks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("visibility", sa.Text(), server_default="private", nullable=False),
        sa.Column("lifecycle_status", sa.Text(), server_default="active", nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("visibility = 'private'", name="ck_notebooks_personal_private"),
        sa.CheckConstraint("lifecycle_status in ('active','archived','deleted')", name="ck_notebooks_lifecycle"),
    )
    op.create_index("ix_notebooks_owner_updated", "notebooks", ["owner_user_id", "updated_at"])
    op.create_index("ix_notebooks_workspace", "notebooks", ["workspace_id"])

    op.create_table(
        "notebook_sources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("notebook_id", UUID, sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("note_id", UUID, sa.ForeignKey("notes.id", ondelete="CASCADE")),
        sa.Column("summary_artifact_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="CASCADE")),
        sa.Column("attached_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_default_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type in ('document','note','summary')", name="ck_notebook_sources_type"),
        sa.CheckConstraint("position >= 0", name="ck_notebook_sources_position"),
        sa.CheckConstraint("num_nonnulls(document_id,note_id,summary_artifact_id) = 1", name="ck_notebook_sources_one_target"),
        sa.CheckConstraint("(source_type='document') = (document_id is not null)", name="ck_notebook_sources_document_target"),
        sa.CheckConstraint("(source_type='note') = (note_id is not null)", name="ck_notebook_sources_note_target"),
        sa.CheckConstraint("(source_type='summary') = (summary_artifact_id is not null)", name="ck_notebook_sources_summary_target"),
    )
    op.create_index("ix_notebook_sources_notebook_position", "notebook_sources", ["notebook_id", "position"])
    op.create_index("uq_notebook_sources_document", "notebook_sources", ["notebook_id", "document_id"], unique=True, postgresql_where=sa.text("document_id is not null"))
    op.create_index("uq_notebook_sources_note", "notebook_sources", ["notebook_id", "note_id"], unique=True, postgresql_where=sa.text("note_id is not null"))
    op.create_index("uq_notebook_sources_summary", "notebook_sources", ["notebook_id", "summary_artifact_id"], unique=True, postgresql_where=sa.text("summary_artifact_id is not null"))

    op.create_table(
        "notebook_sessions",
        sa.Column("notebook_id", UUID, sa.ForeignKey("notebooks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("chat_session_id", UUID, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "notebook_artifacts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("notebook_id", UUID, sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_snapshot", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("summary_artifact_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="SET NULL")),
        sa.Column("note_id", UUID, sa.ForeignKey("notes.id", ondelete="SET NULL")),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("artifact_type in ('executive','detailed','key_points','action_items','comparison')", name="ck_notebook_artifacts_type"),
        sa.CheckConstraint("status in ('pending','queued','running','completed','failed','cancelled')", name="ck_notebook_artifacts_status"),
    )
    op.create_index("ix_notebook_artifacts_notebook_created", "notebook_artifacts", ["notebook_id", "created_at"])
    op.create_index("uq_notebook_artifacts_summary", "notebook_artifacts", ["notebook_id", "summary_artifact_id"], unique=True, postgresql_where=sa.text("summary_artifact_id is not null"))


def downgrade() -> None:
    op.drop_table("notebook_artifacts")
    op.drop_table("notebook_sessions")
    op.drop_table("notebook_sources")
    op.drop_table("notebooks")

"""durable assistant export jobs

Revision ID: 20260720_0010
Revises: 20260720_0009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260720_0010"
down_revision = "20260720_0009"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.Text(), nullable=False), sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("progress_stage", sa.Text(), server_default="queued", nullable=False), sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("title", sa.Text(), nullable=False), sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=False), sa.Column("source_content_hash", sa.Text(), nullable=False),
        sa.Column("output_filename", sa.Text()), sa.Column("output_mime_type", sa.Text()), sa.Column("storage_key", sa.Text()), sa.Column("preview_storage_key", sa.Text()),
        sa.Column("file_size_bytes", sa.Integer()), sa.Column("error_code", sa.Text()), sa.Column("safe_error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("downloaded_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("format in ('pdf', 'docx')", name="ck_export_jobs_format"),
        sa.CheckConstraint("status in ('queued','processing','ready','failed','expired','cancelled')", name="ck_export_jobs_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    for name, column in (("user_id","user_id"),("status","status"),("created_at","created_at"),("expires_at","expires_at")):
        op.create_index(f"ix_export_jobs_{name}", "export_jobs", [column])

def downgrade() -> None:
    op.drop_table("export_jobs")

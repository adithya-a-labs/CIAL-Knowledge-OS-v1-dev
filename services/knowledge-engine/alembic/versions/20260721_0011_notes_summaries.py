"""private notes and immutable summary artifacts

Revision ID: 20260721_0011
Revises: 20260720_0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260721_0011"
down_revision = "20260720_0010"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table("notes",
        sa.Column("id", UUID, primary_key=True), sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), sa.Column("owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), server_default="Untitled", nullable=False), sa.Column("content_json", JSONB), sa.Column("content_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("content_format", sa.Text(), server_default="markdown", nullable=False), sa.Column("plain_text", sa.Text(), server_default="", nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default="false", nullable=False), sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint("revision >= 1", name="ck_notes_revision"), sa.CheckConstraint("length(trim(content_format)) > 0", name="ck_notes_content_format"))
    op.create_index("ix_notes_owner_workspace_updated", "notes", ["owner_user_id", "workspace_id", "updated_at"])
    op.create_index("ix_notes_owner_pinned", "notes", ["owner_user_id"], postgresql_where=sa.text("is_pinned = true and deleted_at is null"))
    op.create_index("ix_notes_owner_archived", "notes", ["owner_user_id"], postgresql_where=sa.text("is_archived = true and deleted_at is null"))
    op.execute("CREATE INDEX ix_notes_search ON notes USING gin (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(plain_text,'')))")
    op.create_table("note_versions", sa.Column("id", UUID, primary_key=True), sa.Column("note_id", UUID, sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("content_json", JSONB), sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.UniqueConstraint("note_id", "revision", name="uq_note_versions_note_revision"))
    op.create_index("ix_note_versions_note_id", "note_versions", ["note_id"])
    op.create_table("note_tags", sa.Column("id", UUID, primary_key=True), sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.Text(), nullable=False), sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("owner_user_id", "normalized_name", name="uq_note_tags_owner_name"))
    op.create_index("ix_note_tags_workspace_owner", "note_tags", ["workspace_id", "owner_user_id"])
    op.create_table("note_tag_links", sa.Column("note_id", UUID, sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True), sa.Column("tag_id", UUID, sa.ForeignKey("note_tags.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("note_document_links", sa.Column("note_id", UUID, sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True), sa.Column("document_id", UUID, sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    op.create_table("summary_artifacts", sa.Column("id", UUID, primary_key=True), sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), sa.Column("owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_summary_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="SET NULL")), sa.Column("title", sa.Text(), nullable=False), sa.Column("summary_type", sa.Text(), nullable=False),
        sa.Column("summary_length", sa.Text(), nullable=False), sa.Column("multi_document_mode", sa.Text(), nullable=False), sa.Column("custom_instructions", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False), sa.Column("content_markdown", sa.Text()), sa.Column("content_json", JSONB), sa.Column("prompt_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False), sa.Column("model_name", sa.Text()), sa.Column("source_fingerprint", sa.Text(), nullable=False),
        sa.Column("citation_count", sa.Integer(), server_default="0", nullable=False), sa.Column("document_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.Column("error_code", sa.Text()), sa.Column("error_message_safe", sa.Text()),
        sa.CheckConstraint("summary_type in ('executive','detailed','key_points','action_items')", name="ck_summary_artifacts_type"), sa.CheckConstraint("summary_length in ('brief','standard','detailed')", name="ck_summary_artifacts_length"),
        sa.CheckConstraint("multi_document_mode in ('together','separate','compare')", name="ck_summary_artifacts_mode"), sa.CheckConstraint("status in ('pending','running','completed','failed','cancelled')", name="ck_summary_artifacts_status"))
    op.create_index("ix_summary_artifacts_owner_status_created", "summary_artifacts", ["owner_user_id", "status", "created_at"])
    op.create_table("summary_sources", sa.Column("id", UUID, primary_key=True), sa.Column("summary_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("source_type", sa.Text(), nullable=False), sa.Column("source_id", UUID),
        sa.Column("document_version_id", UUID, sa.ForeignKey("document_versions.id", ondelete="RESTRICT")), sa.Column("note_version_id", UUID, sa.ForeignKey("note_versions.id", ondelete="RESTRICT")),
        sa.Column("chat_session_id", UUID, sa.ForeignKey("chat_sessions.id", ondelete="RESTRICT")), sa.Column("title", sa.Text(), nullable=False), sa.Column("content_hash", sa.Text(), nullable=False), sa.Column("source_snapshot", JSONB, nullable=False),
        sa.UniqueConstraint("summary_id", "ordinal", name="uq_summary_sources_ordinal"))
    op.create_table("summary_citations", sa.Column("id", UUID, primary_key=True), sa.Column("summary_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_id", sa.Text(), nullable=False), sa.Column("source_record_id", UUID, sa.ForeignKey("summary_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("documents.id", ondelete="SET NULL")), sa.Column("note_id", UUID, sa.ForeignKey("notes.id", ondelete="SET NULL")),
        sa.Column("page_number", sa.Integer()), sa.Column("section", sa.Text()), sa.Column("chunk_id", sa.Text()), sa.Column("excerpt", sa.Text()), sa.Column("metadata", JSONB),
        sa.UniqueConstraint("summary_id", "citation_id", name="uq_summary_citations_id"))


def downgrade() -> None:
    for table in ("summary_citations", "summary_sources", "summary_artifacts", "note_document_links", "note_tag_links", "note_tags", "note_versions", "notes"):
        op.drop_table(table)

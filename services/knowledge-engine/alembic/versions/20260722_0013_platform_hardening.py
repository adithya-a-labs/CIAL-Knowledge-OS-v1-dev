"""platform hardening foundations

Revision ID: 20260722_0013
Revises: 20260721_0012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260722_0013"
down_revision = "20260721_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "indexing_jobs",
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_indexing_jobs_status_available", "indexing_jobs", ["status", "available_at"])
    op.add_column("chat_sessions", sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")))
    op.add_column("chat_sessions", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL")))
    op.add_column("chat_sessions", sa.Column("origin", sa.Text(), server_default="assistant", nullable=False))
    op.add_column("chat_sessions", sa.Column("created_from_document", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")))
    op.add_column("chat_sessions", sa.Column("context_scope", sa.Text(), server_default="all_accessible", nullable=False))
    op.add_column("chat_sessions", sa.Column("selected_document_ids", postgresql.JSONB()))
    op.add_column("chat_sessions", sa.Column("selected_note_ids", postgresql.JSONB()))
    op.add_column("chat_sessions", sa.Column("context_snapshot", postgresql.JSONB()))
    op.create_check_constraint("ck_chat_sessions_origin", "chat_sessions", "origin in ('assistant','homepage','knowledge_center','global_search','saved_knowledge')")
    op.create_check_constraint("ck_chat_sessions_context_scope", "chat_sessions", "context_scope in ('all_accessible','selected_documents','selected_context')")
    op.create_table(
        "search_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_history_user_updated", "search_history", ["user_id", "updated_at"])
    op.create_index("ix_search_history_user_normalized", "search_history", ["user_id", "normalized_query"], unique=True)
    op.drop_constraint("ck_saved_knowledge_item_type", "saved_knowledge_items", type_="check")
    op.alter_column("saved_knowledge_items", "summary_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("saved_knowledge_items", sa.Column("source_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_messages.id", ondelete="SET NULL")))
    op.add_column("saved_knowledge_items", sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL")))
    op.add_column("saved_knowledge_items", sa.Column("description", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("body_markdown", sa.Text(), server_default="", nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("original_question", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("citation_snapshot", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("source_references", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("selected_document_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("context_scope", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("profile", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("model_name", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("prompt_version", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("collection", sa.Text()))
    op.add_column("saved_knowledge_items", sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("visibility", sa.Text(), server_default="private", nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("is_favorite", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("provenance_hash", sa.Text(), server_default="", nullable=False))
    op.add_column("saved_knowledge_items", sa.Column("state", sa.Text(), server_default="active", nullable=False))
    op.execute("UPDATE saved_knowledge_items sk SET body_markdown=coalesce(sa.content_markdown,''), prompt_version=sa.prompt_version, model_name=sa.model_name, provenance_hash=md5('summary:' || sk.summary_id::text) FROM summary_artifacts sa WHERE sa.id=sk.summary_id")
    op.create_check_constraint("ck_saved_knowledge_item_type", "saved_knowledge_items", "item_type in ('summary','answer')")
    op.create_check_constraint("ck_saved_knowledge_visibility", "saved_knowledge_items", "visibility in ('private','restricted')")
    op.create_check_constraint("ck_saved_knowledge_state", "saved_knowledge_items", "state in ('active','archived')")
    op.create_index("ix_saved_knowledge_owner_updated", "saved_knowledge_items", ["owner_user_id", "updated_at"])
    op.execute("CREATE INDEX ix_saved_knowledge_title_search ON saved_knowledge_items (owner_user_id, lower(title)) WHERE deleted_at IS NULL")
    op.create_table(
        "saved_knowledge_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("saved_knowledge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saved_knowledge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("citation_snapshot", postgresql.JSONB(), nullable=False), sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("saved_knowledge_id", "version", name="uq_saved_knowledge_versions_item_version"),
    )
    op.execute("INSERT INTO saved_knowledge_versions (id,saved_knowledge_id,version,title,description,body_markdown,citation_snapshot,tags,created_by_user_id) SELECT gen_random_uuid(),id,version,title,description,body_markdown,citation_snapshot,tags,owner_user_id FROM saved_knowledge_items")


def downgrade():
    op.drop_table("saved_knowledge_versions")
    op.execute("DELETE FROM saved_knowledge_items WHERE item_type='answer'")
    op.execute("DROP INDEX IF EXISTS ix_saved_knowledge_title_search")
    op.drop_index("ix_saved_knowledge_owner_updated", table_name="saved_knowledge_items")
    op.drop_constraint("ck_saved_knowledge_state", "saved_knowledge_items", type_="check")
    op.drop_constraint("ck_saved_knowledge_visibility", "saved_knowledge_items", type_="check")
    op.drop_constraint("ck_saved_knowledge_item_type", "saved_knowledge_items", type_="check")
    for column in ("state","provenance_hash","version","is_favorite","visibility","tags","collection","prompt_version","model_name","profile","context_scope","selected_document_ids","source_references","citation_snapshot","original_question","body_markdown","description","conversation_id","source_message_id"):
        op.drop_column("saved_knowledge_items", column)
    op.alter_column("saved_knowledge_items", "summary_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_check_constraint("ck_saved_knowledge_item_type", "saved_knowledge_items", "item_type = 'summary'")
    op.drop_table("search_history")
    op.drop_constraint("ck_chat_sessions_context_scope", "chat_sessions", type_="check")
    op.drop_constraint("ck_chat_sessions_origin", "chat_sessions", type_="check")
    for column in ("context_snapshot", "selected_note_ids", "selected_document_ids", "context_scope", "created_from_document", "origin", "workspace_id", "organization_id"):
        op.drop_column("chat_sessions", column)
    op.drop_index("ix_indexing_jobs_status_available", table_name="indexing_jobs")
    op.drop_column("indexing_jobs", "available_at")

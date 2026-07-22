"""note index state, saved summaries, and grounded follow-up bindings

Revision ID: 20260721_0012
Revises: 20260721_0011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="20260721_0012"; down_revision="20260721_0011"; branch_labels=None; depends_on=None
UUID=postgresql.UUID(as_uuid=True); JSONB=postgresql.JSONB()

def upgrade():
    op.create_table("note_index_states",sa.Column("note_id",UUID,sa.ForeignKey("notes.id",ondelete="CASCADE"),primary_key=True),sa.Column("indexed_revision",sa.Integer()),sa.Column("status",sa.Text(),server_default="pending",nullable=False),sa.Column("content_hash",sa.Text()),sa.Column("point_count",sa.Integer(),server_default="0",nullable=False),sa.Column("last_error",sa.Text()),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.CheckConstraint("status in ('pending','indexing','indexed','failed','removed')",name="ck_note_index_states_status"))
    op.create_table("saved_knowledge_items",sa.Column("id",UUID,primary_key=True),sa.Column("organization_id",UUID,sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("workspace_id",UUID,sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),sa.Column("owner_user_id",UUID,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("item_type",sa.Text(),server_default="summary",nullable=False),sa.Column("summary_id",UUID,sa.ForeignKey("summary_artifacts.id",ondelete="CASCADE"),nullable=False),sa.Column("title",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("owner_user_id","summary_id",name="uq_saved_knowledge_owner_summary"),sa.CheckConstraint("item_type = 'summary'",name="ck_saved_knowledge_item_type"))
    op.create_index("ix_saved_knowledge_owner_created","saved_knowledge_items",["owner_user_id","created_at"])
    op.create_table("summary_conversation_bindings",sa.Column("id",UUID,primary_key=True),sa.Column("summary_id",UUID,sa.ForeignKey("summary_artifacts.id",ondelete="CASCADE"),nullable=False),sa.Column("chat_session_id",UUID,sa.ForeignKey("chat_sessions.id",ondelete="CASCADE"),nullable=False),sa.Column("owner_user_id",UUID,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("mode",sa.Text(),server_default="original_versions",nullable=False),sa.Column("source_binding",JSONB,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("summary_id","chat_session_id",name="uq_summary_conversation_binding"),sa.CheckConstraint("mode in ('original_versions','latest_versions')",name="ck_summary_conversation_binding_mode"))

def downgrade():
    op.drop_table("summary_conversation_bindings");op.drop_table("saved_knowledge_items");op.drop_table("note_index_states")

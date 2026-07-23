"""harden document summary generation checkpoints

Revision ID: 20260724_0015
Revises: 20260722_0014
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260724_0015"
down_revision = "20260722_0014"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.add_column("summary_map_results", sa.Column("child_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("summary_map_results", sa.Column("prompt_name", sa.Text(), server_default="", nullable=False))
    op.add_column("summary_map_results", sa.Column("prompt_version", sa.Text(), server_default="", nullable=False))
    op.add_column("summary_map_results", sa.Column("schema_name", sa.Text(), server_default="", nullable=False))
    op.add_column("summary_map_results", sa.Column("schema_version", sa.Text(), server_default="", nullable=False))
    op.add_column("summary_map_results", sa.Column("model_name", sa.Text()))
    op.add_column("summary_map_results", sa.Column("budgets", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("summary_map_results", sa.Column("status", sa.Text(), server_default="completed", nullable=False))
    op.create_check_constraint(
        "ck_summary_map_results_status", "summary_map_results",
        "status in ('running','completed','failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_summary_map_results_status", "summary_map_results", type_="check")
    for column in (
        "status", "budgets", "model_name", "schema_version", "schema_name",
        "prompt_version", "prompt_name", "child_ids",
    ):
        op.drop_column("summary_map_results", column)

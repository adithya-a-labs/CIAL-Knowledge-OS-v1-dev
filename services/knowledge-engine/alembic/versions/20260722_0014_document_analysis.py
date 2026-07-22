"""first-class full-document analysis artifacts

Revision ID: 20260722_0014
Revises: 20260722_0013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260722_0014"
down_revision = "20260722_0013"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.drop_constraint("ck_summary_artifacts_type", "summary_artifacts", type_="check")
    op.drop_constraint("ck_summary_artifacts_status", "summary_artifacts", type_="check")
    op.create_check_constraint(
        "ck_summary_artifacts_type", "summary_artifacts",
        "summary_type in ('executive','overview','detailed','key_points','action_items')",
    )
    op.create_check_constraint(
        "ck_summary_artifacts_status", "summary_artifacts",
        "status in ('pending','queued','running','completed','failed','cancelled','stale')",
    )
    op.add_column("summary_artifacts", sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("summary_artifacts", sa.Column("document_id", UUID, sa.ForeignKey("documents.id", ondelete="SET NULL")))
    op.add_column("summary_artifacts", sa.Column("document_version_id", UUID, sa.ForeignKey("document_versions.id", ondelete="RESTRICT")))
    op.add_column("summary_artifacts", sa.Column("citation_snapshot", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("summary_artifacts", sa.Column("reuse_key", sa.Text()))
    op.add_column("summary_artifacts", sa.Column("language", sa.Text(), server_default="en", nullable=False))
    op.add_column("summary_artifacts", sa.Column("generation_config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("summary_artifacts", sa.Column("provenance_hash", sa.Text()))
    op.add_column("summary_artifacts", sa.Column("source_chunk_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("summary_artifacts", sa.Column("source_token_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("summary_artifacts", sa.Column("map_group_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("summary_artifacts", sa.Column("progress", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("summary_artifacts", sa.Column("superseded_by_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="SET NULL")))
    op.execute("UPDATE summary_artifacts SET created_by_user_id = owner_user_id WHERE created_by_user_id IS NULL")
    op.create_index("ix_summary_artifacts_document_version_created", "summary_artifacts", ["document_version_id", "created_at"])
    op.create_index("ix_summary_artifacts_reuse_key", "summary_artifacts", ["reuse_key"])
    op.create_index(
        "uq_summary_artifacts_active_document_analysis", "summary_artifacts", ["reuse_key"], unique=True,
        postgresql_where=sa.text("reuse_key is not null and status in ('queued','running') and deleted_at is null"),
    )

    op.add_column("summary_citations", sa.Column("document_version_id", UUID, sa.ForeignKey("document_versions.id", ondelete="RESTRICT")))
    op.add_column("summary_citations", sa.Column("ordering", sa.Integer()))
    op.create_index("ix_summary_citations_document_version", "summary_citations", ["document_version_id", "ordering"])

    op.create_table(
        "summary_map_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("summary_id", UUID, sa.ForeignKey("summary_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("level", sa.Integer(), server_default="0", nullable=False),
        sa.Column("group_index", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("source_reference_ids", JSONB, nullable=False),
        sa.Column("structured_output", JSONB, nullable=False),
        sa.Column("input_token_count", sa.Integer(), nullable=False),
        sa.Column("output_token_count", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("stage in ('map','reduce')", name="ck_summary_map_results_stage"),
        sa.UniqueConstraint("summary_id", "stage", "level", "group_index", name="uq_summary_map_results_group"),
    )
    op.create_index("ix_summary_map_results_summary_stage", "summary_map_results", ["summary_id", "stage", "level", "group_index"])


def downgrade() -> None:
    op.drop_table("summary_map_results")
    op.drop_index("ix_summary_citations_document_version", table_name="summary_citations")
    op.drop_column("summary_citations", "ordering")
    op.drop_column("summary_citations", "document_version_id")
    op.drop_index("uq_summary_artifacts_active_document_analysis", table_name="summary_artifacts")
    op.drop_index("ix_summary_artifacts_reuse_key", table_name="summary_artifacts")
    op.drop_index("ix_summary_artifacts_document_version_created", table_name="summary_artifacts")
    for column in (
        "superseded_by_id", "progress", "map_group_count", "source_token_count", "source_chunk_count",
        "provenance_hash", "generation_config", "language", "reuse_key", "citation_snapshot",
        "document_version_id", "document_id", "created_by_user_id",
    ):
        op.drop_column("summary_artifacts", column)
    op.drop_constraint("ck_summary_artifacts_status", "summary_artifacts", type_="check")
    op.drop_constraint("ck_summary_artifacts_type", "summary_artifacts", type_="check")
    op.create_check_constraint("ck_summary_artifacts_status", "summary_artifacts", "status in ('pending','running','completed','failed','cancelled')")
    op.create_check_constraint("ck_summary_artifacts_type", "summary_artifacts", "summary_type in ('executive','detailed','key_points','action_items')")

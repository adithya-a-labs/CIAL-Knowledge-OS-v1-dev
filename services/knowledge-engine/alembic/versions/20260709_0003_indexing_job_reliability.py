"""indexing job reliability columns

Revision ID: 20260709_0003
Revises: 20260709_0002
Create Date: 2026-07-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260709_0003"
down_revision = "20260709_0002"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    column_names = _column_names("indexing_jobs")
    if "document_id" not in column_names:
        op.add_column(
            "indexing_jobs",
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "content_hash" not in column_names:
        op.add_column(
            "indexing_jobs",
            sa.Column("content_hash", sa.Text(), nullable=True),
        )
    if "error_detail" not in column_names:
        op.add_column(
            "indexing_jobs",
            sa.Column("error_detail", sa.Text(), nullable=True),
        )

    foreign_key_names = _foreign_key_names("indexing_jobs")
    if "fk_indexing_jobs_document_id" not in foreign_key_names:
        op.create_foreign_key(
            "fk_indexing_jobs_document_id",
            "indexing_jobs",
            "documents",
            ["document_id"],
            ["id"],
            ondelete="SET NULL",
        )

    index_names = _index_names("indexing_jobs")
    if "ix_indexing_jobs_document_id" not in index_names:
        op.create_index(
            "ix_indexing_jobs_document_id",
            "indexing_jobs",
            ["document_id"],
        )
    if "uq_indexing_jobs_active_document_version" not in index_names:
        # Partial unique index: only one pending/running job per document+hash.
        op.execute(
            "CREATE UNIQUE INDEX uq_indexing_jobs_active_document_version "
            "ON indexing_jobs (document_id, content_hash) "
            "WHERE status IN ('pending', 'running')"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_indexing_jobs_active_document_version")

    index_names = _index_names("indexing_jobs")
    if "ix_indexing_jobs_document_id" in index_names:
        op.drop_index("ix_indexing_jobs_document_id", table_name="indexing_jobs")

    foreign_key_names = _foreign_key_names("indexing_jobs")
    if "fk_indexing_jobs_document_id" in foreign_key_names:
        op.drop_constraint("fk_indexing_jobs_document_id", "indexing_jobs", type_="foreignkey")

    column_names = _column_names("indexing_jobs")
    if "error_detail" in column_names:
        op.drop_column("indexing_jobs", "error_detail")
    if "content_hash" in column_names:
        op.drop_column("indexing_jobs", "content_hash")
    if "document_id" in column_names:
        op.drop_column("indexing_jobs", "document_id")

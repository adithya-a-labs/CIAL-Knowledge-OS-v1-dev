"""repository scoped corpus metadata

Revision ID: 20260710_0008
Revises: 20260710_0007
Create Date: 2026-07-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_0008"
down_revision = "20260710_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("folders", sa.Column("repository_id", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("repository_id", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("repository_id", sa.Text(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("repository_id", sa.Text(), nullable=True))
    op.add_column("indexing_jobs", sa.Column("repository_id", sa.Text(), nullable=True))

    op.execute("UPDATE indexing_jobs SET attempts = 0 WHERE attempts IS NULL")
    op.alter_column(
        "indexing_jobs",
        "attempts",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )

    op.drop_constraint("uq_folders_relative_path", "folders", type_="unique")
    op.drop_constraint("uq_documents_relative_path", "documents", type_="unique")

    op.create_index("ix_folders_repository_id", "folders", ["repository_id"])
    op.create_index("ix_documents_repository_id", "documents", ["repository_id"])
    op.create_index("ix_document_versions_repository_id", "document_versions", ["repository_id"])
    op.create_index("ix_ingestion_runs_repository_id", "ingestion_runs", ["repository_id"])
    op.create_index("ix_indexing_jobs_repository_id", "indexing_jobs", ["repository_id"])

    op.create_unique_constraint(
        "uq_folders_repository_relative_path",
        "folders",
        ["repository_id", "relative_path"],
    )
    op.create_unique_constraint(
        "uq_documents_repository_relative_path",
        "documents",
        ["repository_id", "relative_path"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_repository_relative_path", "documents", type_="unique")
    op.drop_constraint("uq_folders_repository_relative_path", "folders", type_="unique")

    op.drop_index("ix_indexing_jobs_repository_id", table_name="indexing_jobs")
    op.drop_index("ix_ingestion_runs_repository_id", table_name="ingestion_runs")
    op.drop_index("ix_document_versions_repository_id", table_name="document_versions")
    op.drop_index("ix_documents_repository_id", table_name="documents")
    op.drop_index("ix_folders_repository_id", table_name="folders")

    op.create_unique_constraint("uq_documents_relative_path", "documents", ["relative_path"])
    op.create_unique_constraint("uq_folders_relative_path", "folders", ["relative_path"])

    op.alter_column(
        "indexing_jobs",
        "attempts",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )

    op.drop_column("indexing_jobs", "repository_id")
    op.drop_column("ingestion_runs", "repository_id")
    op.drop_column("document_versions", "repository_id")
    op.drop_column("documents", "repository_id")
    op.drop_column("folders", "repository_id")

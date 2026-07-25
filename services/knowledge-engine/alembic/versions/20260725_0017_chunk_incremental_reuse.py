"""chunk-level incremental embedding reuse contract

Revision ID: 20260725_0017
Revises: 20260724_0016
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260725_0017"
down_revision = "20260724_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("chunk_hash", sa.Text()))
    op.add_column("document_chunks", sa.Column("embedding_model_version", sa.Text()))
    op.add_column("document_chunks", sa.Column("chunking_version", sa.Text()))
    op.create_index(
        "ix_document_chunks_reuse_contract",
        "document_chunks",
        [
            "document_id",
            "chunk_hash",
            "embedding_model_version",
            "chunking_version",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_reuse_contract", table_name="document_chunks")
    op.drop_column("document_chunks", "chunking_version")
    op.drop_column("document_chunks", "embedding_model_version")
    op.drop_column("document_chunks", "chunk_hash")

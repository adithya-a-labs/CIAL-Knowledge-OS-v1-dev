"""corpus metadata fields

Revision ID: 20260709_0002
Revises: 20260709_0001
Create Date: 2026-07-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260709_0002"
down_revision = "20260709_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("folders", sa.Column("depth", sa.Integer(), server_default="0", nullable=False))
    op.add_column("folders", sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("extension", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.Text(), nullable=True))
    op.execute("update documents set extension = lower(regexp_replace(name, '^.*(\\.[^.]*)$', '\\1')) where name like '%.%'")
    op.execute("update documents set mime_type = 'application/octet-stream' where mime_type is null")


def downgrade() -> None:
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "extension")
    op.drop_column("folders", "last_scanned_at")
    op.drop_column("folders", "depth")


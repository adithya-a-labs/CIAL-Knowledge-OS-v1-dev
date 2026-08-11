"""add monotonic session revocation version

Revision ID: 20260811_0020
Revises: 20260802_0019
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_0020"
down_revision = "20260802_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")

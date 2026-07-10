"""local auth credentials

Revision ID: 20260710_0007
Revises: 20260710_0006
Create Date: 2026-07-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_0007"
down_revision = "20260710_0006"
branch_labels = None
depends_on = None


UUID_TYPE = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "user_credentials",
        sa.Column("id", UUID_TYPE, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID_TYPE,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "password_algorithm",
            sa.Text(),
            nullable=False,
            server_default="scrypt",
        ),
        sa.Column("password_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_user_credentials_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_credentials")

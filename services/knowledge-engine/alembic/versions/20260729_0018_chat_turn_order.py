"""Add deterministic chat turn ordering.

Revision ID: 20260729_0018
Revises: 20260725_0017
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260729_0018"
down_revision = "20260725_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "turn_sequence",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "chat_messages",
        sa.Column(
            "role_sequence",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_chat_messages_session_turn_role",
        "chat_messages",
        ["session_id", "turn_sequence", "role_sequence"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_messages_session_turn_role",
        table_name="chat_messages",
    )
    op.drop_column("chat_messages", "role_sequence")
    op.drop_column("chat_messages", "turn_sequence")

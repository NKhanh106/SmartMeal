"""add unique constraint on conversation_insights(user_id, key)

Revision ID: 20260628_0001
Revises: 20260613_0003
Create Date: 2026-06-28

The service uses ON CONFLICT (user_id, key) DO UPDATE which requires
a unique constraint, not just a regular index.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260628_0001"
down_revision = "20260613_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the non-unique index first
    op.drop_index("idx_insights_user_key", table_name="conversation_insights")

    # Create unique constraint (PostgreSQL automatically creates a unique index)
    op.create_unique_constraint(
        "uq_conversation_insights_user_key",
        "conversation_insights",
        ["user_id", "key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_conversation_insights_user_key",
        "conversation_insights",
        type_="unique",
    )
    # Restore the regular index
    op.create_index(
        "idx_insights_user_key",
        "conversation_insights",
        ["user_id", "key"],
    )

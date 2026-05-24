"""add conversation_insights table for chat summary extraction

Revision ID: 20260503_0002
Revises: 20260503_0001
Create Date: 2026-05-03

Adds:
- table: conversation_insights
  Stores AI-extracted key facts from chatbot conversations.
  Each row = one piece of information (preference, health constraint,
  fitness note, goal change, or general note).
  Deduplication by (user_id, key) via upsert logic in service.
- index: conversation_insights.user_id
- index: conversation_insights.user_id + key (dedup)
- index: conversation_insights.user_id + is_active
- index: conversation_insights.session_id
"""

import sqlalchemy as sa

from alembic import op

revision = "20260503_0002"
down_revision = "20260503_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_insights",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column(
            "insight_type",
            sa.String(50),
            nullable=False,
            server_default="general",
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "idx_insights_user_key",
        "conversation_insights",
        ["user_id", "key"],
    )
    op.create_index(
        "idx_insights_user_active",
        "conversation_insights",
        ["user_id", "is_active"],
    )
    op.create_index(
        "idx_insights_session",
        "conversation_insights",
        ["session_id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_conversation_insights_updated_at
        BEFORE UPDATE ON conversation_insights
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_conversation_insights_updated_at ON conversation_insights")
    op.drop_index("idx_insights_session", table_name="conversation_insights")
    op.drop_index("idx_insights_user_active", table_name="conversation_insights")
    op.drop_index("idx_insights_user_key", table_name="conversation_insights")
    op.drop_table("conversation_insights")

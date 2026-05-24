"""add_message_type_and_card_fields_and_fired_triggers

Revision ID: c76c754abdee
Revises: 20260513_0001
Create Date: 2026-05-12 20:16:49.220324
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c76c754abdee"
down_revision: Union[str, Sequence[str], None] = "20260513_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add card system fields: message_type, card, card_response on chat_messages;
    fired_triggers on chat_sessions."""
    # chat_messages: message type discriminator
    op.add_column(
        "chat_messages",
        sa.Column("message_type", sa.String(length=20), server_default="text", nullable=False),
    )
    # chat_messages: full ChatCard payload for card messages
    op.add_column(
        "chat_messages",
        sa.Column("card", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # chat_messages: user's answer to a card
    op.add_column(
        "chat_messages",
        sa.Column("card_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # chat_sessions: track which hard-rule triggers have fired (idempotency)
    op.add_column(
        "chat_sessions",
        sa.Column("fired_triggers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove card system fields."""
    op.drop_column("chat_sessions", "fired_triggers")
    op.drop_column("chat_messages", "card_response")
    op.drop_column("chat_messages", "card")
    op.drop_column("chat_messages", "message_type")

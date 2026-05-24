"""Add last_activity_at to chat_sessions table

Revision ID: 20260511_0001
Revises: 20260506_0001
Create Date: 2026-05-11 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260511_0001"
down_revision: Union[str, None] = "20260506_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("last_activity_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("""
        UPDATE chat_sessions
        SET last_activity_at = COALESCE(last_message_at, updated_at)
        WHERE last_activity_at IS NULL
    """)


def downgrade() -> None:
    op.drop_column("chat_sessions", "last_activity_at")

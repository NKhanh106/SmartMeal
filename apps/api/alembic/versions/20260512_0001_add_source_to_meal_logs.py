"""Add source field to meal_logs table for chat extraction tracking

Revision ID: 20260512_0001
Revises: 20260511_0001
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260512_0001"
down_revision: Union[str, None] = "20260511_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meal_logs",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="manual"
        ),
    )

    # Create enum type if not exists (for safety)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'meal_log_source') THEN
                CREATE TYPE meal_log_source AS ENUM ('manual', 'chat_extraction', 'chat_command');
            END IF;
        END$$;
    """)

    # Alter column to use enum
    op.execute("""
        ALTER TABLE meal_logs
        ALTER COLUMN source TYPE meal_log_source
        USING source::meal_log_source
    """)


def downgrade() -> None:
    op.drop_column("meal_logs", "source")

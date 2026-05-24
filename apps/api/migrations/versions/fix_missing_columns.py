"""Fix missing columns - add last_activity_at and source

Revision ID: fix_missing_columns
Revises: c76c754abdee
Create Date: 2026-05-12 22:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "fix_missing_columns"
down_revision: Union[str, None] = "c76c754abdee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_activity_at to chat_sessions (from 20260511_0001) - skip if exists
    op.execute("""
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP WITH TIME ZONE
    """)
    op.execute("""
        UPDATE chat_sessions
        SET last_activity_at = COALESCE(last_message_at, updated_at)
        WHERE last_activity_at IS NULL
    """)

    # Add source to meal_logs (from 20260512_0001) - skip if exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'meal_log_source') THEN
                CREATE TYPE meal_log_source AS ENUM ('manual', 'chat_extraction', 'chat_command');
            END IF;
        END$$;
    """)
    op.execute("""
        ALTER TABLE meal_logs ADD COLUMN IF NOT EXISTS source meal_log_source NOT NULL DEFAULT 'manual'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE chat_sessions DROP COLUMN IF EXISTS last_activity_at")
    op.execute("ALTER TABLE meal_logs DROP COLUMN IF EXISTS source")
    op.execute("DROP TYPE IF EXISTS meal_log_source")

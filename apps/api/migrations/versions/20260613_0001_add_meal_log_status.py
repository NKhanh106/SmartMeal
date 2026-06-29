"""Add status field to meal_logs for confirmation workflow

Revision ID: 20260613_0001
Revises: 20260514_0001
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260613_0001"
down_revision: Union[str, None] = "20260514_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'meal_log_status') THEN
                CREATE TYPE meal_log_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
            END IF;
        END$$;
    """)

    op.add_column(
        "meal_logs",
        sa.Column(
            "status",
            postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="meal_log_status", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
    )

    # Add index
    op.create_index("ix_meal_logs_status", "meal_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_meal_logs_status", table_name="meal_logs")
    op.drop_column("meal_logs", "status")
    op.execute("DROP TYPE IF EXISTS meal_log_status")

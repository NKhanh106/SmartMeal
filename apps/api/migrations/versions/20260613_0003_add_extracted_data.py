"""Add extracted_data JSONB column to meal_logs

Revision ID: 20260613_0003
Revises: 20260613_0002_merge_heads
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260613_0003"
down_revision: Union[str, Sequence[str], None] = "20260613_0002_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meal_logs",
        sa.Column(
            "extracted_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("meal_logs", "extracted_data")

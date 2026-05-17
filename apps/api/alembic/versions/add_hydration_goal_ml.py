"""Add hydration_goal_ml to nutrition_goals.

Revision ID: add_hydration_goal_ml
Revises: a3619702571c
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "add_hydration_goal_ml"
down_revision: Union[str, None] = "a3619702571c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "nutrition_goals",
        sa.Column("hydration_goal_ml", sa.Numeric(8, 0), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("nutrition_goals", "hydration_goal_ml")

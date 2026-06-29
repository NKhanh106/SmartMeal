"""Drop unique constraint on health_events

Revision ID: 20260629_0004
Revises: 20260629_0002
Create Date: 2026-06-29

Same symptom category can appear multiple times on the same day.
No unique constraint needed on health_events.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260629_0004"
down_revision: Union[str, Sequence[str], None] = "20260629_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_health_user_date_category",
        "health_events",
        type_="unique",
    )


def downgrade() -> None:
    pass

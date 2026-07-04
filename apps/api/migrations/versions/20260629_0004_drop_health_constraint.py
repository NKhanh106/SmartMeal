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
    # Idempotent: only drop if the constraint exists. Earlier migration 0001
    # creates it on legacy deployments, but newer 0001 omits it. Migration
    # 0002 is a no-op, so 0004 must tolerate both schemas.
    op.execute(
        "ALTER TABLE health_events "
        "DROP CONSTRAINT IF EXISTS uq_health_user_date_category"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE health_events "
        "ADD CONSTRAINT uq_health_user_date_category "
        "UNIQUE (user_id, event_date, category)"
    )

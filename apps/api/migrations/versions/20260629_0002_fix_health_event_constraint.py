"""Remove duplicate health_events constraint fix

Revision ID: 20260629_0002
Revises: 20260629_0001
Create Date: 2026-06-29

The original 0001 migration was updated to not create the unique constraint.
This migration is now a no-op to avoid conflicts.
"""

from typing import Sequence, Union


revision: str = "20260629_0002"
down_revision: Union[str, Sequence[str], None] = "20260629_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

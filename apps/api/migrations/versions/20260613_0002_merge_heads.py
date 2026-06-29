"""Merge heads: meal_log_status and remove_image_features

Revision ID: 20260613_0002_merge_heads
Revises: 20260613_0001, 372559ce19c2
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260613_0002_merge_heads"
down_revision: Union[str, None] = ("20260613_0001", "372559ce19c2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # merge revision, no schema changes needed


def downgrade() -> None:
    pass

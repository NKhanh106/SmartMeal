"""merge_heads

Revision ID: f127c50a74d6
Revises: 20260514_0001, c76c754abdee
Create Date: 2026-05-12 22:20:58.120832

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f127c50a74d6'
down_revision: Union[str, Sequence[str], None] = ('20260514_0001', 'c76c754abdee')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

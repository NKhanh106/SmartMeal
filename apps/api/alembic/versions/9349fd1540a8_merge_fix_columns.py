"""merge_fix_columns

Revision ID: 9349fd1540a8
Revises: fix_missing_columns, f127c50a74d6
Create Date: 2026-05-12 22:24:50.459152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9349fd1540a8'
down_revision: Union[str, Sequence[str], None] = ('fix_missing_columns', 'f127c50a74d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

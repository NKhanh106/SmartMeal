"""Make users.login_allowed_at nullable

Revision ID: 20260630_0001
Revises: 20260629_0004
Create Date: 2026-06-30

The SQLAlchemy model declares login_allowed_at as nullable=True
(rate-limit allowance timestamp is optional, defaulting to NULL
when the account has never been blocked). However, the legacy
column was created with NOT NULL, causing INSERT failures when
smoke users omit the field. Align schema with model.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260630_0001"
down_revision: Union[str, Sequence[str], None] = "20260629_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ALTER COLUMN login_allowed_at DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users ALTER COLUMN login_allowed_at SET NOT NULL"
    )
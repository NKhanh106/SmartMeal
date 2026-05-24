"""Add exercises table for workout exercise library.

Exercises are now stored in the DB instead of hardcoded in workout_plans.py.
Seed with: python -m app.db.seeds.seed_exercises
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_0001"
down_revision = "20260504_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("muscle_group", sa.String(length=100), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("default_sets", sa.Integer(), nullable=True),
        sa.Column("default_reps", sa.Integer(), nullable=True),
        sa.Column("default_rest_seconds", sa.Integer(), nullable=True),
        sa.Column("calories_per_minute", sa.Float(), nullable=True),
        sa.Column("equipment_needed", sa.Boolean(), nullable=True),
        sa.Column("instructions", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("exercises")

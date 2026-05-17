"""Add extended profile fields — usage goal, health conditions, lifestyle, taste preferences

Revision ID: 20260513_0001
Revises: 20260512_0001
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260513_0001"
down_revision: Union[str, None] = "20260512_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create enum types ─────────────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'usage_goal_enum') THEN
                CREATE TYPE usage_goal_enum AS ENUM (
                    'muscle_gain', 'weight_loss', 'weight_gain', 'maintain_shape',
                    'nutrient_supplement', 'medical_treatment', 'balanced_lifestyle',
                    'sports_performance', 'pregnancy_nursing', 'elderly_nutrition'
                );
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sleep_quality_enum') THEN
                CREATE TYPE sleep_quality_enum AS ENUM ('poor', 'fair', 'good', 'excellent');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'meal_frequency_enum') THEN
                CREATE TYPE meal_frequency_enum AS ENUM (
                    'two_meals', 'three_meals', 'four_meals', 'five_plus', 'intermittent_fasting'
                );
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cooking_preference_enum') THEN
                CREATE TYPE cooking_preference_enum AS ENUM (
                    'home_cooked', 'eat_out', 'mixed', 'meal_prep'
                );
            END IF;
        END$$;
    """)

    # ── Rename legacy Text columns → _text suffix ─────────────────────────────
    # This preserves old data while freeing the original names for JSONB columns.
    op.execute("ALTER TABLE user_profiles RENAME COLUMN allergies TO allergies_text")
    op.execute("ALTER TABLE user_profiles RENAME COLUMN disliked_foods TO disliked_foods_text")
    op.execute("ALTER TABLE user_profiles RENAME COLUMN preferred_foods TO preferred_foods_text")

    # ── Usage Goal ────────────────────────────────────────────────────────────
    op.add_column(
        "user_profiles",
        sa.Column("usage_goal", postgresql.ENUM(
            "muscle_gain", "weight_loss", "weight_gain", "maintain_shape",
            "nutrient_supplement", "medical_treatment", "balanced_lifestyle",
            "sports_performance", "pregnancy_nursing", "elderly_nutrition",
            name="usage_goal_enum", create_type=False
        ), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("usage_goal_note", sa.String(500), nullable=True)
    )

    # ── Health Conditions (JSONB) ─────────────────────────────────────────────
    op.add_column(
        "user_profiles",
        sa.Column("health_conditions", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("allergies", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("medications", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("dietary_restrictions", postgresql.JSONB, nullable=True)
    )

    # ── Lifestyle ──────────────────────────────────────────────────────────────
    op.add_column(
        "user_profiles",
        sa.Column("sleep_duration_hours", sa.Float, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("sleep_quality", postgresql.ENUM(
            "poor", "fair", "good", "excellent",
            name="sleep_quality_enum", create_type=False
        ), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("sleep_schedule", sa.String(50), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("stress_level", sa.Integer, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("meal_frequency", postgresql.ENUM(
            "two_meals", "three_meals", "four_meals", "five_plus", "intermittent_fasting",
            name="meal_frequency_enum", create_type=False
        ), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("cooking_preference", postgresql.ENUM(
            "home_cooked", "eat_out", "mixed", "meal_prep",
            name="cooking_preference_enum", create_type=False
        ), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("wake_up_time", sa.String(10), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("sleep_time", sa.String(10), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("work_schedule", sa.String(50), nullable=True)
    )

    # ── Taste Preferences (JSONB) ─────────────────────────────────────────────
    op.add_column(
        "user_profiles",
        sa.Column("taste_preferences", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("cuisine_preferences", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("disliked_foods", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("favorite_foods", postgresql.JSONB, nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("eating_speed", sa.String(20), nullable=True)
    )
    op.add_column(
        "user_profiles",
        sa.Column("chew_difficulty", sa.Boolean, nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "chew_difficulty")
    op.drop_column("user_profiles", "eating_speed")
    op.drop_column("user_profiles", "favorite_foods")
    op.drop_column("user_profiles", "disliked_foods")
    op.drop_column("user_profiles", "cuisine_preferences")
    op.drop_column("user_profiles", "taste_preferences")
    op.drop_column("user_profiles", "work_schedule")
    op.drop_column("user_profiles", "sleep_time")
    op.drop_column("user_profiles", "wake_up_time")
    op.drop_column("user_profiles", "cooking_preference")
    op.drop_column("user_profiles", "meal_frequency")
    op.drop_column("user_profiles", "stress_level")
    op.drop_column("user_profiles", "sleep_schedule")
    op.drop_column("user_profiles", "sleep_quality")
    op.drop_column("user_profiles", "sleep_duration_hours")
    op.drop_column("user_profiles", "dietary_restrictions")
    op.drop_column("user_profiles", "medications")
    op.drop_column("user_profiles", "allergies")
    op.drop_column("user_profiles", "health_conditions")
    op.drop_column("user_profiles", "usage_goal_note")
    op.drop_column("user_profiles", "usage_goal")

    # Restore legacy column names
    op.execute("ALTER TABLE user_profiles RENAME COLUMN preferred_foods_text TO preferred_foods")
    op.execute("ALTER TABLE user_profiles RENAME COLUMN disliked_foods_text TO disliked_foods")
    op.execute("ALTER TABLE user_profiles RENAME COLUMN allergies_text TO allergies")

"""add progress_logs, workout_plans, workout_items tables

Revision ID: 20260429_0002
Revises: 20260427_0001
Create Date: 2026-04-29

Adds:
- enum: workout_difficulty_type (nguoi_moi, trung_binh, nang_cao)
- table: progress_logs
- table: workout_plans
- table: workout_items

Also fixes:
- meal_items.source server_default aligned from 'nhap_thu_cong' -> 'ai_nhan_dien'
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260429_0002"
down_revision = "20260427_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Tạo enum workout_difficulty_type ──────────────────────────────────
    op.execute(
        "CREATE TYPE workout_difficulty_type AS ENUM ('nguoi_moi', 'trung_binh', 'nang_cao')"
    )

    # ── 2. Sửa meal_items.source server_default cho nhất quán ─────────────────
    op.execute(
        "ALTER TABLE meal_items ALTER COLUMN source DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE meal_items ALTER COLUMN source SET DEFAULT 'ai_nhan_dien'"
    )

    # ── 3. Bảng progress_logs ──────────────────────────────────────────────────
    op.create_table(
        "progress_logs",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("weight_kg", sa.Numeric(6, 2)),
        sa.Column("body_fat_percent", sa.Numeric(5, 2)),
        sa.Column("waist_cm", sa.Numeric(5, 2)),
        sa.Column("neck_cm", sa.Numeric(5, 2)),
        sa.Column("chest_cm", sa.Numeric(5, 2)),
        sa.Column("hip_cm", sa.Numeric(5, 2)),
        sa.Column("progress_photo_url", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "log_date", name="uq_progress_user_date"),
        sa.CheckConstraint("weight_kg IS NULL OR (weight_kg > 0 AND weight_kg <= 500)", name="chk_progress_logs_weight"),
        sa.CheckConstraint(
            "body_fat_percent IS NULL OR (body_fat_percent > 0 AND body_fat_percent <= 100)",
            name="chk_progress_logs_body_fat",
        ),
    )
    op.create_index("idx_progress_logs_user_date", "progress_logs", ["user_id", "log_date"])
    op.execute(
        """
        CREATE TRIGGER trg_progress_logs_updated_at
        BEFORE UPDATE ON progress_logs
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )

    # ── 4. Bảng workout_plans ─────────────────────────────────────────────────
    op.create_table(
        "workout_plans",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_name", sa.String(255), nullable=False),
        sa.Column("goal_type", sa.String(20)),  # nullable, FK sau
        sa.Column(
            "difficulty",
            postgresql.ENUM("nguoi_moi", "trung_binh", "nang_cao", name="workout_difficulty_type", create_type=False),
            nullable=False,
            server_default="nguoi_moi",
        ),
        sa.Column("start_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("end_date", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("LENGTH(TRIM(plan_name)) > 0", name="chk_workout_plans_name_not_blank"),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="chk_workout_plans_end_after_start",
        ),
    )
    op.create_index("idx_workout_plans_user_id", "workout_plans", ["user_id"])
    op.create_index(
        "idx_workout_plans_one_active_per_user",
        "workout_plans",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.execute(
        """
        CREATE TRIGGER trg_workout_plans_updated_at
        BEFORE UPDATE ON workout_plans
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )

    # ── 5. Bảng workout_items ─────────────────────────────────────────────────
    op.create_table(
        "workout_items",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workout_plan_id",
            sa.UUID(),
            sa.ForeignKey("workout_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workout_date", sa.Date()),
        sa.Column("day_of_week", sa.SmallInteger()),
        sa.Column("muscle_group", sa.String(100)),
        sa.Column("exercise_name", sa.String(255), nullable=False),
        sa.Column("weight_kg", sa.Numeric(6, 2)),
        sa.Column("sets", sa.Integer()),
        sa.Column("reps", sa.Integer()),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("rest_seconds", sa.Integer()),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("LENGTH(TRIM(exercise_name)) > 0", name="chk_workout_items_name_not_blank"),
        sa.CheckConstraint(
            "day_of_week IS NULL OR (day_of_week >= 1 AND day_of_week <= 7)",
            name="chk_workout_items_day_of_week",
        ),
        sa.CheckConstraint(
            "sets IS NULL OR sets > 0",
            name="chk_workout_items_sets_positive",
        ),
        sa.CheckConstraint(
            "reps IS NULL OR reps > 0",
            name="chk_workout_items_reps_positive",
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="chk_workout_items_duration_positive",
        ),
        sa.CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0",
            name="chk_workout_items_rest_non_negative",
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR weight_kg > 0",
            name="chk_workout_items_weight_positive",
        ),
        sa.CheckConstraint(
            "(is_completed = FALSE AND completed_at IS NULL) OR (is_completed = TRUE AND completed_at IS NOT NULL)",
            name="chk_workout_items_completed_state",
        ),
    )
    op.create_index("idx_workout_items_plan_id", "workout_items", ["workout_plan_id"])
    op.create_index("idx_workout_items_plan_date", "workout_items", ["workout_plan_id", "workout_date"])
    op.create_index("idx_workout_items_muscle_group", "workout_items", ["muscle_group"])
    op.execute(
        """
        CREATE TRIGGER trg_workout_items_updated_at
        BEFORE UPDATE ON workout_items
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.drop_table("workout_items")
    op.drop_table("workout_plans")
    op.drop_table("progress_logs")
    op.execute("DROP TYPE IF EXISTS workout_difficulty_type CASCADE")

    # Restore original meal_items.source default
    op.execute(
        "ALTER TABLE meal_items ALTER COLUMN source DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE meal_items ALTER COLUMN source SET DEFAULT 'nhap_thu_cong'"
    )

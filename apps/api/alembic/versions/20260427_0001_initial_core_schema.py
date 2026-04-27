"""initial core schema

Revision ID: 20260427_0001
Revises:
Create Date: 2026-04-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260427_0001"
down_revision = None
branch_labels = None
depends_on = None

gender_type = postgresql.ENUM("nam", "nu", "khac", "khong_muon_noi", name="gender_type", create_type=False)
activity_level_type = postgresql.ENUM(
    "it_van_dong",
    "van_dong_nhe",
    "van_dong_vua",
    "van_dong_nhieu",
    "van_dong_rat_nhieu",
    name="activity_level_type",
    create_type=False,
)
nutrition_goal_type = postgresql.ENUM("giam_can", "giu_can", "tang_co", name="nutrition_goal_type", create_type=False)
meal_type_enum = postgresql.ENUM("bua_sang", "bua_trua", "bua_toi", "an_vat", "khac", name="meal_type_enum", create_type=False)
food_source_type = postgresql.ENUM("he_thong", "usda", "thu_cong", "ai_goi_y", name="food_source_type", create_type=False)
item_source_type = postgresql.ENUM(
    "ai_nhan_dien",
    "nguoi_dung_xac_nhan",
    "nhap_thu_cong",
    name="item_source_type",
    create_type=False,
)
diet_type_enum = postgresql.ENUM(
    "binh_thuong",
    "an_chay",
    "thuan_chay",
    "keto",
    "it_tinh_bot",
    "nhieu_dam",
    "khac",
    name="diet_type_enum",
    create_type=False,
)


def _enum(name: str, *values: str) -> None:
    op.execute(
        "CREATE TYPE "
        + name
        + " AS ENUM ("
        + ", ".join(f"'{value}'" for value in values)
        + ")"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    _enum("gender_type", "nam", "nu", "khac", "khong_muon_noi")
    _enum(
        "activity_level_type",
        "it_van_dong",
        "van_dong_nhe",
        "van_dong_vua",
        "van_dong_nhieu",
        "van_dong_rat_nhieu",
    )
    _enum("nutrition_goal_type", "giam_can", "giu_can", "tang_co")
    _enum("meal_type_enum", "bua_sang", "bua_trua", "bua_toi", "an_vat", "khac")
    _enum("food_source_type", "he_thong", "usda", "thu_cong", "ai_goi_y")
    _enum("item_source_type", "ai_nhan_dien", "nguoi_dung_xac_nhan", "nhap_thu_cong")
    _enum("diet_type_enum", "binh_thuong", "an_chay", "thuan_chay", "keto", "it_tinh_bot", "nhieu_dam", "khac")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("failed_login_attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("login_allowed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("LENGTH(TRIM(email::TEXT)) > 0", name="chk_users_email_not_blank"),
        sa.CheckConstraint("failed_login_attempts >= 0", name="chk_users_failed_login_attempts"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="chk_users_role"),
    )
    op.execute("CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("gender", gender_type, nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("height_cm", sa.Numeric(6, 2), nullable=False),
        sa.Column("current_weight_kg", sa.Numeric(6, 2), nullable=False),
        sa.Column("current_body_fat_percent", sa.Numeric(5, 2)),
        sa.Column("current_waist_cm", sa.Numeric(5, 2)),
        sa.Column("current_neck_cm", sa.Numeric(5, 2)),
        sa.Column("current_hip_cm", sa.Numeric(5, 2)),
        sa.Column("current_chest_cm", sa.Numeric(5, 2)),
        sa.Column("activity_level", activity_level_type, nullable=False, server_default="it_van_dong"),
        sa.Column("diet_type", diet_type_enum, nullable=False, server_default="binh_thuong"),
        sa.Column("allergies", sa.Text()),
        sa.Column("disliked_foods", sa.Text()),
        sa.Column("preferred_foods", sa.Text()),
        sa.Column("health_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("CREATE TRIGGER trg_user_profiles_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "nutrition_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_type", nutrition_goal_type, nullable=False),
        sa.Column("target_weight_kg", sa.Numeric(6, 2)),
        sa.Column("bmr_kcal", sa.Numeric(8, 2)),
        sa.Column("tdee_kcal", sa.Numeric(8, 2)),
        sa.Column("bmi", sa.Numeric(5, 2)),
        sa.Column("daily_calorie_target", sa.Numeric(8, 2), nullable=False),
        sa.Column("protein_target_g", sa.Numeric(8, 2), nullable=False),
        sa.Column("carb_target_g", sa.Numeric(8, 2), nullable=False),
        sa.Column("fat_target_g", sa.Numeric(8, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("end_date", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "user_id", name="uq_nutrition_goals_id_user_id"),
    )
    op.create_index("uq_nutrition_goals_one_active_per_user", "nutrition_goals", ["user_id"], unique=True, postgresql_where=sa.text("is_active = TRUE"))
    op.execute("CREATE TRIGGER trg_nutrition_goals_updated_at BEFORE UPDATE ON nutrition_goals FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "food_nutrition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("food_name", sa.String(255), nullable=False),
        sa.Column("food_name_vi", sa.String(255)),
        sa.Column("food_name_en", sa.String(255)),
        sa.Column("category", sa.String(100)),
        sa.Column("serving_size_g", sa.Numeric(8, 2), nullable=False, server_default="100"),
        sa.Column("calories_per_100g", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("protein_per_100g", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("carb_per_100g", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("fat_per_100g", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("fiber_per_100g", sa.Numeric(8, 2)),
        sa.Column("sugar_per_100g", sa.Numeric(8, 2)),
        sa.Column("sodium_mg_per_100g", sa.Numeric(8, 2)),
        sa.Column("source", food_source_type, nullable=False, server_default="he_thong"),
        sa.Column("external_id", sa.String(255)),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("CREATE TRIGGER trg_food_nutrition_updated_at BEFORE UPDATE ON food_nutrition FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "meal_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nutrition_goal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("meal_type", meal_type_enum, nullable=False, server_default="khac"),
        sa.Column("meal_time", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("image_url", sa.Text()),
        sa.Column("image_storage_path", sa.Text()),
        sa.Column("ai_model", sa.String(100)),
        sa.Column("ai_confidence", sa.Numeric(5, 4)),
        sa.Column("total_calories", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total_protein_g", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total_carb_g", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total_fat_g", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(
        """
        ALTER TABLE meal_logs
        ADD CONSTRAINT fk_meal_logs_nutrition_goal
        FOREIGN KEY (nutrition_goal_id, user_id)
        REFERENCES nutrition_goals(id, user_id)
        ON DELETE SET NULL (nutrition_goal_id)
        """
    )
    op.create_index("idx_meal_logs_user_time", "meal_logs", ["user_id", "meal_time"])
    op.execute("CREATE TRIGGER trg_meal_logs_updated_at BEFORE UPDATE ON meal_logs FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "meal_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meal_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meal_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_nutrition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("food_nutrition.id", ondelete="SET NULL")),
        sa.Column("detected_food_name", sa.String(255), nullable=False),
        sa.Column("display_food_name", sa.String(255)),
        sa.Column("estimated_weight_g", sa.Numeric(10, 2)),
        sa.Column("calories", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("protein_g", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("carb_g", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("source", item_source_type, nullable=False, server_default="nhap_thu_cong"),
        sa.Column("ai_raw_result", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("CREATE TRIGGER trg_meal_items_updated_at BEFORE UPDATE ON meal_items FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "ai_analysis_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("provider_name", sa.String(50)),
        sa.Column("model_name", sa.String(100)),
        sa.Column("prompt_version", sa.String(50)),
        sa.Column("input_summary", sa.Text()),
        sa.Column("raw_response", postgresql.JSONB()),
        sa.Column("status", sa.String(50), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "daily_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("calories_target", sa.Numeric(8, 2)),
        sa.Column("protein_target_g", sa.Numeric(8, 2)),
        sa.Column("carb_target_g", sa.Numeric(8, 2)),
        sa.Column("fat_target_g", sa.Numeric(8, 2)),
        sa.Column("meal_suggestion", sa.Text()),
        sa.Column("workout_suggestion", sa.Text()),
        sa.Column("lifestyle_suggestion", sa.Text()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_raw_response", postgresql.JSONB()),
        sa.Column("ai_analysis_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_analysis_logs.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(50), nullable=False, server_default="generated"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "recommendation_date", name="uq_daily_recommendation_user_date"),
    )
    op.execute("CREATE TRIGGER trg_daily_recommendations_updated_at BEFORE UPDATE ON daily_recommendations FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("CREATE TRIGGER trg_chat_sessions_updated_at BEFORE UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_analysis_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_analysis_logs.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for table in (
        "chat_messages",
        "chat_sessions",
        "daily_recommendations",
        "ai_analysis_logs",
        "meal_items",
        "meal_logs",
        "food_nutrition",
        "nutrition_goals",
        "user_profiles",
        "users",
    ):
        op.drop_table(table)

    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
    for enum_name in (
        "diet_type_enum",
        "item_source_type",
        "food_source_type",
        "meal_type_enum",
        "nutrition_goal_type",
        "activity_level_type",
        "gender_type",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")

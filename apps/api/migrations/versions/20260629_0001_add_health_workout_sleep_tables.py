"""Add health_events, muscle_soreness, workout_logs, sleep_logs tables

Revision ID: 20260629_0001
Revises: 20260628_0001
Create Date: 2026-06-29

Thay thế JSONB trong user_memory bằng bảng riêng cho:
- HEALTH_EVENT: Triệu chứng, bệnh, hồi phục, đo lường, ghi chú sức khỏe
- MUSCLE_SORENESS: Tình trạng đau cơ
- WORKOUT_LOG: Lịch sử tập luyện
- SLEEP_LOG: Giấc ngủ hàng ngày
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260629_0001"
down_revision: Union[str, Sequence[str], None] = "20260628_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. health_events ──────────────────────────────────────────────────────────
    op.create_table(
        "health_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),  # symptom | illness | recovery | measurement | note
        sa.Column("category", sa.String(50), nullable=True),    # digestive | muscular | metabolic | respiratory | other
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),     # mild | moderate | severe
        sa.Column("resolved", sa.Boolean(), default=False),
        sa.Column("source_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_health_events_user_id", "health_events", ["user_id"])
    op.create_index("ix_health_events_event_date", "health_events", ["event_date"])

    # ── 2. muscle_soreness ──────────────────────────────────────────────────────
    op.create_table(
        "muscle_soreness",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("sore_areas", postgresql.ARRAY(sa.String()), default=list),
        sa.Column("pain_level", sa.Integer(), nullable=True),  # 1-10
        sa.Column("soreness_type", sa.String(50), nullable=True),  # acute | delayed | chronic | injury
        sa.Column("workout_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workout_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_recovered", sa.Boolean(), default=False),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_muscle_soreness_user_id", "muscle_soreness", ["user_id"])
    op.create_index("ix_muscle_soreness_log_date", "muscle_soreness", ["log_date"])

    # ── 3. workout_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "workout_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("workout_type", sa.String(100), nullable=True),   # gym | cardio | yoga | running | etc
        sa.Column("workout_name", sa.String(200), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("intensity", sa.String(20), nullable=True),      # light | moderate | intense
        sa.Column("calories_burned", sa.Numeric(7, 2), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),         # manual | chat_extraction | device
        sa.Column("source_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workout_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workout_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("completed", sa.Boolean(), default=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workout_logs_user_id", "workout_logs", ["user_id"])
    op.create_index("ix_workout_logs_workout_date", "workout_logs", ["workout_date"])

    # ── 4. sleep_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "sleep_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sleep_date", sa.Date(), nullable=False),
        sa.Column("bed_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wake_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sleep_duration_hours", sa.Numeric(4, 2), nullable=True),
        sa.Column("quality", sa.String(20), nullable=True),       # poor | fair | good | excellent
        sa.Column("wake_up_count", sa.Integer(), default=0),
        sa.Column("deep_sleep_hours", sa.Numeric(4, 2), nullable=True),
        sa.Column("rem_sleep_hours", sa.Numeric(4, 2), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),         # manual | chat_extraction | device
        sa.Column("source_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sleep_logs_user_id", "sleep_logs", ["user_id"])
    op.create_index("ix_sleep_logs_sleep_date", "sleep_logs", ["sleep_date"])


def downgrade() -> None:
    op.drop_table("sleep_logs")
    op.drop_table("workout_logs")
    op.drop_table("muscle_soreness")
    op.drop_table("health_events")

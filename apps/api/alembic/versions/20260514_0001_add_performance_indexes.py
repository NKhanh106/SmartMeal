"""Add performance indexes for chat, meal_logs, and food_nutrition tables.

Revision ID: 20260514_0001
Revises: 20260513_0001
Create Date: 2026-05-14 00:00:00.000000

Adds composite indexes to speed up:
- Chat session listing (user_id, status, last_message_at)
- Chat message pagination (session_id, created_at)
- Meal log dashboard queries (user_id, meal_time)
- Food nutrition fuzzy search (already has GIN trgm index, add B-tree for food_name_vi)

Safety: pg_trgm extension already exists (created in 20260504_0001).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260514_0001"
down_revision: Union[str, None] = "20260513_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── chat_sessions indexes ────────────────────────────────────────────────────

    # Composite index for listing active sessions ordered by last_message_at
    # Covers: WHERE user_id=? AND status!='deleted' ORDER BY last_message_at DESC
    op.create_index(
        "ix_chat_sessions_user_status_last_msg",
        "chat_sessions",
        ["user_id", "status", "last_message_at"],
        unique=False,
    )

    # Composite index for listing sessions ordered by last_activity_at
    # Covers: WHERE user_id=? AND status!='deleted' ORDER BY last_activity_at DESC
    op.create_index(
        "ix_chat_sessions_user_status_activity",
        "chat_sessions",
        ["user_id", "status", "last_activity_at"],
        unique=False,
    )

    # ── chat_messages indexes ──────────────────────────────────────────────────

    # Composite index for paginating messages by session and time
    # Covers: WHERE session_id=? ORDER BY created_at DESC (with optional id cursor)
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )

    # Index on session_id alone for counting messages per session
    op.create_index(
        "ix_chat_messages_session_id",
        "chat_messages",
        ["session_id"],
        unique=False,
    )

    # ── meal_logs indexes ───────────────────────────────────────────────────────

    # Composite index for dashboard queries (today's meals, weekly stats)
    # Covers: WHERE user_id=? AND meal_time>=? ORDER BY meal_time DESC
    op.create_index(
        "ix_meal_logs_user_meal_time",
        "meal_logs",
        ["user_id", "meal_time"],
        unique=False,
    )

    # Index for meal_logs by user only (used by various user-scoped queries)
    op.create_index(
        "ix_meal_logs_user_id",
        "meal_logs",
        ["user_id"],
        unique=False,
    )

    # ── food_nutrition indexes ─────────────────────────────────────────────────

    # B-tree index on food_name_vi for exact/prefix lookups
    op.create_index(
        "ix_food_nutrition_food_name_vi",
        "food_nutrition",
        ["food_name_vi"],
        unique=False,
        postgresql_where=sa.text("food_name_vi IS NOT NULL"),
    )

    # B-tree index on food_name for exact lookups (faster than GIN for prefix matches)
    op.create_index(
        "ix_food_nutrition_food_name",
        "food_nutrition",
        ["food_name"],
        unique=False,
    )

    # B-tree index on is_verified (used in queries that prioritize verified foods)
    op.create_index(
        "ix_food_nutrition_is_verified",
        "food_nutrition",
        ["is_verified"],
        unique=False,
    )

    # ── meal_items index ───────────────────────────────────────────────────────

    # Index for joining meal_items to meal_logs efficiently
    op.create_index(
        "ix_meal_items_meal_log_id",
        "meal_items",
        ["meal_log_id"],
        unique=False,
    )


def downgrade() -> None:
    # meal_items
    op.drop_index("ix_meal_items_meal_log_id", table_name="meal_items")

    # food_nutrition
    op.drop_index("ix_food_nutrition_is_verified", table_name="food_nutrition")
    op.drop_index("ix_food_nutrition_food_name", table_name="food_nutrition")
    op.drop_index("ix_food_nutrition_food_name_vi", table_name="food_nutrition")

    # meal_logs
    op.drop_index("ix_meal_logs_user_id", table_name="meal_logs")
    op.drop_index("ix_meal_logs_user_meal_time", table_name="meal_logs")

    # chat_messages
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")

    # chat_sessions
    op.drop_index("ix_chat_sessions_user_status_activity", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_status_last_msg", table_name="chat_sessions")

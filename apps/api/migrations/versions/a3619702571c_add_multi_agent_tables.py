"""add_multi_agent_tables

Revision ID: a3619702571c
Revises: 9349fd1540a8
Create Date: 2026-05-13 22:34:40.723010

Creates:
- user_memory      : persistent 'brain' per user — body state, health events,
                     nutrition/fitness memory, conversation summary, key facts
- agent_runs       : execution log for every agent run (debug, cost tracking)
- agent_insights   : structured outputs from specialist agents per session

Extends:
- chat_sessions    : +agent_context JSONB, +needs_extraction BOOLEAN
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a3619702571c"
down_revision: Union[str, Sequence[str], None] = "9349fd1540a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── user_memory ─────────────────────────────────────────────────────────────
    op.create_table(
        "user_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("body_snapshot", postgresql.JSONB, nullable=True),
        sa.Column("health_events", postgresql.JSONB, nullable=True),
        sa.Column(
            "nutrition_memory", postgresql.JSONB, nullable=True
        ),
        sa.Column("fitness_memory", postgresql.JSONB, nullable=True),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("key_facts", postgresql.JSONB, nullable=True),
        sa.Column(
            "last_extraction_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_health_check_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "extraction_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_memory_user_id"),
    )
    op.create_index("ix_user_memory_user_id", "user_memory", ["user_id"])

    # ── agent_runs ───────────────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_agent_runs_run_id", "agent_runs", ["run_id"])
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index(
        "ix_agent_runs_user_agent_created",
        "agent_runs",
        ["user_id", "agent_name", "created_at"],
    )

    # ── agent_insights ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_insights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("insight_type", sa.String(length=50), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "used_by_orchestrator",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_insights_run_id", "agent_insights", ["run_id"])
    op.create_index(
        "ix_agent_insights_session_agent",
        "agent_insights",
        ["session_id", "agent_name"],
    )
    op.create_index(
        "ix_agent_insights_user_created",
        "agent_insights",
        ["user_id", "created_at"],
    )

    # ── Extend chat_sessions ─────────────────────────────────────────────────────
    op.add_column(
        "chat_sessions",
        sa.Column(
            "agent_context", postgresql.JSONB, nullable=True
        ),
    )
    op.add_column(
        "chat_sessions",
        sa.Column(
            "needs_extraction",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "needs_extraction")
    op.drop_column("chat_sessions", "agent_context")

    op.drop_table("agent_insights")
    op.drop_table("agent_runs")
    op.drop_table("user_memory")

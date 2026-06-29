import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base


class AgentRun(Base):
    """
    Log of every agent execution for debugging, performance monitoring, and cost tracking.

    Written by BaseAgent._log_start / _log_complete in the shared agent infrastructure.
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_user_agent_created", "user_id", "agent_name", "created_at"),
        Index("ix_agent_runs_session_id", "session_id"),
        Index("ix_agent_runs_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Stable identifier for this run (used as FK by agent_insights)
    run_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    # Optional: which chat session triggered this run
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Which agent ran
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "orchestrator" | "extractor" | "health_monitor" |
    #         "nutrition_advisor" | "fitness_coach" | "web_researcher"

    # What triggered this run
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "user_message" | "scheduled" | "agent_request" | "manual"

    # Token usage (populated by BaseAgent._call_ai)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Execution status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
    )
    # Values: "pending" | "running" | "completed" | "failed" | "skipped"

    # Truncated summaries for dashboards
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Error detail if status == "failed"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Arbitrary metadata (provider, model, etc.) — avoid name 'metadata' (SQLAlchemy reserved)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

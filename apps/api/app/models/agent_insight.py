import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
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


class AgentInsight(Base):
    """
    Outputs from each specialist agent, stored per-session for the orchestrator to combine.

    The orchestrator reads these after all agents complete, then synthesizes a final response.
    """

    __tablename__ = "agent_insights"
    __table_args__ = (
        Index("ix_agent_insights_session_agent", "session_id", "agent_name"),
        Index("ix_agent_insights_run_id", "run_id"),
        Index("ix_agent_insights_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Which agent run produced this insight
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Which conversation session this insight belongs to
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Which specialist agent produced this
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "orchestrator" | "extractor" | "health_monitor" |
    #         "nutrition_advisor" | "fitness_coach" | "web_researcher"

    # What kind of insight this is
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "health_status" | "nutrition_recommendation" | "fitness_recommendation"
    #         "extracted_facts" | "web_research" | "alert"

    # Agent-specific structured output (schema varies per agent)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # How confident the agent is in this insight (0.0 – 1.0)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Priority: 1 = urgent, 10 = low
    priority: Mapped[int] = mapped_column(Integer, default=5, server_default="5")

    # Whether the orchestrator has already consumed this insight
    used_by_orchestrator: Mapped[bool] = mapped_column(default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Some insights are time-sensitive (e.g. health alerts)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

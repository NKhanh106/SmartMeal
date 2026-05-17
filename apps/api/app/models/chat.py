import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.db.session import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active", server_default="active"
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # Tracks which hard-rule card triggers have already fired in this session.
    # Prevents re-asking the same question.
    # Format: {"missing_goal": true, "missing_weight": true}
    fired_triggers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Multi-Agent Context ─────────────────────────────────────────────────────
    # Stores which agents ran this session + their summary outputs.
    # Used to avoid re-running agents unnecessarily.
    # Schema:
    # {
    #   "extractor": {"status": "completed", "summary": "..."},
    #   "health_monitor": {"status": "skipped", "reason": "no_health_data"},
    #   ...
    # }
    agent_context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Set True after each user message; set False after Agent 1 (extractor) runs.
    # Allows the orchestrator to skip extraction if already done.
    needs_extraction: Mapped[bool] = mapped_column(
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_analysis_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_analysis_logs.id", ondelete="SET NULL"),
    )

    role: Mapped[str] = mapped_column(String(50), nullable=False)
    # user | assistant | system

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Message type: "text" | "card" | "card_response" | "meal_log" | "system"
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        server_default="text",
    )

    # Full ChatCard payload when message_type == "card"
    card: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ChatCardResponse when message_type == "card_response"
    card_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    meta_data: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=None)

    @property
    def metadata_dict(self) -> Optional[dict]:
        """Return meta_data as plain dict, never Pydantic MetaData."""
        if self.meta_data is None:
            return None
        if isinstance(self.meta_data, dict):
            return self.meta_data
        return dict(self.meta_data) if hasattr(self.meta_data, "__iter__") else None

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

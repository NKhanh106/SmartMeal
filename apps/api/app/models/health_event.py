import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class HealthEvent(Base):
    """
    Bảng ghi nhận sự kiện sức khỏe của user.
    Loại: triệu chứng, bệnh, hồi phục, đo lường, ghi chú.
    """
    __tablename__ = "health_events"
    __table_args__ = (
        Index("ix_health_events_user_id", "user_id"),
        Index("ix_health_events_event_date", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # symptom | illness | recovery | measurement | note
    category: Mapped[Optional[str]] = mapped_column(String(50))  # digestive | muscular | metabolic | respiratory | other

    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(20))  # mild | moderate | severe
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    source_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=text("now()"),
    )

    user = relationship("User", back_populates="health_events")
    session = relationship("ChatSession", foreign_keys=[source_session_id])

    def __repr__(self) -> str:
        return f"<HealthEvent(user_id='{self.user_id}', date='{self.event_date}', type='{self.event_type}')>"

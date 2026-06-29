import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Boolean, Index, text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import SleepQualityEnum


class SleepLog(Base):
    """
    Bảng ghi nhận giấc ngủ của user.
    Mỗi record = 1 đêm ngủ.
    """
    __tablename__ = "sleep_logs"
    __table_args__ = (
        Index("ix_sleep_logs_user_id", "user_id"),
        Index("ix_sleep_logs_sleep_date", "sleep_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    sleep_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Thời gian ngủ
    bed_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    wake_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sleep_duration_hours: Mapped[Optional[float]] = mapped_column(Numeric(4, 2))

    # Chất lượng giấc ngủ
    quality: Mapped[Optional[str]] = mapped_column(String(20))  # poor | fair | good | excellent

    # Chi tiết giấc ngủ (định kỳ hỏi)
    wake_up_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # số lần thức giấc
    deep_sleep_hours: Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    rem_sleep_hours: Mapped[Optional[float]] = mapped_column(Numeric(4, 2))

    # Nguồn dữ liệu
    source: Mapped[Optional[str]] = mapped_column(String(50))  # manual | chat_extraction | device
    source_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=text("now()"),
    )

    user = relationship("User", back_populates="sleep_logs")
    session = relationship("ChatSession", foreign_keys=[source_session_id])

    def __repr__(self) -> str:
        return f"<SleepLog(user_id='{self.user_id}', date='{self.sleep_date}', hours={self.sleep_duration_hours})>"

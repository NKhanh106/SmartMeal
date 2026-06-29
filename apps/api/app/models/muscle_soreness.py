import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Boolean, Index, text, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class MuscleSoreness(Base):
    """
    Bảng ghi nhận tình trạng đau cơ của user.
    Theo dõi vùng cơ bị đau, mức độ đau, thời gian hồi phục.
    """
    __tablename__ = "muscle_soreness"
    __table_args__ = (
        Index("ix_muscle_soreness_user_id", "user_id"),
        Index("ix_muscle_soreness_log_date", "log_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    log_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Các vùng cơ bị đau (lưu dạng mảng)
    sore_areas: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=list)
    # Ví dụ: ["chest", "shoulders", "biceps", "back", "legs", "abs", "triceps", "forearms"]

    pain_level: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10 scale
    soreness_type: Mapped[Optional[str]] = mapped_column(String(50))  # acute | delayed | chronic | injury

    # Thông tin bổ sung
    workout_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_recovered: Mapped[bool] = mapped_column(Boolean, default=False)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=text("now()"),
    )

    user = relationship("User", back_populates="muscle_soreness")
    workout_session = relationship("WorkoutPlan", foreign_keys=[workout_session_id])

    def __repr__(self) -> str:
        return f"<MuscleSoreness(user_id='{self.user_id}', date='{self.log_date}', areas='{self.sore_areas}')>"

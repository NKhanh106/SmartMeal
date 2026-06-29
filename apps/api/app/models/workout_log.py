import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Boolean, Index, text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WorkoutLog(Base):
    """
    Bảng ghi nhận lịch sử tập luyện của user.
    Mỗi record = 1 buổi tập.
    """
    __tablename__ = "workout_logs"
    __table_args__ = (
        Index("ix_workout_logs_user_id", "user_id"),
        Index("ix_workout_logs_workout_date", "workout_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    workout_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Thông tin buổi tập
    workout_type: Mapped[Optional[str]] = mapped_column(String(100))  # gym | cardio | yoga | running | swimming | etc
    workout_name: Mapped[Optional[str]] = mapped_column(String(200))
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    intensity: Mapped[Optional[str]] = mapped_column(String(20))  # light | moderate | intense

    # Calories
    calories_burned: Mapped[Optional[float]] = mapped_column(Numeric(7, 2))

    # Thông tin bổ sung
    source: Mapped[Optional[str]] = mapped_column(String(50))  # manual | chat_extraction | device
    source_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    workout_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text)

    completed: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=text("now()"),
    )

    user = relationship("User", back_populates="workout_logs")
    workout_plan = relationship("WorkoutPlan", foreign_keys=[workout_plan_id])

    def __repr__(self) -> str:
        return f"<WorkoutLog(user_id='{self.user_id}', date='{self.workout_date}', type='{self.workout_type}')>"

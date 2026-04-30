import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WorkoutItem(Base):
    __tablename__ = "workout_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workout_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    workout_date: Mapped[Optional[date]] = mapped_column(Date)
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer)
    muscle_group: Mapped[Optional[str]] = mapped_column(String(100))
    exercise_name: Mapped[str] = mapped_column(String(255), nullable=False)

    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    sets: Mapped[Optional[int]] = mapped_column(Integer)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    rest_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    note: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    workout_plan = relationship(
        "WorkoutPlan",
        back_populates="items",
    )

    def __repr__(self) -> str:
        return f"<WorkoutItem(exercise_name='{self.exercise_name}')>"

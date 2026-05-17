import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Exercise(Base):
    """
    Master library of available exercises.
    Seeded from the hardcoded _EXERCISES dict in workout_plans.py.
    Allows admins to manage exercise templates via DB without redeploying.
    """

    __tablename__ = "exercises"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50))  # "cardio", "strength", "flexibility"
    muscle_group: Mapped[str] = mapped_column(String(100))
    difficulty: Mapped[str] = mapped_column(String(20))  # "nguoi_moi", "trung_binh", "nang_cao"
    default_sets: Mapped[int] = mapped_column(Integer, default=3)
    default_reps: Mapped[int] = mapped_column(Integer, default=12)
    default_rest_seconds: Mapped[int] = mapped_column(Integer, default=60)
    calories_per_minute: Mapped[float] = mapped_column(Float, nullable=True)
    equipment_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    instructions: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<Exercise(name='{self.name}', muscle_group='{self.muscle_group}')>"

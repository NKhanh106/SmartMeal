import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import WorkoutDifficultyType


class WorkoutPlan(Base):
    __tablename__ = "workout_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_type: Mapped[Optional[str]] = mapped_column(String(20))
    difficulty: Mapped[WorkoutDifficultyType] = mapped_column(
        Enum(WorkoutDifficultyType, name="workout_difficulty_type", create_type=False),
        nullable=False,
        default=WorkoutDifficultyType.nguoi_moi,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    user = relationship("User", back_populates="workout_plans")
    items = relationship(
        "WorkoutItem",
        back_populates="workout_plan",
        cascade="all, delete-orphan",
    )

    # Unique constraint chỉ có ở DB (partial index trong migration),
    # không đặt ở ORM để cho phép nhiều inactive plans cùng user
    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<WorkoutPlan(user_id='{self.user_id}', plan_name='{self.plan_name}')>"

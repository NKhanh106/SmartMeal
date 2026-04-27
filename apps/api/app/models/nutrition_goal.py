import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import NutritionGoalType


class NutritionGoal(Base):
    __tablename__ = "nutrition_goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    goal_type: Mapped[NutritionGoalType] = mapped_column(
        Enum(NutritionGoalType, name="nutrition_goal_type", create_type=False),
        nullable=False
    )
    
    target_weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    start_date: Mapped[date] = mapped_column(Date, server_default=text("CURRENT_DATE"))
    end_date: Mapped[Optional[date]] = mapped_column(Date)

    bmr_kcal: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    tdee_kcal: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    bmi: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Các chỉ số daily target tính toán
    daily_calorie_target: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    protein_target_g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    carb_target_g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    fat_target_g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    
    note: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()")
    )

    # Đảm bảo (id, user_id) là DUY NHẤT để hỗ trợ composite foreign key ở bảng meal_logs
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_nutrition_goals_id_user_id"),
        Index("uq_nutrition_goals_one_active_per_user", "user_id", unique=True, postgresql_where=text("is_active = true")),
    )

    def __repr__(self) -> str:
        return f"<NutritionGoal(user_id='{self.user_id}', goal_type='{self.goal_type}', active='{self.is_active}')>"

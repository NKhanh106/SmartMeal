import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum, ForeignKey, ForeignKeyConstraint, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ItemSourceType, MealLogSourceType, MealLogStatus, MealTypeEnum


class MealLog(Base):
    __tablename__ = "meal_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="meal_logs")

    nutrition_goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    meal_type: Mapped[MealTypeEnum] = mapped_column(
        Enum(MealTypeEnum, name="meal_type_enum", create_type=False),
        nullable=False,
        default=MealTypeEnum.khac,
    )

    meal_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        nullable=False, 
        server_default=text("now()")
    )

    source: Mapped[MealLogSourceType] = mapped_column(
        Enum(MealLogSourceType, name="meal_log_source", create_type=False),
        nullable=False,
        default=MealLogSourceType.manual,
        server_default="manual",
    )

    status: Mapped[MealLogStatus] = mapped_column(
        Enum(MealLogStatus, name="meal_log_status", create_type=False),
        nullable=False,
        default=MealLogStatus.PENDING,
        server_default="PENDING",
        index=True,
    )

    extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    ai_model: Mapped[Optional[str]] = mapped_column(String(100))
    ai_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    total_calories: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_protein_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_carb_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_fat_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    note: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()")
    )

    items = relationship(
        "MealItem",
        back_populates="meal_log",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["nutrition_goal_id", "user_id"],
            ["nutrition_goals.id", "nutrition_goals.user_id"],
            name="fk_meal_logs_nutrition_goal",
            ondelete="SET NULL",
        ),
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    meal_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_logs.id", ondelete="CASCADE"),
        nullable=False,
    )

    food_nutrition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("food_nutrition.id", ondelete="SET NULL"),
        nullable=True,
    )

    detected_food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_food_name: Mapped[Optional[str]] = mapped_column(String(255))

    estimated_weight_g: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    calories: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    protein_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    carb_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    fat_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    source: Mapped[ItemSourceType] = mapped_column(
        Enum(ItemSourceType, name="item_source_type", create_type=False),
        nullable=False,
        default=ItemSourceType.ai_nhan_dien,
    )

    ai_raw_result: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()")
    )

    meal_log = relationship(
        "MealLog",
        back_populates="items",
    )

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import FoodSourceType


class FoodNutrition(Base):
    __tablename__ = "food_nutrition"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    food_name_vi: Mapped[Optional[str]] = mapped_column(String(255))
    food_name_en: Mapped[Optional[str]] = mapped_column(String(255))
    
    category: Mapped[Optional[str]] = mapped_column(String(100))

    serving_size_g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=100)

    calories_per_100g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    protein_per_100g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    carb_per_100g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    fat_per_100g: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)

    fiber_per_100g: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    sugar_per_100g: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    sodium_mg_per_100g: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

    source: Mapped[FoodSourceType] = mapped_column(
        Enum(FoodSourceType, name="food_source_type", create_type=False),
        nullable=False,
        default=FoodSourceType.he_thong
    )

    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()")
    )

    creator = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<FoodNutrition(name='{self.food_name}', cal='{self.calories_per_100g}', source='{self.source}')>"

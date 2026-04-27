import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.db.session import Base


class DailyRecommendation(Base):
    __tablename__ = "daily_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    recommendation_date: Mapped[date] = mapped_column(Date, nullable=False)

    calories_target: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    protein_target_g: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    carb_target_g: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    fat_target_g: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

    meal_suggestion: Mapped[Optional[str]] = mapped_column(Text)
    workout_suggestion: Mapped[Optional[str]] = mapped_column(Text)
    lifestyle_suggestion: Mapped[Optional[str]] = mapped_column(Text)

    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    ai_raw_response: Mapped[Optional[dict]] = mapped_column(JSONB)
    ai_analysis_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_analysis_logs.id", ondelete="SET NULL"),
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generated")

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        UniqueConstraint("user_id", "recommendation_date", name="uq_daily_recommendation_user_date"),
    )

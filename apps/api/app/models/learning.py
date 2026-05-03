"""
Learning System Models — stores user corrections and learned preferences.

This enables the feedback loop:
  User corrects AI prediction → stored here → future predictions improve

Three types of learning data:
1. FoodCorrection: User changes detected food name or weight
2. MealFeedback: User rates the overall accuracy of a meal log
3. UserPreferenceLearned: Inferred preferences from repeated behavior
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import ItemSourceType


class FoodCorrection(Base):
    """
    Stores when a user corrects the AI's food recognition.

    This is the primary feedback loop for improving food mapping accuracy.
    Every time a user edits an AI-detected food item, we record:
    - What AI detected → what user corrected to
    - Weight adjustments
    - Whether user accepted/rejected the suggestion

    This data feeds the learning service to improve future matching.
    """
    __tablename__ = "food_corrections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Context
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    meal_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_logs.id", ondelete="SET NULL"), nullable=True
    )
    meal_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_items.id", ondelete="SET NULL"), nullable=True
    )

    # What the AI detected
    ai_detected_food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_matched_food_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    ai_estimated_weight_g: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    ai_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    ai_match_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    # What the user corrected to
    corrected_food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    corrected_food_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    corrected_weight_g: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Correction type for analysis
    correction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="food_name_changed | weight_adjusted | food_replaced | food_added | food_removed"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("ix_food_corrections_user_created", "user_id", "created_at"),
        Index("ix_food_corrections_ai_name", "ai_detected_food_name"),
        Index("ix_food_corrections_corrected_name", "corrected_food_name"),
    )


class MealFeedback(Base):
    """
    User feedback on meal log accuracy.

    After logging a meal, users can rate the accuracy.
    This feeds into overall system quality tracking.
    """
    __tablename__ = "meal_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    meal_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_logs.id", ondelete="CASCADE"), nullable=False
    )

    # Feedback score (1-5 stars)
    accuracy_rating: Mapped[Optional[int]] = mapped_column(Integer)
    # Was the nutrition estimate accurate?
    nutrition_accurate: Mapped[Optional[bool]] = mapped_column(Boolean)
    # User's comment
    comment: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("ix_meal_feedback_user", "user_id"),
        Index("ix_meal_feedback_meal", "meal_log_id"),
    )


class UserPreferenceLearned(Base):
    """
    Inferred user preferences from repeated behavior.

    This is NOT manually set — it is computed from meal history.
    Examples:
    - User always adds extra rice to meals → preferred_portion_multiplier = 1.3
    - User logs breakfast at ~7:30am daily → typical_breakfast_time = "07:30"
    - User avoids pork in 90% of meals → disliked_ingredients includes "thịt heo"
    """
    __tablename__ = "user_preferences_learned"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Inferred eating patterns
    typical_meal_times: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="JSON: {bua_sang: '07:30', bua_trua: '12:00', bua_toi: '19:00'}"
    )
    avg_meals_per_day: Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    avg_calories_per_meal: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

    # Inferred food preferences
    frequently_logged_foods: Mapped[Optional[list[str]]] = mapped_column(
        JSONB,
        comment="List of food_name_vi strings user logs most often"
    )
    avoided_foods: Mapped[Optional[list[str]]] = mapped_column(
        JSONB,
        comment="Foods user rarely or never logs"
    )

    # Confidence in learned preferences (based on data volume)
    preference_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        comment="0.0-1.0 confidence in the learned preferences"
    )

    # Meta
    data_points_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()")
    )

    __table_args__ = (
        Index("ix_user_preferences_learned_user", "user_id"),
    )

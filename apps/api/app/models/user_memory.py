import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class UserMemory(Base):
    """
    Persistent 'brain' for each user — continuously updated by Agent 1 (extractor).
    All other agents READ from this table as their primary context source.

    One record per user via UniqueConstraint on user_id.
    """

    __tablename__ = "user_memory"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_memory_user_id"),
        Index("ix_user_memory_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="memory")

    # ── Body State (updated frequently) ─────────────────────────────────────────
    # Schema:
    # {
    #   "weight": 68.5,
    #   "weight_updated_at": "2026-05-13",
    #   "energy_level": "low",           # low | normal | high
    #   "sleep_last_night": 5.5,         # hours, extracted from chat
    #   "digestion_status": "normal",     # normal | bloated | diarrhea | constipated
    #   "muscle_status": {
    #     "sore_areas": ["right_arm", "lower_back"],
    #     "injury_areas": [],
    #     "last_workout": "2026-05-12"
    #   },
    #   "hydration": "low",              # low | normal | high
    #   "last_updated": "2026-05-13T08:30:00"
    # }
    body_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Health Events (append-only log) ─────────────────────────────────────────
    # Schema: array of events, newest first, max 50 entries
    # [
    #   {
    #     "event_id": "uuid",
    #     "date": "2026-05-13",
    #     "type": "symptom",             # symptom | illness | recovery | measurement | note
    #     "category": "digestive",       # digestive | muscular | metabolic | respiratory | other
    #     "description": "Bị tiêu chảy sau bữa tối",
    #     "severity": "mild",           # mild | moderate | severe
    #     "resolved": false,
    #     "source_session_id": "uuid",
    #     "extracted_at": "2026-05-13T09:00:00"
    #   }
    # ]
    health_events: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ── Nutrition Memory ─────────────────────────────────────────────────────────
    # Schema:
    # {
    #   "recent_meals": [               # last 7 days, extracted from chat
    #     {
    #       "date": "2026-05-13",
    #       "meal_type": "lunch",
    #       "items": ["phở bò", "rau thơm", "chanh"],
    #       "estimated_kcal": 450,
    #       "confidence": "high",
    #       "source_session_id": "uuid"
    #     }
    #   ],
    #   "avg_daily_kcal_7d": 1850,
    #   "protein_adequacy": "low",     # low | adequate | high
    #   "common_deficiencies": ["iron", "vitamin_d"],
    #   "foods_to_avoid": [             # confirmed bad reactions
    #     {"food": "sữa", "reason": "tiêu chảy", "confidence": "high"}
    #   ],
    #   "preferred_foods": ["cơm gạo lứt", "ức gà"],
    #   "meal_pattern": "3_meals_regular"
    # }
    nutrition_memory: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Fitness Memory ──────────────────────────────────────────────────────────
    # Schema:
    # {
    #   "current_plan_id": 123,
    #   "last_workout_date": "2026-05-12",
    #   "workout_frequency_7d": 3,
    #   "preferred_workout_types": ["gym", "cardio"],
    #   "current_restrictions": [
    #     {"area": "right_arm", "reason": "muscle_soreness", "since": "2026-05-13"}
    #   ],
    #   "fitness_level": "intermediate",  # beginner | intermediate | advanced
    #   "recent_achievements": []
    # }
    fitness_memory: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Conversation Intelligence ─────────────────────────────────────────────────
    # Rolling summary of last 30 sessions — updated by Agent 1
    # Plain text, max ~800 tokens, used as context injection
    conversation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Long-term stable facts extracted from ALL conversations
    # [
    #   {"fact": "Không ăn được đồ cay", "confidence": "high", "first_seen": "2026-05-01"},
    #   {"fact": "Tập gym buổi sáng trước 7h", "confidence": "medium", "first_seen": "2026-05-05"},
    #   {"fact": "Bị dị ứng tôm", "confidence": "high", "first_seen": "2026-04-20"}
    # ]
    key_facts: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ── Meta ────────────────────────────────────────────────────────────────────
    last_extraction_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    extraction_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

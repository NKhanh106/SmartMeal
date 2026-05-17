import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (
    ActivityLevelType,
    CookingPreferenceEnum,
    DietTypeEnum,
    GenderType,
    MealFrequencyEnum,
    SleepQualityEnum,
    UsageGoalEnum,
)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Khóa ngoại trỏ đến bảng users (UNIQUE vì mỗi user chỉ có 1 profile)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False
    )

    # --- Thông tin nhân khẩu học ---
    gender: Mapped[GenderType] = mapped_column(
        Enum(GenderType, name="gender_type", create_type=False), 
        nullable=False
    )
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Thông tin thể chất hiện tại ---
    height_cm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    current_weight_kg: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)

    # Số đo cơ thể hiện tại (Optional)
    current_body_fat_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_waist_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_neck_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_hip_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_chest_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # --- Mức độ vận động ---
    activity_level: Mapped[ActivityLevelType] = mapped_column(
        Enum(ActivityLevelType, name="activity_level_type", create_type=False),
        nullable=False,
        default=ActivityLevelType.it_van_dong
    )

    # --- Cá nhân hóa thực đơn ---
    # Note: The legacy Text columns were renamed to _text suffix during migration.
    # New code should use the JSONB versions below.
    diet_type: Mapped[DietTypeEnum] = mapped_column(
        Enum(DietTypeEnum, name="diet_type_enum", create_type=False),
        nullable=False,
        default=DietTypeEnum.binh_thuong,
    )
    allergies_text: Mapped[Optional[str]] = mapped_column(Text)
    disliked_foods_text: Mapped[Optional[str]] = mapped_column(Text)
    preferred_foods_text: Mapped[Optional[str]] = mapped_column(Text)

    # --- Ghi chú sức khỏe ---
    health_note: Mapped[Optional[str]] = mapped_column(Text)

    # ── Usage Goal ─────────────────────────────────────────────────────────────
    usage_goal: Mapped[Optional[UsageGoalEnum]] = mapped_column(
        Enum(UsageGoalEnum, name="usage_goal_enum", create_type=False),
        nullable=True,
    )
    usage_goal_note: Mapped[Optional[str]] = mapped_column(String(500))

    # ── Health Conditions (JSONB) ─────────────────────────────────────────────
    health_conditions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    allergies: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    medications: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dietary_restrictions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Lifestyle ──────────────────────────────────────────────────────────────
    sleep_duration_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sleep_quality: Mapped[Optional[SleepQualityEnum]] = mapped_column(
        Enum(SleepQualityEnum, name="sleep_quality_enum", create_type=False),
        nullable=True,
    )
    sleep_schedule: Mapped[Optional[str]] = mapped_column(String(50))
    stress_level: Mapped[Optional[int]] = mapped_column(nullable=True)
    meal_frequency: Mapped[Optional[MealFrequencyEnum]] = mapped_column(
        Enum(MealFrequencyEnum, name="meal_frequency_enum", create_type=False),
        nullable=True,
    )
    cooking_preference: Mapped[Optional[CookingPreferenceEnum]] = mapped_column(
        Enum(CookingPreferenceEnum, name="cooking_preference_enum", create_type=False),
        nullable=True,
    )
    wake_up_time: Mapped[Optional[str]] = mapped_column(String(10))
    sleep_time: Mapped[Optional[str]] = mapped_column(String(10))
    work_schedule: Mapped[Optional[str]] = mapped_column(String(50))

    # ── Taste Preferences (JSONB) ───────────────────────────────────────────
    taste_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cuisine_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    disliked_foods: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    favorite_foods: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    eating_speed: Mapped[Optional[str]] = mapped_column(String(20))
    chew_difficulty: Mapped[Optional[bool]] = mapped_column(nullable=True)

    # --- Audit trails ---
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()")
    )

    # Relationship để map ngược lại cho dễ truy vấn (vd: profile.user)
    # Lưu ý: Sẽ cần khai báo `profile = relationship("UserProfile", back_populates="user", uselist=False)` bên file user.py sau đó
    user = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id='{self.user_id}', height='{self.height_cm}', weight='{self.current_weight_kg}')>"

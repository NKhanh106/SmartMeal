"""
Pydantic schemas for extended user profile fields.
All schemas include the new usage goal, health conditions, lifestyle, and taste preference fields.
"""
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.core.constants import CONDITION_RULES, HEALTH_CONDITIONS
from app.models.enums import (
    ActivityLevelType,
    CookingPreferenceEnum,
    DietTypeEnum,
    GenderType,
    MealFrequencyEnum,
    SleepQualityEnum,
    UsageGoalEnum,
)


# ─── Shared Nested Schemas ───────────────────────────────────────────────────────

class HealthConditionItem(BaseModel):
    condition: str = Field(..., description="Condition ID from HEALTH_CONDITIONS constant")
    severity: Optional[str] = Field("managed", description="managed | unmanaged | resolved")
    diagnosed_year: Optional[int] = Field(None, ge=1950, le=2100)
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("condition")
    @classmethod
    def validate_condition_id(cls, v: str) -> str:
        valid_ids = {c["id"] for c in HEALTH_CONDITIONS}
        if v not in valid_ids:
            raise ValueError(f"Invalid condition ID '{v}'. Must be one of: {sorted(valid_ids)}")
        return v


class AllergyItem(BaseModel):
    allergen: str = Field(..., description="Allergen ID, e.g. 'peanuts', 'milk', 'eggs'")
    severity: Optional[str] = Field("moderate", description="mild | moderate | severe")


class MedicationItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    frequency: Optional[str] = Field(None, max_length=100, description="e.g. 'daily', 'twice a day'")
    note: Optional[str] = Field(None, max_length=500)


class TastePreferencesSchema(BaseModel):
    """Flavor preference scores on a 1-5 scale."""
    spicy: Optional[int] = Field(None, ge=1, le=5)
    sweet: Optional[int] = Field(None, ge=1, le=5)
    salty: Optional[int] = Field(None, ge=1, le=5)
    sour: Optional[int] = Field(None, ge=1, le=5)
    bitter: Optional[int] = Field(None, ge=1, le=5)


# ─── Create / Update Schemas ──────────────────────────────────────────────────

class UsageGoalMixin(BaseModel):
    usage_goal: Optional[UsageGoalEnum] = None
    usage_goal_note: Optional[str] = Field(None, max_length=500)


class HealthConditionsMixin(BaseModel):
    health_conditions: Optional[list[HealthConditionItem]] = None
    allergies: Optional[list[AllergyItem]] = None
    medications: Optional[list[MedicationItem]] = None
    dietary_restrictions: Optional[list[str]] = Field(
        None,
        description="List of dietary restriction IDs e.g. ['vegetarian', 'gluten_free']",
    )


class LifestyleMixin(BaseModel):
    sleep_duration_hours: Optional[float] = Field(None, ge=1.0, le=14.0)
    sleep_quality: Optional[SleepQualityEnum] = None
    sleep_schedule: Optional[str] = Field(None, max_length=50, description="e.g. '23:00-06:30'")
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    meal_frequency: Optional[MealFrequencyEnum] = None
    cooking_preference: Optional[CookingPreferenceEnum] = None
    wake_up_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    sleep_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    work_schedule: Optional[str] = Field(None, max_length=50)

    @model_validator(mode="after")
    def validate_time_range(self) -> "LifestyleMixin":
        if self.wake_up_time and self.sleep_time:
            if self.wake_up_time >= self.sleep_time:
                raise ValueError("wake_up_time must be earlier than sleep_time")
        return self


class TastePreferencesMixin(BaseModel):
    taste_preferences: Optional[TastePreferencesSchema] = None
    cuisine_preferences: Optional[list[str]] = Field(
        None,
        description="List of cuisine IDs e.g. ['vietnamese', 'japanese']",
    )
    disliked_foods: Optional[list[str]] = None
    favorite_foods: Optional[list[str]] = None
    eating_speed: Optional[str] = Field(None, pattern=r"^(slow|normal|fast)$")
    chew_difficulty: Optional[bool] = None


# ─── Full Schemas ──────────────────────────────────────────────────────────────

class UserProfileCreateBase(BaseModel):
    """Base fields for profile creation."""
    gender: GenderType
    date_of_birth: date
    height_cm: float = Field(..., gt=0, le=300)
    current_weight_kg: float = Field(..., gt=0, le=500)
    current_body_fat_percent: Optional[float] = Field(None, ge=0, le=60)
    current_waist_cm: Optional[float] = Field(None, ge=0, le=300)
    current_neck_cm: Optional[float] = Field(None, ge=0, le=100)
    current_hip_cm: Optional[float] = Field(None, ge=0, le=300)
    current_chest_cm: Optional[float] = Field(None, ge=0, le=300)
    activity_level: ActivityLevelType = ActivityLevelType.it_van_dong
    diet_type: DietTypeEnum = DietTypeEnum.binh_thuong


class UserProfileUpdateBase(BaseModel):
    """All fields optional for partial updates."""
    gender: Optional[GenderType] = None
    date_of_birth: Optional[date] = None
    height_cm: Optional[float] = Field(None, gt=0, le=300)
    current_weight_kg: Optional[float] = Field(None, gt=0, le=500)
    current_body_fat_percent: Optional[float] = Field(None, ge=0, le=60)
    current_waist_cm: Optional[float] = Field(None, ge=0, le=300)
    current_neck_cm: Optional[float] = Field(None, ge=0, le=100)
    current_hip_cm: Optional[float] = Field(None, ge=0, le=300)
    current_chest_cm: Optional[float] = Field(None, ge=0, le=300)
    activity_level: Optional[ActivityLevelType] = None
    diet_type: Optional[DietTypeEnum] = None


class UserProfileCreate(
    UserProfileCreateBase,
    UsageGoalMixin,
    HealthConditionsMixin,
    LifestyleMixin,
    TastePreferencesMixin,
):
    @model_validator(mode="after")
    def validate_medical_treatment_requires_condition(self) -> "UserProfileCreate":
        if self.usage_goal == UsageGoalEnum.medical_treatment:
            if not self.health_conditions:
                raise ValueError(
                    "health_conditions must be provided when usage_goal is 'medical_treatment'"
                )
        return self


class UserProfileUpdate(
    UserProfileUpdateBase,
    UsageGoalMixin,
    HealthConditionsMixin,
    LifestyleMixin,
    TastePreferencesMixin,
):
    pass


# ─── Response Schema ───────────────────────────────────────────────────────────

class UserProfileResponse(
    UserProfileCreateBase,
    UsageGoalMixin,
    HealthConditionsMixin,
    LifestyleMixin,
    TastePreferencesMixin,
):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def health_risk_flags(self) -> list[str]:
        """Return list of dietary risk flags based on active health conditions."""
        if not self.health_conditions:
            return []

        flags: list[str] = []

        for condition in self.health_conditions:
            # Handle both dict (from JSONB) and HealthConditionItem object
            if isinstance(condition, dict):
                severity = condition.get("severity", "managed")
                condition_id = condition.get("condition", "")
            else:
                severity = getattr(condition, "severity", "managed")
                condition_id = getattr(condition, "condition", "")

            # Skip resolved conditions
            if severity == "resolved":
                continue

            # Add rules for this condition
            rules = CONDITION_RULES.get(condition_id, [])
            flags.extend(rules)

        return list(set(flags))  # deduplicate

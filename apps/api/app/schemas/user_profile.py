from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ActivityLevelType, DietTypeEnum, GenderType


class UserProfileBase(BaseModel):
    gender: GenderType
    date_of_birth: date

    height_cm: Decimal = Field(..., ge=50, le=250)
    current_weight_kg: Decimal = Field(..., ge=20, le=300)

    current_body_fat_percent: Optional[Decimal] = Field(None, ge=1, le=80)
    current_waist_cm: Optional[Decimal] = Field(None, ge=30, le=250)
    current_neck_cm: Optional[Decimal] = Field(None, ge=20, le=80)
    current_hip_cm: Optional[Decimal] = Field(None, ge=30, le=250)
    current_chest_cm: Optional[Decimal] = Field(None, ge=30, le=250)

    activity_level: ActivityLevelType = ActivityLevelType.it_van_dong
    diet_type: DietTypeEnum = DietTypeEnum.binh_thuong

    allergies: Optional[str] = None
    disliked_foods: Optional[str] = None
    preferred_foods: Optional[str] = None
    health_note: Optional[str] = None

    @model_validator(mode="after")
    def validate_birth_date(self) -> "UserProfileBase":
        if self.date_of_birth > date.today():
            raise ValueError("date_of_birth cannot be in the future.")
        return self


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    gender: Optional[GenderType] = None
    date_of_birth: Optional[date] = None

    height_cm: Optional[Decimal] = Field(None, ge=50, le=250)
    current_weight_kg: Optional[Decimal] = Field(None, ge=20, le=300)

    current_body_fat_percent: Optional[Decimal] = Field(None, ge=1, le=80)
    current_waist_cm: Optional[Decimal] = Field(None, ge=30, le=250)
    current_neck_cm: Optional[Decimal] = Field(None, ge=20, le=80)
    current_hip_cm: Optional[Decimal] = Field(None, ge=30, le=250)
    current_chest_cm: Optional[Decimal] = Field(None, ge=30, le=250)

    activity_level: Optional[ActivityLevelType] = None
    diet_type: Optional[DietTypeEnum] = None

    allergies: Optional[str] = None
    disliked_foods: Optional[str] = None
    preferred_foods: Optional[str] = None
    health_note: Optional[str] = None

    @model_validator(mode="after")
    def validate_birth_date(self) -> "UserProfileUpdate":
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValueError("date_of_birth cannot be in the future.")
        return self


class UserProfileResponse(UserProfileBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import NutritionGoalType


class NutritionGoalCalculateRequest(BaseModel):
    goal_type: NutritionGoalType
    # User có thể nhập target_weight để tính thời gian sau này (optional)
    target_weight_kg: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class NutritionGoalCalculateResponse(BaseModel):
    bmi: float = Field(..., description="Chỉ số khối cơ thể")
    bmr_kcal: int = Field(..., description="Basal Metabolic Rate")
    tdee_kcal: int = Field(..., description="Total Daily Energy Expenditure")
    daily_calorie_target: int = Field(..., description="Calo mục tiêu mỗi ngày")
    protein_target_g: int = Field(..., description="Lượng Protein mục tiêu (gram)")
    carb_target_g: int = Field(..., description="Lượng Carb mục tiêu (gram)")
    fat_target_g: int = Field(..., description="Lượng Fat mục tiêu (gram)")

class NutritionGoalCreate(BaseModel):
    goal_type: NutritionGoalType
    target_weight_kg: Optional[float] = None
    hydration_goal_ml: Optional[int] = Field(default=None, ge=500, le=8000)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "NutritionGoalCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self

class NutritionGoalResponse(BaseModel):
    id: UUID
    user_id: UUID
    goal_type: NutritionGoalType
    target_weight_kg: Optional[float]
    hydration_goal_ml: Optional[int] = None
    start_date: date
    end_date: Optional[date]

    bmi: Optional[float] = None
    bmr_kcal: Optional[float] = None
    tdee_kcal: Optional[float] = None

    daily_calorie_target: float
    protein_target_g: float
    carb_target_g: float
    fat_target_g: float

    note: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NutritionGoalUpdate(BaseModel):
    target_weight_kg: Optional[float] = None
    hydration_goal_ml: Optional[int] = Field(default=None, ge=500, le=8000)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "NutritionGoalUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import NutritionGoalType, WorkoutDifficultyType

# ── WorkoutItem Schemas ────────────────────────────────────────────────────────

class WorkoutItemBase(BaseModel):
    workout_date: Optional[date] = None
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    muscle_group: Optional[str] = Field(None, max_length=100)
    exercise_name: str = Field(..., min_length=1, max_length=255)
    weight_kg: Optional[Decimal] = Field(None, gt=0, le=500)
    sets: Optional[int] = Field(None, ge=1)
    reps: Optional[int] = Field(None, ge=1)
    duration_minutes: Optional[int] = Field(None, ge=1)
    rest_seconds: Optional[int] = Field(None, ge=0)
    order_index: int = Field(default=0, ge=0)
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_day_of_week(self) -> "WorkoutItemBase":
        if self.day_of_week is not None and not (1 <= self.day_of_week <= 7):
            raise ValueError("day_of_week must be between 1 (Monday) and 7 (Sunday).")
        return self


class WorkoutItemCreate(WorkoutItemBase):
    pass


class WorkoutItemUpdate(BaseModel):
    workout_date: Optional[date] = None
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    muscle_group: Optional[str] = Field(None, max_length=100)
    exercise_name: Optional[str] = Field(None, min_length=1, max_length=255)
    weight_kg: Optional[Decimal] = Field(None, gt=0, le=500)
    sets: Optional[int] = Field(None, ge=1)
    reps: Optional[int] = Field(None, ge=1)
    duration_minutes: Optional[int] = Field(None, ge=1)
    rest_seconds: Optional[int] = Field(None, ge=0)
    order_index: Optional[int] = Field(None, ge=0)
    is_completed: Optional[bool] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_day_of_week(self) -> "WorkoutItemUpdate":
        if self.day_of_week is not None and not (1 <= self.day_of_week <= 7):
            raise ValueError("day_of_week must be between 1 (Monday) and 7 (Sunday).")
        return self


class WorkoutItemResponse(BaseModel):
    id: UUID
    workout_plan_id: UUID
    workout_date: Optional[date] = None
    day_of_week: Optional[int] = None
    muscle_group: Optional[str] = None
    exercise_name: str
    weight_kg: Optional[Decimal] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_minutes: Optional[int] = None
    rest_seconds: Optional[int] = None
    order_index: int
    is_completed: bool
    completed_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── WorkoutPlan Schemas ────────────────────────────────────────────────────────

class WorkoutPlanBase(BaseModel):
    plan_name: str = Field(..., min_length=1, max_length=255)
    goal_type: Optional[NutritionGoalType] = None
    difficulty: WorkoutDifficultyType = WorkoutDifficultyType.nguoi_moi
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "WorkoutPlanBase":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self


class WorkoutPlanCreate(WorkoutPlanBase):
    is_active: bool = True


class WorkoutPlanUpdate(BaseModel):
    plan_name: Optional[str] = Field(None, min_length=1, max_length=255)
    goal_type: Optional[NutritionGoalType] = None
    difficulty: Optional[WorkoutDifficultyType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None
    # Sentinel: truyền true để xóa giá trị nullable hiện tại
    clear_end_date: bool = Field(default=False, description="Set to true to clear end_date")
    clear_note: bool = Field(default=False, description="Set to true to clear note")

    @model_validator(mode="after")
    def validate_date_range(self) -> "WorkoutPlanUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self


class WorkoutPlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    plan_name: str
    goal_type: Optional[str] = None
    difficulty: str
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkoutPlanDetailResponse(WorkoutPlanResponse):
    items: list[WorkoutItemResponse] = []


class WorkoutPlanWithItemsCreate(BaseModel):
    plan_name: str = Field(..., min_length=1, max_length=255)
    goal_type: Optional[NutritionGoalType] = None
    difficulty: WorkoutDifficultyType = WorkoutDifficultyType.nguoi_moi
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None
    items: list[WorkoutItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_date_range(self) -> "WorkoutPlanWithItemsCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import MealTypeEnum


class NutritionGoalSummary(BaseModel):
    id: UUID
    goal_type: str

    daily_calorie_target: Optional[Decimal] = None
    protein_target_g: Optional[Decimal] = None
    carb_target_g: Optional[Decimal] = None
    fat_target_g: Optional[Decimal] = None


class MacroProgress(BaseModel):
    consumed: Decimal
    target: Optional[Decimal] = None
    remaining: Optional[Decimal] = None
    percent: Optional[Decimal] = None


class DailyMealSummary(BaseModel):
    id: UUID
    meal_type: MealTypeEnum
    meal_time: datetime

    total_calories: Decimal
    total_protein_g: Decimal
    total_carb_g: Decimal
    total_fat_g: Decimal

    note: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None


class DailyDashboardResponse(BaseModel):
    user_id: UUID
    target_date: date

    active_goal: Optional[NutritionGoalSummary] = None

    total_calories: Decimal
    total_protein_g: Decimal
    total_carb_g: Decimal
    total_fat_g: Decimal

    calories_progress: MacroProgress
    protein_progress: MacroProgress
    carb_progress: MacroProgress
    fat_progress: MacroProgress

    meal_count: int
    auto_detected_count: int = 0
    meals: list[DailyMealSummary]


class WeeklyDailyItem(BaseModel):
    date: date

    total_calories: Decimal
    total_protein_g: Decimal
    total_carb_g: Decimal
    total_fat_g: Decimal

    meal_count: int


class WeeklyDashboardResponse(BaseModel):
    user_id: UUID

    start_date: date
    end_date: date

    active_goal: Optional[NutritionGoalSummary] = None

    total_calories: Decimal
    avg_calories: Decimal

    total_protein_g: Decimal
    total_carb_g: Decimal
    total_fat_g: Decimal

    daily_items: list[WeeklyDailyItem]

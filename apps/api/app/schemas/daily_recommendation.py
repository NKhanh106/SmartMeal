from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DailyPlannerAIResult(BaseModel):
    recommendation_date: date

    calories_target: Optional[Decimal] = Field(None, ge=0)
    protein_target_g: Optional[Decimal] = Field(None, ge=0)
    carb_target_g: Optional[Decimal] = Field(None, ge=0)
    fat_target_g: Optional[Decimal] = Field(None, ge=0)

    meal_suggestion: str
    workout_suggestion: str
    lifestyle_suggestion: str

    summary: str


class DailyRecommendationResponse(BaseModel):
    id: UUID
    user_id: UUID

    recommendation_date: date

    calories_target: Optional[Decimal] = None
    protein_target_g: Optional[Decimal] = None
    carb_target_g: Optional[Decimal] = None
    fat_target_g: Optional[Decimal] = None

    meal_suggestion: Optional[str] = None
    workout_suggestion: Optional[str] = None
    lifestyle_suggestion: Optional[str] = None

    ai_summary: Optional[str] = None
    ai_analysis_log_id: Optional[UUID] = None
    status: str

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateDailyPlannerResponse(BaseModel):
    recommendation: DailyRecommendationResponse

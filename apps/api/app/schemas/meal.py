from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ItemSourceType, MealLogSourceType, MealTypeEnum


class MealItemCreate(BaseModel):
    food_nutrition_id: Optional[UUID] = None

    detected_food_name: Optional[str] = Field(None, max_length=255)
    display_food_name: Optional[str] = Field(None, max_length=255)

    estimated_weight_g: Decimal = Field(..., gt=0)

    source: Optional[ItemSourceType] = None
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)


class MealLogCreate(BaseModel):
    nutrition_goal_id: Optional[UUID] = None

    meal_type: MealTypeEnum = MealTypeEnum.khac
    meal_time: Optional[datetime] = None


    source: MealLogSourceType = MealLogSourceType.manual

    note: Optional[str] = None

    items: list[MealItemCreate] = Field(..., min_length=1)


class MealItemResponse(BaseModel):
    id: UUID
    meal_log_id: UUID

    food_nutrition_id: Optional[UUID] = None

    detected_food_name: str
    display_food_name: Optional[str] = None

    estimated_weight_g: Optional[Decimal] = None

    calories: Decimal
    protein_g: Decimal
    carb_g: Decimal
    fat_g: Decimal

    confidence: Optional[Decimal] = None
    source: ItemSourceType

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MealLogResponse(BaseModel):
    id: UUID

    user_id: UUID
    nutrition_goal_id: Optional[UUID] = None

    meal_type: MealTypeEnum
    meal_time: datetime


    source: MealLogSourceType

    total_calories: Decimal
    total_protein_g: Decimal
    total_carb_g: Decimal
    total_fat_g: Decimal

    note: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    items: list[MealItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MealLogSummaryResponse(BaseModel):
    id: UUID

    user_id: UUID
    meal_type: MealTypeEnum
    meal_time: datetime

    source: MealLogSourceType

    total_calories: Decimal
    total_protein_g: Decimal
    total_carb_g: Decimal
    total_fat_g: Decimal

    note: Optional[str] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

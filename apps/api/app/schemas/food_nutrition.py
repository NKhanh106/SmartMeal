from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FoodSourceType


class FoodNutritionBase(BaseModel):
    food_name: str = Field(..., min_length=1, max_length=255)
    food_name_vi: Optional[str] = Field(None, max_length=255)
    food_name_en: Optional[str] = Field(None, max_length=255)

    category: Optional[str] = Field(None, max_length=100)

    serving_size_g: Decimal = Field(default=Decimal("100"), gt=0)

    calories_per_100g: Decimal = Field(default=Decimal("0"), ge=0)
    protein_per_100g: Decimal = Field(default=Decimal("0"), ge=0)
    carb_per_100g: Decimal = Field(default=Decimal("0"), ge=0)
    fat_per_100g: Decimal = Field(default=Decimal("0"), ge=0)

    fiber_per_100g: Optional[Decimal] = Field(None, ge=0)
    sugar_per_100g: Optional[Decimal] = Field(None, ge=0)
    sodium_mg_per_100g: Optional[Decimal] = Field(None, ge=0)

    source: FoodSourceType = FoodSourceType.he_thong
    external_id: Optional[str] = Field(None, max_length=255)

    is_verified: bool = False
    created_by_user_id: Optional[UUID] = None

class FoodNutritionCreate(FoodNutritionBase):
    pass

class FoodNutritionUpdate(BaseModel):
    food_name: Optional[str] = Field(None, min_length=1, max_length=255)
    food_name_vi: Optional[str] = Field(None, max_length=255)
    food_name_en: Optional[str] = Field(None, max_length=255)

    category: Optional[str] = Field(None, max_length=100)

    serving_size_g: Optional[Decimal] = Field(None, gt=0)

    calories_per_100g: Optional[Decimal] = Field(None, ge=0)
    protein_per_100g: Optional[Decimal] = Field(None, ge=0)
    carb_per_100g: Optional[Decimal] = Field(None, ge=0)
    fat_per_100g: Optional[Decimal] = Field(None, ge=0)

    fiber_per_100g: Optional[Decimal] = Field(None, ge=0)
    sugar_per_100g: Optional[Decimal] = Field(None, ge=0)
    sodium_mg_per_100g: Optional[Decimal] = Field(None, ge=0)

    source: Optional[FoodSourceType] = None
    external_id: Optional[str] = Field(None, max_length=255)

    is_verified: Optional[bool] = None
    created_by_user_id: Optional[UUID] = None

class FoodNutritionResponse(FoodNutritionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NutritionEstimateRequest(BaseModel):
    food_id: UUID
    weight_g: Decimal = Field(..., gt=0)

class NutritionEstimateResponse(BaseModel):
    food_id: UUID
    food_name: str
    weight_g: Decimal

    calories: Decimal
    protein_g: Decimal
    carb_g: Decimal
    fat_g: Decimal

    fiber_g: Optional[Decimal] = None
    sugar_g: Optional[Decimal] = None
    sodium_mg: Optional[Decimal] = None

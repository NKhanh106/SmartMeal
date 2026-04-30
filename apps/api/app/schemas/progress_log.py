from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProgressLogBase(BaseModel):
    log_date: date

    weight_kg: Optional[Decimal] = Field(None, ge=Decimal("20"), le=Decimal("300"))
    body_fat_percent: Optional[Decimal] = Field(None, ge=Decimal("1"), le=Decimal("80"))
    waist_cm: Optional[Decimal] = Field(None, ge=Decimal("30"), le=Decimal("250"))
    neck_cm: Optional[Decimal] = Field(None, ge=Decimal("20"), le=Decimal("80"))
    chest_cm: Optional[Decimal] = Field(None, ge=Decimal("30"), le=Decimal("250"))
    hip_cm: Optional[Decimal] = Field(None, ge=Decimal("30"), le=Decimal("250"))

    progress_photo_url: Optional[str] = None
    note: Optional[str] = None


class ProgressLogCreate(ProgressLogBase):
    pass


class ProgressLogUpdate(BaseModel):
    weight_kg: Optional[Decimal] = Field(None, ge=Decimal("20"), le=Decimal("300"))
    body_fat_percent: Optional[Decimal] = Field(None, ge=Decimal("1"), le=Decimal("80"))
    waist_cm: Optional[Decimal] = Field(None, ge=Decimal("30"), le=Decimal("250"))
    neck_cm: Optional[Decimal] = Field(None, ge=Decimal("20"), le=Decimal("80"))
    chest_cm: Optional[Decimal] = Field(None, ge=Decimal("30"), le=Decimal("250"))
    hip_cm: Optional[Decimal] = Field(None, ge=Decimal("30"), le=Decimal("250"))

    progress_photo_url: Optional[str] = None
    note: Optional[str] = None


class ProgressLogResponse(ProgressLogBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

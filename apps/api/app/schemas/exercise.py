from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExerciseResponse(BaseModel):
    """Exercise library item — read-only, managed by admins via DB."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str | None = None
    muscle_group: str | None = None
    difficulty: str | None = None
    default_sets: int | None = None
    default_reps: int | None = None
    default_rest_seconds: int | None = None
    calories_per_minute: float | None = None
    equipment_needed: bool = False
    instructions: list[str] | None = None
    is_active: bool = True

from __future__ import annotations

import uuid as uuid_lib
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UpdateTarget(str, Enum):
    MEAL_LOG = "meal_log"
    BODY_WEIGHT = "body_weight"
    BODY_MEASUREMENT = "body_measurement"
    HEALTH_SYMPTOM = "health_symptom"
    HEALTH_RECOVERY = "health_recovery"
    HEALTH_CONDITION = "health_condition"
    WORKOUT_LOG = "workout_log"
    MUSCLE_SORENESS = "muscle_soreness"
    PROFILE_METRIC = "profile_metric"
    SLEEP_LOG = "sleep_log"
    STRESS_LOG = "stress_log"
    NUTRITION_GOAL = "nutrition_goal"


class UpdateField(BaseModel):
    label: str
    value: Any
    unit: str | None = None
    display: str


class UpdateProposal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposal_id: str = Field(default_factory=lambda: str(uuid_lib.uuid4()))
    target: UpdateTarget
    fields: list[UpdateField] = Field(default_factory=list)

    summary: str
    detail: str
    confidence: float

    raw_data: dict = Field(default_factory=dict)

    source_message: str = ""
    session_id: str = ""

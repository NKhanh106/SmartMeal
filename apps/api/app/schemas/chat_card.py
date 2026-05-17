from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class CardType(str, Enum):
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    RANK = "rank"
    NUMBER_INPUT = "number_input"
    CONFIRM = "confirm"


class CardOption(BaseModel):
    id: str = Field(..., description="machine-readable key, e.g. 'muscle_gain'")
    label: str = Field(..., description="display text, e.g. 'Tăng cơ'")
    icon: str | None = Field(None, description="emoji or lucide icon name")
    description: str | None = Field(None, description="optional sublabel")


class ChatCard(BaseModel):
    card_id: str = Field(..., description="uuid — used to match response")
    card_type: CardType
    title: str = Field(..., description="main question text")
    subtitle: str | None = Field(None, description="optional context/hint")
    options: list[CardOption] | None = Field(None, description="for select/rank types")
    min_value: float | None = Field(None, description="for number_input")
    max_value: float | None = Field(None, description="for number_input")
    unit: str | None = Field(None, description="e.g. 'kg', 'kcal'")
    placeholder: str | None = Field(None, description="for number_input")
    min_selections: int | None = Field(None, description="for multi_select")
    max_selections: int | None = Field(None, description="for multi_select")
    trigger_reason: str = Field(..., description="internal label: 'missing_goal', 'ai_request', etc.")
    skippable: bool = Field(default=True, description="whether user can dismiss without answering")


class ChatCardResponse(BaseModel):
    card_id: str
    card_type: CardType
    selected_ids: list[str] | None = Field(None, description="for single/multi select")
    ranked_ids: list[str] | None = Field(None, description="for rank")
    number_value: float | None = Field(None, description="for number_input")
    text_value: str | None = Field(None, description="for number_input (text mode)")
    confirmed: bool | None = Field(None, description="for confirm")

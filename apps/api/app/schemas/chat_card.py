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


class ClarificationOption(BaseModel):
    id: str = Field(..., description="machine-readable key, e.g. 'meal_plan'")
    label: str = Field(..., description="display text in Vietnamese, e.g. 'Lên thực đơn'")
    description: str | None = Field(None, description="optional short description in Vietnamese")


class ClarificationPayload(BaseModel):
    """
    Schema that AI returns when it needs clarification.
    Parsed by NutritionAdvisorAgent to generate a ChatCard.

    Only used when: needs_clarification == True
    """
    needs_clarification: bool = Field(
        default=False,
        description="Set to True only when the request is genuinely ambiguous"
    )
    clarification_question: str = Field(
        ...,
        description="Main question displayed as card title (max 60 chars Vietnamese)"
    )
    clarification_hint: str | None = Field(
        None,
        description="Optional subtitle/hint (max 100 chars Vietnamese)"
    )
    clarification_options: list[ClarificationOption] = Field(
        ...,
        description="2–4 distinct options. NEVER fewer than 2 or more than 4."
    )
    confidence: float = Field(
        default=0.3,
        description="How confident the AI is that this clarification covers user intent (0.0–1.0)"
    )
    reason: str | None = Field(
        None,
        description="Internal reason for triggering clarification (not shown to user)"
    )


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


# ─── Clarification Card Builder ─────────────────────────────────────────────────


def build_clarification_card(
    clarification: "ClarificationPayload",
    trigger_reason: str = "intent_ambiguity",
    card_id: str | None = None,
) -> "ChatCard":
    """
    Convert an AI-generated ClarificationPayload into a ChatCard.

    Usage:
        clarification = ClarificationPayload.model_validate(ai_json)
        if clarification.needs_clarification:
            card = build_clarification_card(clarification)
            return AgentResult(..., suggested_card=card)
    """
    from uuid import uuid4

    options = [
        CardOption(id=opt.id, label=opt.label, description=opt.description)
        for opt in clarification.clarification_options
    ]

    return ChatCard(
        card_id=card_id or str(uuid4()),
        card_type=CardType.SINGLE_SELECT,
        title=clarification.clarification_question,
        subtitle=clarification.clarification_hint,
        options=options,
        trigger_reason=trigger_reason,
        skippable=True,
    )

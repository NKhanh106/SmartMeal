"""
Nutrition Pending State API.

Provides endpoints for managing MealLog records in PENDING state:
  GET  /nutrition/pending               — list all pending meal logs for current user
  PATCH /nutrition/pending/{id}/confirm — approve a pending meal log with user-edited data

Pending State Lifecycle:
  1. ExtractorAgent (fire-and-forget, Redis queue) extracts meals from chat message
     and writes PENDING MealLog records with total_calories = sum of items.
  2. Frontend polls GET /nutrition/pending to surface a confirmation card.
  3. User reviews/edits the item list and confirms via PATCH /nutrition/pending/{id}/confirm.
  4. The endpoint acquires a row-level lock (SELECT FOR UPDATE) to prevent race
     conditions between concurrent confirm requests.
  5. Per-item negative clamp (D-5): each field is forced to >= 0 before summing.
  6. BMR floor enforcement (D-2/D-3): rejects if projected daily total < 1.0 × BMR.
  7. Updates extracted_data, recalculates totals, sets status = APPROVED.
  8. Commits transaction and invalidates the user's daily plan cache.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import MealLogStatus, MealTypeEnum
from app.models.meal import MealLog
from app.models.user import User
from app.services.meal_service import confirm_pending_meal_log, get_pending_meal_logs
from app.services.daily_recommendation_service import invalidate_user_plan_cache

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class PendingMealLogResponse(BaseModel):
    """MealLog response that includes PENDING state fields."""
    id: UUID
    user_id: UUID
    meal_type: MealTypeEnum
    meal_time: Any
    source: Any
    status: MealLogStatus
    extracted_data: Any
    total_calories: Any
    total_protein_g: Any
    total_carb_g: Any
    total_fat_g: Any
    ai_model: str | None
    ai_confidence: Any | None
    note: str | None
    created_at: Any
    updated_at: Any

    model_config = ConfigDict(from_attributes=True)


class ConfirmPendingRequest(BaseModel):
    """Request body for confirming a pending meal log.

    The updated_data dict should contain the final list of food items
    (with any quantity adjustments made by the user on the frontend).
    Minimum required shape:
        {
            "items": [
                {"food_name": "...", "calories": N, "protein_g": N, "carb_g": N, "fat_g": N},
                ...
            ]
        }
    """
    updated_data: dict[str, Any]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/pending",
    response_model=list[PendingMealLogResponse],
    summary="List pending meal logs",
)
async def list_pending_meal_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[MealLog]:
    """
    Retrieve all MealLog records with status = PENDING for the authenticated user.

    These records are created by the extractor_queue_worker after AI extracts
    meal data from a chat message. Frontend can poll this endpoint to surface
    a confirmation UI before the meal is officially committed.

    No recalculate_daily_metrics is triggered here — this endpoint is read-only.
    """
    return await get_pending_meal_logs(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/pending/{log_id}/confirm",
    response_model=PendingMealLogResponse,
    summary="Confirm a pending meal log",
)
async def confirm_pending_meal(
    log_id: UUID,
    body: ConfirmPendingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealLog:
    """
    Approve a PENDING MealLog.

    Workflow:
      1. SELECT FOR UPDATE — locks the row to prevent concurrent race conditions
         (A-3 / A-4 fix).
      2. Validates ownership (user_id matches current_user).
      3. Validates the record is still in PENDING state.
      4. Updates extracted_data with user-edited food items.
      5. Recalculates total_calories / protein / carb / fat from updated_data.
      6. Sets status = APPROVED.
      7. Commits the transaction.
      8. Invalidates the user's daily plan cache so recalculation propagates
         to future dashboard queries.

    On success returns the updated MealLog with status = APPROVED.
    """
    meal_log = await confirm_pending_meal_log(
        db=db,
        meal_log_id=log_id,
        user_id=current_user.id,
        updated_data=body.updated_data,
    )

    await db.commit()
    await invalidate_user_plan_cache(current_user.id)

    return meal_log

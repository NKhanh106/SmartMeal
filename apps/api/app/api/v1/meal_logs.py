from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import ensure_user_access, get_current_user
from app.db.session import get_db
from app.models.enums import MealLogSourceType
from app.models.meal import MealLog
from app.models.user import User
from app.schemas.meal import MealLogCreate, MealLogResponse, MealLogSummaryResponse
from app.services.meal_service import create_meal_log_with_items, recalculate_meal_totals
from app.services.daily_recommendation_service import invalidate_user_plan_cache

router = APIRouter(prefix="/meal-logs", tags=["Meal Logs"])


@router.post("/", response_model=MealLogResponse, status_code=status.HTTP_201_CREATED)
async def create_meal_log(
    payload: MealLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meal_log = await create_meal_log_with_items(
        db=db,
        payload=payload,
        user_id=current_user.id,
    )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Meal log could not be created because related data is invalid.",
        )

    await invalidate_user_plan_cache(current_user.id)

    result = await db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.id == meal_log.id)
    )
    return result.scalar_one()


@router.get("/user", response_model=list[MealLogSummaryResponse])
async def get_my_meal_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    return await _list_meal_logs(db, current_user.id, limit, offset)


@router.get("/user/{user_id}", response_model=list[MealLogSummaryResponse])
async def get_user_meal_logs(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await _list_meal_logs(db, user_id, limit, offset)


@router.get("/{meal_log_id}", response_model=MealLogResponse)
async def get_meal_log_detail(
    meal_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meal_log = await _get_meal_log_or_404(db, meal_log_id)
    ensure_user_access(current_user, meal_log.user_id)
    return meal_log


@router.delete("/{meal_log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal_log(
    meal_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meal_log = await _get_meal_log_or_404(db, meal_log_id)
    ensure_user_access(current_user, meal_log.user_id)
    await db.delete(meal_log)
    await db.commit()
    await invalidate_user_plan_cache(meal_log.user_id)
    return None


async def _list_meal_logs(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
    offset: int,
) -> list[MealLog]:
    result = await db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == user_id)
        .order_by(MealLog.meal_time.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def _get_meal_log_or_404(db: AsyncSession, meal_log_id: UUID) -> MealLog:
    result = await db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.id == meal_log_id)
    )
    meal_log = result.scalar_one_or_none()
    if not meal_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal log not found.",
        )
    return meal_log


@router.get("/extracted-today", response_model=list[MealLogSummaryResponse])
async def get_extracted_meals_today(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get meals that were auto-extracted from chat today."""
    from datetime import datetime, timezone

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(MealLog)
        .where(
            MealLog.user_id == current_user.id,
            MealLog.created_at >= today_start,
            MealLog.source.in_([
                MealLogSourceType.chat_extraction,
                MealLogSourceType.chat_command,
            ])
        )
        .order_by(MealLog.meal_time.desc())
    )
    return list(result.scalars().all())


@router.post("/{meal_log_id}/recalculate", response_model=MealLogResponse)
async def recalculate_meal_log_totals(
    meal_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recalculate nutrition totals for a meal log after items are edited.
    Must be called after editing any MealItem within a MealLog.
    """
    meal_log = await _get_meal_log_or_404(db, meal_log_id)
    if meal_log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this meal log.",
        )

    updated = await recalculate_meal_totals(db, meal_log_id)
    return updated

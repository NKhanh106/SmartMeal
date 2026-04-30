from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workout_item import WorkoutItem
from app.models.workout_plan import WorkoutPlan
from app.schemas.workout import WorkoutItemCreate, WorkoutItemUpdate


async def deactivate_other_active_plans(db: AsyncSession, user_id: UUID, except_plan_id: UUID) -> None:
    from sqlalchemy import update
    await db.execute(
        update(WorkoutPlan)
        .where(
            WorkoutPlan.user_id == user_id,
            WorkoutPlan.is_active.is_(True),
            WorkoutPlan.id != except_plan_id,
        )
        .values(is_active=False)
    )


async def create_workout_plan(
    db: AsyncSession,
    user_id: UUID,
    plan_name: str,
    difficulty: str,
    goal_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    note: Optional[str] = None,
    is_active: bool = True,
) -> WorkoutPlan:
    if is_active:
        await deactivate_other_active_plans(db, user_id, except_plan_id=UUID(int=0))

    plan = WorkoutPlan(
        user_id=user_id,
        plan_name=plan_name,
        goal_type=goal_type,
        difficulty=difficulty,
        start_date=start_date or date.today(),
        end_date=end_date,
        is_active=is_active,
        note=note,
    )
    db.add(plan)
    await db.flush()
    return plan


async def get_workout_plan_by_id(
    db: AsyncSession,
    plan_id: UUID,
) -> WorkoutPlan:
    result = await db.execute(
        select(WorkoutPlan)
        .options(selectinload(WorkoutPlan.items))
        .where(WorkoutPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found.",
        )
    return plan


async def get_user_workout_plans(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[WorkoutPlan]:
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == user_id)
        .order_by(WorkoutPlan.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_active_workout_plan(
    db: AsyncSession,
    user_id: UUID,
) -> WorkoutPlan | None:
    result = await db.execute(
        select(WorkoutPlan)
        .options(selectinload(WorkoutPlan.items))
        .where(
            WorkoutPlan.user_id == user_id,
            WorkoutPlan.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def update_workout_plan(
    db: AsyncSession,
    plan_id: UUID,
    user_id: UUID,
    plan_name: Optional[str] = None,
    goal_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_active: Optional[bool] = None,
    note: Optional[str] = None,
    *,
    clear_end_date: bool = False,
    clear_note: bool = False,
) -> WorkoutPlan:
    plan = await get_workout_plan_by_id(db, plan_id)
    if plan.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this workout plan.",
        )

    if plan_name is not None:
        plan.plan_name = plan_name
    if goal_type is not None:
        plan.goal_type = goal_type
    if difficulty is not None:
        plan.difficulty = difficulty
    if start_date is not None:
        plan.start_date = start_date
    if end_date is not None:
        plan.end_date = end_date
    elif clear_end_date:
        plan.end_date = None
    if is_active is not None:
        if is_active and not plan.is_active:
            await deactivate_other_active_plans(db, user_id, except_plan_id=plan.id)
        plan.is_active = is_active
    if note is not None:
        plan.note = note
    elif clear_note:
        plan.note = None

    await db.flush()
    return plan


async def delete_workout_plan(
    db: AsyncSession,
    plan_id: UUID,
    user_id: UUID,
) -> None:
    plan = await get_workout_plan_by_id(db, plan_id)
    if plan.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this workout plan.",
        )
    await db.delete(plan)
    await db.flush()


async def add_workout_item(
    db: AsyncSession,
    plan_id: UUID,
    user_id: UUID,
    payload: WorkoutItemCreate,
) -> WorkoutItem:
    plan = await get_workout_plan_by_id(db, plan_id)
    if plan.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to add items to this plan.",
        )

    item = WorkoutItem(
        workout_plan_id=plan.id,
        workout_date=payload.workout_date,
        day_of_week=payload.day_of_week,
        muscle_group=payload.muscle_group,
        exercise_name=payload.exercise_name,
        weight_kg=float(payload.weight_kg) if payload.weight_kg else None,
        sets=payload.sets,
        reps=payload.reps,
        duration_minutes=payload.duration_minutes,
        rest_seconds=payload.rest_seconds,
        order_index=payload.order_index,
        note=payload.note,
        is_completed=False,
    )
    db.add(item)
    await db.flush()
    return item


async def get_workout_item_by_id(
    db: AsyncSession,
    item_id: UUID,
) -> WorkoutItem:
    result = await db.execute(
        select(WorkoutItem).where(WorkoutItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout item not found.",
        )
    return item


async def update_workout_item(
    db: AsyncSession,
    item_id: UUID,
    user_id: UUID,
    payload: WorkoutItemUpdate,
) -> WorkoutItem:
    item = await get_workout_item_by_id(db, item_id)
    plan = await get_workout_plan_by_id(db, item.workout_plan_id)
    if plan.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this workout item.",
        )

    if payload.workout_date is not None:
        item.workout_date = payload.workout_date
    if payload.day_of_week is not None:
        item.day_of_week = payload.day_of_week
    if payload.muscle_group is not None:
        item.muscle_group = payload.muscle_group
    if payload.exercise_name is not None:
        item.exercise_name = payload.exercise_name
    if payload.weight_kg is not None:
        item.weight_kg = float(payload.weight_kg)
    if payload.sets is not None:
        item.sets = payload.sets
    if payload.reps is not None:
        item.reps = payload.reps
    if payload.duration_minutes is not None:
        item.duration_minutes = payload.duration_minutes
    if payload.rest_seconds is not None:
        item.rest_seconds = payload.rest_seconds
    if payload.order_index is not None:
        item.order_index = payload.order_index
    if payload.is_completed is not None:
        item.is_completed = payload.is_completed
        if payload.is_completed:
            item.completed_at = datetime.now(timezone.utc)
        else:
            item.completed_at = None
    if payload.note is not None:
        item.note = payload.note

    await db.flush()
    return item


async def delete_workout_item(
    db: AsyncSession,
    item_id: UUID,
    user_id: UUID,
) -> None:
    item = await get_workout_item_by_id(db, item_id)
    plan = await get_workout_plan_by_id(db, item.workout_plan_id)
    if plan.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this workout item.",
        )
    await db.delete(item)
    await db.flush()

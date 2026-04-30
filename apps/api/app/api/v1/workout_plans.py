from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.db.session import get_db
from app.models.nutrition_goal import NutritionGoal
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.workout import (
    WorkoutItemCreate,
    WorkoutItemResponse,
    WorkoutItemUpdate,
    WorkoutPlanCreate,
    WorkoutPlanDetailResponse,
    WorkoutPlanResponse,
    WorkoutPlanUpdate,
    WorkoutPlanWithItemsCreate,
)
from app.services import workout_service as service

router = APIRouter(prefix="/workout-plans", tags=["Workout Plans"])

# ─── Auto-generate exercises based on goal type ────────────────────────────────

_EXERCISES: dict[str, list[dict]] = {
    "giam_can": [
        {"day_of_week": 1, "muscle_group": "Full Body", "exercise_name": "Push-ups", "sets": 3, "reps": 15, "rest_seconds": 60, "order_index": 1},
        {"day_of_week": 1, "muscle_group": "Full Body", "exercise_name": "Bodyweight Squats", "sets": 3, "reps": 20, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 1, "muscle_group": "Cardio", "exercise_name": "Jumping Jacks", "sets": 3, "reps": 30, "rest_seconds": 45, "order_index": 3},
        {"day_of_week": 2, "muscle_group": "Full Body", "exercise_name": "Lunges", "sets": 3, "reps": 12, "rest_seconds": 60, "order_index": 1},
        {"day_of_week": 2, "muscle_group": "Core", "exercise_name": "Plank", "sets": 3, "reps": 30, "rest_seconds": 45, "order_index": 2},
        {"day_of_week": 2, "muscle_group": "Cardio", "exercise_name": "Burpees", "sets": 3, "reps": 10, "rest_seconds": 60, "order_index": 3},
        {"day_of_week": 3, "muscle_group": "Upper Body", "exercise_name": "Dips", "sets": 3, "reps": 12, "rest_seconds": 60, "order_index": 1},
        {"day_of_week": 3, "muscle_group": "Lower Body", "exercise_name": "Glute Bridges", "sets": 3, "reps": 15, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 3, "muscle_group": "Cardio", "exercise_name": "Mountain Climbers", "sets": 3, "reps": 20, "rest_seconds": 45, "order_index": 3},
        {"day_of_week": 4, "muscle_group": "Full Body", "exercise_name": "Push-ups", "sets": 3, "reps": 15, "rest_seconds": 60, "order_index": 1},
        {"day_of_week": 4, "muscle_group": "Full Body", "exercise_name": "Bodyweight Squats", "sets": 3, "reps": 20, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 4, "muscle_group": "Core", "exercise_name": "Bicycle Crunches", "sets": 3, "reps": 20, "rest_seconds": 45, "order_index": 3},
        {"day_of_week": 5, "muscle_group": "Full Body", "exercise_name": "Pike Push-ups", "sets": 3, "reps": 10, "rest_seconds": 60, "order_index": 1},
        {"day_of_week": 5, "muscle_group": "Lower Body", "exercise_name": "Step-ups", "sets": 3, "reps": 12, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 5, "muscle_group": "Cardio", "exercise_name": "High Knees", "sets": 3, "reps": 30, "rest_seconds": 45, "order_index": 3},
        {"day_of_week": 6, "muscle_group": "Full Body", "exercise_name": "Superman Hold", "sets": 3, "reps": 12, "rest_seconds": 45, "order_index": 1},
        {"day_of_week": 6, "muscle_group": "Cardio", "exercise_name": "Jump Squats", "sets": 3, "reps": 15, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 6, "muscle_group": "Core", "exercise_name": "Leg Raises", "sets": 3, "reps": 15, "rest_seconds": 45, "order_index": 3},
    ],
    "tang_co": [
        {"day_of_week": 1, "muscle_group": "Chest", "exercise_name": "Push-ups", "sets": 4, "reps": 10, "rest_seconds": 90, "order_index": 1},
        {"day_of_week": 1, "muscle_group": "Back", "exercise_name": "Superman Hold", "sets": 4, "reps": 10, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 1, "muscle_group": "Triceps", "exercise_name": "Diamond Push-ups", "sets": 3, "reps": 8, "rest_seconds": 90, "order_index": 3},
        {"day_of_week": 2, "muscle_group": "Legs", "exercise_name": "Bodyweight Squats", "sets": 4, "reps": 12, "rest_seconds": 90, "order_index": 1},
        {"day_of_week": 2, "muscle_group": "Legs", "exercise_name": "Lunges", "sets": 3, "reps": 10, "rest_seconds": 90, "order_index": 2},
        {"day_of_week": 2, "muscle_group": "Glutes", "exercise_name": "Glute Bridges", "sets": 4, "reps": 12, "rest_seconds": 60, "order_index": 3},
        {"day_of_week": 3, "muscle_group": "Shoulders", "exercise_name": "Pike Push-ups", "sets": 4, "reps": 8, "rest_seconds": 90, "order_index": 1},
        {"day_of_week": 3, "muscle_group": "Back", "exercise_name": "Reverse Snow Angels", "sets": 3, "reps": 12, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 3, "muscle_group": "Core", "exercise_name": "Plank", "sets": 3, "reps": 45, "rest_seconds": 60, "order_index": 3},
        {"day_of_week": 4, "muscle_group": "Chest", "exercise_name": "Wide Push-ups", "sets": 4, "reps": 10, "rest_seconds": 90, "order_index": 1},
        {"day_of_week": 4, "muscle_group": "Biceps", "exercise_name": "Doorway Curls", "sets": 3, "reps": 12, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 4, "muscle_group": "Legs", "exercise_name": "Jump Squats", "sets": 3, "reps": 10, "rest_seconds": 90, "order_index": 3},
        {"day_of_week": 5, "muscle_group": "Full Body", "exercise_name": "Burpees", "sets": 4, "reps": 8, "rest_seconds": 90, "order_index": 1},
        {"day_of_week": 5, "muscle_group": "Core", "exercise_name": "Bicycle Crunches", "sets": 3, "reps": 20, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 5, "muscle_group": "Back", "exercise_name": "Superman Hold", "sets": 4, "reps": 10, "rest_seconds": 60, "order_index": 3},
    ],
    "giu_can": [
        {"day_of_week": 1, "muscle_group": "Full Body", "exercise_name": "Push-ups", "sets": 3, "reps": 12, "rest_seconds": 75, "order_index": 1},
        {"day_of_week": 1, "muscle_group": "Legs", "exercise_name": "Bodyweight Squats", "sets": 3, "reps": 15, "rest_seconds": 75, "order_index": 2},
        {"day_of_week": 1, "muscle_group": "Core", "exercise_name": "Plank", "sets": 3, "reps": 30, "rest_seconds": 60, "order_index": 3},
        {"day_of_week": 2, "muscle_group": "Full Body", "exercise_name": "Lunges", "sets": 3, "reps": 12, "rest_seconds": 75, "order_index": 1},
        {"day_of_week": 2, "muscle_group": "Upper Body", "exercise_name": "Dips", "sets": 3, "reps": 10, "rest_seconds": 75, "order_index": 2},
        {"day_of_week": 2, "muscle_group": "Cardio", "exercise_name": "Jumping Jacks", "sets": 3, "reps": 30, "rest_seconds": 45, "order_index": 3},
        {"day_of_week": 3, "muscle_group": "Full Body", "exercise_name": "Glute Bridges", "sets": 3, "reps": 15, "rest_seconds": 60, "order_index": 1},
        {"day_of_week": 3, "muscle_group": "Core", "exercise_name": "Bicycle Crunches", "sets": 3, "reps": 15, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 3, "muscle_group": "Full Body", "exercise_name": "Superman Hold", "sets": 3, "reps": 10, "rest_seconds": 60, "order_index": 3},
        {"day_of_week": 4, "muscle_group": "Full Body", "exercise_name": "Push-ups", "sets": 3, "reps": 12, "rest_seconds": 75, "order_index": 1},
        {"day_of_week": 4, "muscle_group": "Legs", "exercise_name": "Step-ups", "sets": 3, "reps": 12, "rest_seconds": 75, "order_index": 2},
        {"day_of_week": 4, "muscle_group": "Cardio", "exercise_name": "Mountain Climbers", "sets": 3, "reps": 20, "rest_seconds": 60, "order_index": 3},
        {"day_of_week": 5, "muscle_group": "Full Body", "exercise_name": "Burpees", "sets": 3, "reps": 8, "rest_seconds": 75, "order_index": 1},
        {"day_of_week": 5, "muscle_group": "Core", "exercise_name": "Leg Raises", "sets": 3, "reps": 12, "rest_seconds": 60, "order_index": 2},
        {"day_of_week": 5, "muscle_group": "Upper Body", "exercise_name": "Pike Push-ups", "sets": 3, "reps": 8, "rest_seconds": 75, "order_index": 3},
    ],
}


def _map_activity_to_difficulty(activity_level: str) -> str:
    mapping = {
        "it_van_dong": "nguoi_moi",
        "van_dong_nhe": "nguoi_moi",
        "van_dong_vua": "trung_binh",
        "van_dong_nhieu": "nang_cao",
        "van_dong_rat_nhieu": "nang_cao",
    }
    return mapping.get(activity_level, "trung_binh")


def _plan_name_for_goal(goal_type: str) -> str:
    names = {
        "giam_can": "Weight Loss Plan",
        "tang_co": "Muscle Gain Plan",
        "giu_can": "Maintenance Plan",
    }
    return names.get(goal_type, "Workout Plan")


@router.post("/", response_model=WorkoutPlanDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_workout_plan(
    payload: WorkoutPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await service.create_workout_plan(
        db=db,
        user_id=current_user.id,
        plan_name=payload.plan_name,
        goal_type=payload.goal_type.value if payload.goal_type else None,
        difficulty=payload.difficulty.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        note=payload.note,
        is_active=payload.is_active,
    )
    await db.commit()
    await db.refresh(plan)
    return plan


@router.post("/with-items", response_model=WorkoutPlanDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_workout_plan_with_items(
    payload: WorkoutPlanWithItemsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await service.create_workout_plan(
        db=db,
        user_id=current_user.id,
        plan_name=payload.plan_name,
        goal_type=payload.goal_type.value if payload.goal_type else None,
        difficulty=payload.difficulty.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        note=payload.note,
        is_active=True,
    )

    for item_payload in payload.items:
        await service.add_workout_item(
            db=db,
            plan_id=plan.id,
            user_id=current_user.id,
            payload=item_payload,
        )

    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/user", response_model=list[WorkoutPlanResponse])
async def get_my_workout_plans(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    return await service.get_user_workout_plans(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get("/user/{user_id}", response_model=list[WorkoutPlanResponse])
async def get_user_workout_plans(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await service.get_user_workout_plans(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/user/{user_id}/active", response_model=WorkoutPlanDetailResponse)
async def get_user_active_workout_plan(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    plan = await service.get_active_workout_plan(db=db, user_id=user_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout plan found for this user.",
        )
    return plan


@router.get("/{plan_id}", response_model=WorkoutPlanDetailResponse)
async def get_workout_plan_detail(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await service.get_workout_plan_by_id(db=db, plan_id=plan_id)
    ensure_user_access(current_user, plan.user_id)
    return plan


@router.put("/{plan_id}", response_model=WorkoutPlanDetailResponse)
async def update_workout_plan(
    plan_id: UUID,
    payload: WorkoutPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)

    plan = await service.update_workout_plan(
        db=db,
        plan_id=plan_id,
        user_id=current_user.id,
        plan_name=update_data.get("plan_name"),
        goal_type=update_data.get("goal_type"),
        difficulty=update_data.get("difficulty"),
        start_date=update_data.get("start_date"),
        end_date=update_data.get("end_date"),
        is_active=update_data.get("is_active"),
        note=update_data.get("note"),
        clear_end_date=update_data.get("clear_end_date", False),
        clear_note=update_data.get("clear_note", False),
    )
    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_workout_plan(
        db=db,
        plan_id=plan_id,
        user_id=current_user.id,
    )
    await db.commit()
    return None


# ── Workout Items ──────────────────────────────────────────────────────────────

@router.post("/{plan_id}/items", response_model=WorkoutItemResponse, status_code=status.HTTP_201_CREATED)
async def add_workout_item(
    plan_id: UUID,
    payload: WorkoutItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await service.add_workout_item(
        db=db,
        plan_id=plan_id,
        user_id=current_user.id,
        payload=payload,
    )
    await db.commit()
    await db.refresh(item)
    return item


# ── Workout Item flat routes ────────────────────────────────────────────────────

@router.put("/items/{item_id}", response_model=WorkoutItemResponse)
async def update_workout_item(
    item_id: UUID,
    payload: WorkoutItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await service.update_workout_item(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
        payload=payload,
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_workout_item(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
    )
    await db.commit()
    return None


# ── Auto-generate workout plan ─────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=WorkoutPlanDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_workout_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == current_user.id,
            NutritionGoal.is_active.is_(True),
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active nutrition goal found. Please set your goal first.",
        )

    result_profile = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result_profile.scalar_one_or_none()
    difficulty = _map_activity_to_difficulty(profile.activity_level.value) if profile else "trung_binh"

    exercises = _EXERCISES.get(goal.goal_type.value, _EXERCISES["giu_can"])
    plan = await service.create_workout_plan(
        db=db,
        user_id=current_user.id,
        plan_name=_plan_name_for_goal(goal.goal_type.value),
        goal_type=goal.goal_type.value,
        difficulty=difficulty,
        start_date=goal.start_date,
        end_date=goal.end_date,
        is_active=True,
    )

    for ex in exercises:
        await service.add_workout_item(
            db=db,
            plan_id=plan.id,
            user_id=current_user.id,
            payload=WorkoutItemCreate(**ex),
        )

    await db.commit()
    await db.refresh(plan)
    return plan

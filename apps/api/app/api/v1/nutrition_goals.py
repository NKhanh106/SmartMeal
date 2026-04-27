from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.db.session import get_db
from app.models.nutrition_goal import NutritionGoal
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.nutrition_goal import (
    NutritionGoalCalculateRequest,
    NutritionGoalCalculateResponse,
    NutritionGoalCreate,
    NutritionGoalResponse,
)
from app.services.nutrition_service import calculate_nutrition_targets

router = APIRouter(prefix="/nutrition-goals", tags=["Nutrition Goals"])


async def _get_profile_or_404(db: AsyncSession, user_id: UUID) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile is required before calculating nutrition goals.",
        )
    return profile


@router.post("/calculate", response_model=NutritionGoalCalculateResponse)
async def calculate_goal_preview(
    payload: NutritionGoalCalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await _get_profile_or_404(db, current_user.id)
    targets = calculate_nutrition_targets(profile, payload.goal_type)
    return NutritionGoalCalculateResponse(**targets)


@router.post("/", response_model=NutritionGoalResponse, status_code=status.HTTP_201_CREATED)
async def create_nutrition_goal(
    payload: NutritionGoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await _get_profile_or_404(db, current_user.id)
    targets = calculate_nutrition_targets(profile, payload.goal_type)
    start_date = payload.start_date or date.today()

    await db.execute(
        update(NutritionGoal)
        .where(NutritionGoal.user_id == current_user.id, NutritionGoal.is_active.is_(True))
        .values(is_active=False)
    )

    new_goal = NutritionGoal(
        user_id=current_user.id,
        goal_type=payload.goal_type,
        target_weight_kg=payload.target_weight_kg,
        start_date=start_date,
        end_date=payload.end_date,
        bmi=targets["bmi"],
        bmr_kcal=targets["bmr_kcal"],
        tdee_kcal=targets["tdee_kcal"],
        daily_calorie_target=targets["daily_calorie_target"],
        protein_target_g=targets["protein_target_g"],
        carb_target_g=targets["carb_target_g"],
        fat_target_g=targets["fat_target_g"],
        is_active=True,
    )
    db.add(new_goal)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create nutrition goal because of a data conflict.",
        )

    await db.refresh(new_goal)
    return new_goal


@router.get("/active", response_model=NutritionGoalResponse)
async def get_my_active_nutrition_goal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_active_goal_or_404(db, current_user.id)


@router.get("/{user_id}/active", response_model=NutritionGoalResponse)
async def get_active_nutrition_goal_by_user_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await _get_active_goal_or_404(db, user_id)


async def _get_active_goal_or_404(db: AsyncSession, user_id: UUID) -> NutritionGoal:
    result = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == user_id,
            NutritionGoal.is_active.is_(True),
        )
    )
    active_goal = result.scalar_one_or_none()
    if not active_goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active nutrition goal not found.",
        )
    return active_goal

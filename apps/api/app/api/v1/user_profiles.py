from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.core.cache import cache_delete, cache_get, cache_set, make_cache_key
from app.db.session import get_db
from app.models import UserProfile
from app.models.user import User
from app.schemas.profile import (
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter(prefix="/user-profiles", tags=["User Profiles"])

_USER_PROFILE_TTL = 1800  # 30 minutes


async def _get_profile_or_404(db: AsyncSession, user_id: UUID) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )
    return profile


@router.post("/", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
    payload: UserProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile already exists.",
        )

    # Convert nested schemas to plain dicts for storage
    data = payload.model_dump()
    # Convert health_condition items to dicts
    if data.get("health_conditions"):
        data["health_conditions"] = [dict(c) if hasattr(c, "model_dump") else c for c in data["health_conditions"]]
    if data.get("allergies"):
        data["allergies"] = [dict(a) if hasattr(a, "model_dump") else a for a in data["allergies"]]
    if data.get("medications"):
        data["medications"] = [dict(m) if hasattr(m, "model_dump") else m for m in data["medications"]]
    if data.get("taste_preferences") and hasattr(data["taste_preferences"], "model_dump"):
        data["taste_preferences"] = data["taste_preferences"]

    profile = UserProfile(**data, user_id=current_user.id)
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User profile already exists or references an invalid user.",
        )

    await db.refresh(profile)
    return profile


@router.get("/me", response_model=UserProfileResponse)
async def get_my_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = make_cache_key("user_profile", str(current_user.id))
    cached = await cache_get(cache_key)
    if cached:
        return UserProfileResponse.model_validate(cached)

    profile = await _get_profile_or_404(db, current_user.id)
    await cache_set(cache_key, UserProfileResponse.model_validate(profile).model_dump(mode="json"), _USER_PROFILE_TTL)
    return profile


@router.put("/me", response_model=UserProfileResponse)
async def update_my_user_profile(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await _get_profile_or_404(db, current_user.id)

    # Capture the old usage_goal before updating
    old_usage_goal = profile.usage_goal

    for key, value in payload.model_dump(exclude_unset=True).items():
        # Convert nested Pydantic models to plain dicts for JSONB columns
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    await cache_delete(make_cache_key("user_profile", str(current_user.id)))

    # If usage_goal was just set or changed, suggest creating a matching nutrition goal
    new_usage_goal = profile.usage_goal
    if new_usage_goal and new_usage_goal != old_usage_goal:
        _suggest_nutrition_goal_from_usage(current_user.id, new_usage_goal, profile, db)

    return profile


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await _get_profile_or_404(db, user_id)


@router.put("/{user_id}", response_model=UserProfileResponse)
async def update_user_profile_by_id(
    user_id: UUID,
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    profile = await _get_profile_or_404(db, user_id)

    # Capture the old usage_goal before updating
    old_usage_goal = profile.usage_goal

    for key, value in payload.model_dump(exclude_unset=True).items():
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    await cache_delete(make_cache_key("user_profile", str(user_id)))

    # If usage_goal was just set or changed, suggest creating a matching nutrition goal
    new_usage_goal = profile.usage_goal
    if new_usage_goal and new_usage_goal != old_usage_goal:
        _suggest_nutrition_goal_from_usage(user_id, new_usage_goal, profile, db)

    return profile


async def _suggest_nutrition_goal_from_usage(
    user_id: UUID,
    usage_goal: str,
    profile: UserProfile,
    db: AsyncSession,
) -> None:
    """
    Suggest a nutrition goal when a usage_goal is set in the profile.
    Maps usage_goal -> goal_type and creates a new active nutrition goal.
    Does NOT overwrite an existing active goal of the same type.
    """
    from app.core.constants import USAGE_GOAL_TO_NUTRITION_GOAL
    from app.services.nutrition_service import calculate_nutrition_targets
    from app.models.nutrition_goal import NutritionGoal
    from sqlalchemy import select, update
    from datetime import date

    goal_type_str = USAGE_GOAL_TO_NUTRITION_GOAL.get(usage_goal)
    if not goal_type_str:
        return

    try:
        from app.models.enums import NutritionGoalType
        goal_type = NutritionGoalType(goal_type_str)
    except (ValueError, ImportError):
        return

    # Check if an active goal of this type already exists
    existing = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == user_id,
            NutritionGoal.goal_type == goal_type,
            NutritionGoal.is_active.is_(True),
        )
    )
    if existing.scalar_one_or_none():
        return  # Already has a matching goal — don't overwrite

    # Check profile has enough data for BMR/TDEE
    if not profile.current_weight_kg or not profile.height_cm:
        return

    try:
        age_years = calculate_age(profile.date_of_birth)
    except (ValueError, TypeError):
        return

    try:
        targets = calculate_nutrition_targets(profile, goal_type=goal_type)
    except (ValueError, TypeError, ArithmeticError):
        return

    # Deactivate any existing active goals
    await db.execute(
        update(NutritionGoal)
        .where(NutritionGoal.user_id == user_id, NutritionGoal.is_active.is_(True))
        .values(is_active=False)
    )

    new_goal = NutritionGoal(
        user_id=user_id,
        goal_type=goal_type,
        start_date=date.today(),
        bmi=targets.get("bmi"),
        bmr_kcal=targets.get("bmr_kcal"),
        tdee_kcal=targets.get("tdee_kcal"),
        daily_calorie_target=targets.get("daily_calorie_target"),
        protein_target_g=targets.get("protein_target_g"),
        carb_target_g=targets.get("carb_target_g"),
        fat_target_g=targets.get("fat_target_g"),
        is_active=True,
    )
    db.add(new_goal)
    await db.commit()


def calculate_age(dob) -> int:
    """Calculate age from a date object."""
    from datetime import date
    today = date.today()
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age

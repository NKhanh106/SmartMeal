from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import FoodSourceType
from app.models.food_nutrition import FoodNutrition
from app.models.user import User
from app.schemas.food_nutrition import (
    FoodNutritionCreate,
    FoodNutritionResponse,
    FoodNutritionUpdate,
    NutritionEstimateRequest,
    NutritionEstimateResponse,
)
from app.services.food_nutrition_service import calculate_nutrition_by_weight

router = APIRouter(prefix="/food-nutrition", tags=["Food Nutrition"])


@router.post("/", response_model=FoodNutritionResponse, status_code=status.HTTP_201_CREATED)
async def create_food_nutrition(
    payload: FoodNutritionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food_data = payload.model_dump()
    if current_user.role != "admin":
        food_data["source"] = FoodSourceType.thu_cong
        food_data["is_verified"] = False
        food_data["created_by_user_id"] = current_user.id
    elif food_data.get("created_by_user_id") is None:
        food_data["created_by_user_id"] = current_user.id

    food = FoodNutrition(**food_data)
    db.add(food)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Food nutrition already exists or references invalid data.",
        )

    await db.refresh(food)
    return food


@router.get("/", response_model=list[FoodNutritionResponse])
async def list_food_nutrition(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(
        select(FoodNutrition)
        .order_by(FoodNutrition.food_name.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/search", response_model=list[FoodNutritionResponse])
async def search_food_nutrition(
    keyword: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
):
    search_pattern = f"%{keyword.strip()}%"
    result = await db.execute(
        select(FoodNutrition)
        .where(
            or_(
                FoodNutrition.food_name.ilike(search_pattern),
                FoodNutrition.food_name_vi.ilike(search_pattern),
                FoodNutrition.food_name_en.ilike(search_pattern),
            )
        )
        .order_by(FoodNutrition.is_verified.desc(), FoodNutrition.food_name.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{food_id}", response_model=FoodNutritionResponse)
async def get_food_nutrition(
    food_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await _get_food_or_404(db, food_id)


@router.put("/{food_id}", response_model=FoodNutritionResponse)
async def update_food_nutrition(
    food_id: UUID,
    payload: FoodNutritionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = await _get_food_or_404(db, food_id)
    _ensure_food_write_access(current_user, food)

    update_data = payload.model_dump(exclude_unset=True)
    if current_user.role != "admin":
        update_data.pop("source", None)
        update_data.pop("is_verified", None)
        update_data.pop("created_by_user_id", None)

    for key, value in update_data.items():
        setattr(food, key, value)

    await db.commit()
    await db.refresh(food)
    return food


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_nutrition(
    food_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = await _get_food_or_404(db, food_id)
    _ensure_food_write_access(current_user, food)
    await db.delete(food)
    await db.commit()
    return None


@router.post("/estimate", response_model=NutritionEstimateResponse)
async def estimate_food_nutrition(
    payload: NutritionEstimateRequest,
    db: AsyncSession = Depends(get_db),
):
    food = await _get_food_or_404(db, payload.food_id)
    calculated_result = calculate_nutrition_by_weight(
        food=food,
        weight_g=payload.weight_g,
    )
    return NutritionEstimateResponse(**calculated_result)


async def _get_food_or_404(db: AsyncSession, food_id: UUID) -> FoodNutrition:
    result = await db.execute(select(FoodNutrition).where(FoodNutrition.id == food_id))
    food = result.scalar_one_or_none()
    if not food:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food nutrition not found.",
        )
    return food


def _ensure_food_write_access(current_user: User, food: FoodNutrition) -> None:
    if current_user.role == "admin":
        return
    if food.created_by_user_id != current_user.id or food.source != FoodSourceType.thu_cong:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify manually created foods that belong to you.",
        )

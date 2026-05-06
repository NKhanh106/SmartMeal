import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ItemSourceType
from app.models.food_nutrition import FoodNutrition
from app.models.meal import MealItem, MealLog
from app.models.nutrition_goal import NutritionGoal
from app.schemas.meal import MealLogCreate


def round_decimal(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def calculate_item_nutrition(food: Optional[FoodNutrition], weight_g: Decimal) -> dict:
    if food is None:
        return {
            "calories": round_decimal(Decimal("0")),
            "protein_g": round_decimal(Decimal("0")),
            "carb_g": round_decimal(Decimal("0")),
            "fat_g": round_decimal(Decimal("0")),
        }
    ratio = weight_g / Decimal("100")
    calories = Decimal(str(food.calories_per_100g)) * ratio
    protein_g = Decimal(str(food.protein_per_100g)) * ratio
    carb_g = Decimal(str(food.carb_per_100g)) * ratio
    fat_g = Decimal(str(food.fat_per_100g)) * ratio

    return {
        "calories": round_decimal(calories),
        "protein_g": round_decimal(protein_g),
        "carb_g": round_decimal(carb_g),
        "fat_g": round_decimal(fat_g),
    }


async def create_meal_log_with_items(
    db: AsyncSession,
    payload: MealLogCreate,
    user_id: uuid.UUID,
) -> MealLog:
    meal_time = payload.meal_time or datetime.now(timezone.utc)

    if payload.nutrition_goal_id is not None:
        goal_result = await db.execute(
            select(NutritionGoal).where(
                NutritionGoal.id == payload.nutrition_goal_id,
                NutritionGoal.user_id == user_id,
            )
        )
        if goal_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nutrition goal is invalid for this user.",
            )

    meal_log = MealLog(
        user_id=user_id,
        nutrition_goal_id=payload.nutrition_goal_id,
        meal_type=payload.meal_type,
        meal_time=meal_time,
        image_url=payload.image_url,
        image_storage_path=payload.image_storage_path,
        note=payload.note,
        total_calories=0,
        total_protein_g=0,
        total_carb_g=0,
        total_fat_g=0,
    )

    db.add(meal_log)
    await db.flush()

    total_calories = Decimal("0")
    total_protein = Decimal("0")
    total_carb = Decimal("0")
    total_fat = Decimal("0")

    # ── Batch-fetch all foods upfront to avoid N+1 queries ────────────────────
    food_ids = [item.food_nutrition_id for item in payload.items if item.food_nutrition_id is not None]
    food_map: dict[uuid.UUID, FoodNutrition] = {}
    if food_ids:
        food_result = await db.execute(
            select(FoodNutrition).where(FoodNutrition.id.in_(food_ids))
        )
        food_map = {food.id: food for food in food_result.scalars().all()}

    for item_payload in payload.items:
        food_id = item_payload.food_nutrition_id
        detected_name = item_payload.detected_food_name

        food = food_map.get(food_id) if food_id else None
        if food_id is not None and food is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Food nutrition not found: {food_id}",
            )

        nutrition = calculate_item_nutrition(food, item_payload.estimated_weight_g)

        meal_item = MealItem(
            meal_log_id=meal_log.id,
            food_nutrition_id=food.id if food else None,
            detected_food_name=detected_name or (food.food_name if food else "Unknown"),
            display_food_name=item_payload.display_food_name or (food.food_name if food else detected_name),
            estimated_weight_g=float(item_payload.estimated_weight_g),
            calories=float(nutrition["calories"]),
            protein_g=float(nutrition["protein_g"]),
            carb_g=float(nutrition["carb_g"]),
            fat_g=float(nutrition["fat_g"]),
            confidence=float(item_payload.confidence) if item_payload.confidence is not None else None,
            source=item_payload.source or ItemSourceType.ai_nhan_dien,
        )

        db.add(meal_item)
        total_calories += nutrition["calories"]
        total_protein += nutrition["protein_g"]
        total_carb += nutrition["carb_g"]
        total_fat += nutrition["fat_g"]

    meal_log.total_calories = float(round_decimal(total_calories))
    meal_log.total_protein_g = float(round_decimal(total_protein))
    meal_log.total_carb_g = float(round_decimal(total_carb))
    meal_log.total_fat_g = float(round_decimal(total_fat))

    await db.flush()
    return meal_log


async def recalculate_meal_totals(db: AsyncSession, meal_log_id):
    result = await db.execute(select(MealItem).where(MealItem.meal_log_id == meal_log_id))
    items = result.scalars().all()

    log_result = await db.execute(select(MealLog).where(MealLog.id == meal_log_id))
    meal_log = log_result.scalar_one_or_none()
    if not meal_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal log not found.",
        )

    meal_log.total_calories = float(round_decimal(sum(Decimal(str(item.calories)) for item in items)))
    meal_log.total_protein_g = float(round_decimal(sum(Decimal(str(item.protein_g)) for item in items)))
    meal_log.total_carb_g = float(round_decimal(sum(Decimal(str(item.carb_g)) for item in items)))
    meal_log.total_fat_g = float(round_decimal(sum(Decimal(str(item.fat_g)) for item in items)))

    await db.flush()
    return meal_log

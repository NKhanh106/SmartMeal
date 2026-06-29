import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

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
        source=payload.source,
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

    # Clamp negative values to zero — a meal cannot have negative calories/nutrients.
    neg_warn = []
    for item in items:
        for field, val in [("calories", item.calories), ("protein_g", item.protein_g),
                           ("carb_g", item.carb_g), ("fat_g", item.fat_g)]:
            if val is not None and float(val) < 0:
                neg_warn.append(f"{field}={val} on item {item.id}")

    total_cal = float(round_decimal(sum(Decimal(str(item.calories)) for item in items)))
    total_prot = float(round_decimal(sum(Decimal(str(item.protein_g)) for item in items)))
    total_carb = float(round_decimal(sum(Decimal(str(item.carb_g)) for item in items)))
    total_fat = float(round_decimal(sum(Decimal(str(item.fat_g)) for item in items)))

    meal_log.total_calories = max(total_cal, 0.0)
    meal_log.total_protein_g = max(total_prot, 0.0)
    meal_log.total_carb_g = max(total_carb, 0.0)
    meal_log.total_fat_g = max(total_fat, 0.0)

    await db.flush()
    return meal_log


# ── Pending State Service Functions ──────────────────────────────────────────

async def get_pending_meal_logs(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[MealLog]:
    """
    Retrieve all MealLog records with status = PENDING for a given user.
    Ordered by meal_time descending (most recent first).
    """
    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == user_id)
        .where(MealLog.status == "PENDING")
        .order_by(MealLog.meal_time.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def confirm_pending_meal_log(
    db: AsyncSession,
    meal_log_id: uuid.UUID,
    user_id: uuid.UUID,
    updated_data: dict[str, Any],
) -> MealLog:
    """
    A-3 / A-4 fix: SELECT FOR UPDATE prevents race condition when two concurrent
    requests try to confirm/reject the same pending meal log.

    D-5 fix: Per-item negative clamp — each food item's calories/macros are
    forced to 0 before summing to prevent a single malicious item from inflating
    totals or bypassing the floor check.

    D-2 / D-3 fix: BMR floor enforcement — after aggregating totals from the
    approved list, the function queries all APPROVED meals for the same user on
    the same date and verifies the projected daily sum does not fall below
    1.0 × BMR. If it would, the entire operation is rejected with HTTP 400.

    Steps:
    1. SELECT FOR UPDATE to lock the row and read current status.
    2. Guard: reject if already APPROVED or REJECTED.
    3. Guard: reject if not owned by requesting user.
    4. Per-item negative clamp (D-5).
    5. Aggregate totals and BMR floor check (D-2 / D-3).
    6. Update extracted_data and status = APPROVED.
    7. Caller must commit + close session.
    """
    from datetime import date, datetime as dt
    from decimal import Decimal as D
    from sqlalchemy import func

    from app.models.enums import MealLogStatus
    from app.models.nutrition_goal import NutritionGoal

    # A-3: Row-level lock — blocks other transactions from reading/writing
    # this row until the current transaction commits or rolls back.
    result = await db.execute(
        select(MealLog)
        .where(MealLog.id == meal_log_id)
        .with_for_update()
    )
    meal_log = result.scalar_one_or_none()

    if not meal_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal log not found.",
        )

    if meal_log.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this meal log.",
        )

    if meal_log.status != MealLogStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Meal log is already in '{meal_log.status}' state and cannot be confirmed.",
        )

    # ── D-5: Per-item negative clamp before any calculation ────────────────────
    # A malicious or buggy item with calories=-500 must never affect totals.
    items: list[dict[str, Any]] = updated_data.get("items") or []
    for item in items:
        for field in ("calories", "protein_g", "carb_g", "fat_g"):
            raw = item.get(field)
            if raw is None:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                item[field] = 0.0
                continue
            item[field] = max(val, 0.0)

    # ── D-2 / D-3: BMR floor enforcement ────────────────────────────────────
    # Fetch the user's active NutritionGoal to obtain BMR.
    goal_result = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == user_id,
            NutritionGoal.is_active == True,  # noqa: E712
        )
    )
    active_goal: NutritionGoal | None = goal_result.scalar_one_or_none()

    if active_goal is not None and active_goal.bmr_kcal is not None:
        bmr = float(active_goal.bmr_kcal)
        floor = bmr * 1.0  # MINIMUM_CALORIE_FLOOR_FACTOR = 1.0
        meal_cal = sum(i.get("calories", 0) for i in items)
        meal_dt  = meal_log.meal_time
        meal_date = meal_dt.date() if meal_dt else date.today()

        # Sum all APPROVED meals for this user on the same date.
        # The current meal is still PENDING so not included yet.
        day_start = dt.combine(meal_date, dt.min.time()).replace(tzinfo=timezone.utc)
        day_end   = dt.combine(meal_date, dt.max.time()).replace(tzinfo=timezone.utc)

        existing_result = await db.execute(
            select(func.coalesce(func.sum(MealLog.total_calories), 0))
            .where(
                MealLog.user_id == user_id,
                MealLog.status == MealLogStatus.APPROVED,
                MealLog.meal_time >= day_start,
                MealLog.meal_time <= day_end,
            )
        )
        existing_total: float = float(existing_result.scalar() or 0)
        projected_total = existing_total + meal_cal

        if projected_total < floor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Approved meal would bring daily total ({projected_total:.0f} kcal) "
                    f"below BMR floor ({floor:.0f} kcal). "
                    "Reject this meal or adjust other entries first."
                ),
            )

    # ── Step 4: Update extracted_data with clamped values ─────────────────────
    meal_log.extracted_data = updated_data

    # ── Step 5: Recalculate totals from D-5-clamped items ────────────────────
    total_cal  = sum(i.get("calories", 0)  for i in items)
    total_prot = sum(i.get("protein_g", 0) for i in items)
    total_carb = sum(i.get("carb_g", 0)   for i in items)
    total_fat  = sum(i.get("fat_g", 0)    for i in items)

    meal_log.total_calories  = round_decimal(D(str(max(total_cal,  0.0))))
    meal_log.total_protein_g = round_decimal(D(str(max(total_prot, 0.0))))
    meal_log.total_carb_g    = round_decimal(D(str(max(total_carb, 0.0))))
    meal_log.total_fat_g     = round_decimal(D(str(max(total_fat,  0.0))))

    # ── Step 6: Mark as APPROVED ─────────────────────────────────────────────
    meal_log.status = MealLogStatus.APPROVED

    await db.flush()
    return meal_log

"""
Meal extraction service for SmartMeal chatbot.

This module handles:
1. Passive extraction: extracting meal data from chat conversations
2. Active extraction: processing explicit meal logging commands from chat
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.core.config import settings
from app.models.enums import ItemSourceType, MealLogSourceType, MealTypeEnum
from app.models.food_nutrition import FoodNutrition
from app.models.meal import MealItem, MealLog
from app.schemas.meal import MealLogCreate, MealItemCreate
from app.services.meal_service import create_meal_log_with_items

logger = logging.getLogger("smartmeal.meal_extraction")

# ─── Extraction Prompt ────────────────────────────────────────────────────────

MEAL_EXTRACTION_PROMPT = """You are a nutrition extraction engine. Analyze the following conversation and extract any food or drink the user mentioned consuming.

User said: "{user_message}"
AI response context: {ai_response}

Return a JSON array. Each item must have:
- food_name: string (name of the food/drink)
- quantity: number (estimated serving size)
- unit: string (g, ml, piece, bowl, cup, etc.)
- meal_type: "bua_sang" | "bua_trua" | "bua_toi" | "an_vat" | null
- confidence: "high" | "medium" | "low"

If nothing was consumed or mentioned as consumed/planned to eat, return: []

Only include items the user clearly consumed or is planning to eat NOW. Ignore hypothetical or past mentions.

Respond with raw JSON only. No explanation."""


def detect_meal_command(message: str) -> tuple[bool, str | None]:
    """
    Detect if message contains a meal logging command.
    Returns (is_command, food_mention).
    """
    patterns = [
        r"^(?:log|add|track)\s+(?:that\s+)?(.+)",
        r"^(?:i\s+)?(?:just\s+)?(?:ate|had)\s+(.+?)(?:\s+please)?$",
        r"^(?:i\s+)?(?:will\s+)?(?:eat|have)\s+(.+?)(?:\s+for\s+(?:my\s+)?(?:breakfast|lunch|dinner|snack))?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, message.strip(), re.IGNORECASE)
        if match:
            return True, match.group(1).strip()

    return False, None


def infer_meal_type_from_time() -> MealTypeEnum:
    """Infer meal type from current server time."""
    now = datetime.now(timezone.utc).hour

    if 5 <= now < 11:
        return MealTypeEnum.bua_sang
    elif 11 <= now < 15:
        return MealTypeEnum.bua_trua
    elif 15 <= now < 21:
        return MealTypeEnum.bua_toi
    else:
        return MealTypeEnum.an_vat


async def _extract_meals_from_text(
    user_message: str,
    ai_response: str = "",
) -> list[dict]:
    """
    Call AI to extract meal data from text.
    Returns list of meal items.
    """
    prompt = MEAL_EXTRACTION_PROMPT.format(
        user_message=user_message,
        ai_response=ai_response[:500] if ai_response else "",
    )

    provider = get_ai_provider(settings.AI_CHAT_PROVIDER)

    try:
        from fastapi.concurrency import run_in_threadpool

        response = await run_in_threadpool(
            provider.generate_text,
            system_prompt="You are a nutrition extraction engine. Return only JSON.",
            user_prompt=prompt,
            temperature=0.1,
        )

        # Parse JSON response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        meals = json.loads(response.strip())
        if not isinstance(meals, list):
            return []

        # Filter low confidence
        return [m for m in meals if m.get("confidence", "low") != "low"]

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse meal extraction JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Meal extraction failed: {e}")
        return []


async def _find_matching_food(
    db: AsyncSession,
    food_name: str,
) -> tuple[FoodNutrition | None, float]:
    """
    Try to find a matching food in the database.
    Returns (food, confidence_score).
    """
    search_term = food_name.lower().strip()

    # Try exact match first
    result = await db.execute(
        select(FoodNutrition).where(
            FoodNutrition.food_name.ilike(f"%{search_term}%")
        ).limit(5)
    )
    foods = list(result.scalars().all())

    if not foods:
        return None, 0.0

    # Score by match quality
    for food in foods:
        if search_term == food.food_name.lower():
            return food, 1.0
        if food.food_name.lower().startswith(search_term):
            return food, 0.9
        if search_term in food.food_name.lower():
            return food, 0.7

    return foods[0], 0.5


async def _check_recent_duplicate(
    db: AsyncSession,
    user_id: UUID,
    food_name: str,
    minutes: int = 10,
) -> bool:
    """Check if a similar meal was logged within the last N minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    result = await db.execute(
        select(MealItem)
        .join(MealLog)
        .where(
            MealLog.user_id == user_id,
            MealItem.detected_food_name.ilike(f"%{food_name}%"),
            MealLog.created_at >= cutoff,
        )
        .limit(1)
    )

    return result.scalar_one_or_none() is not None


async def extract_meals_from_message(
    db: AsyncSession,
    user_id: UUID,
    user_message: str,
    ai_response: str = "",
) -> list[MealLog]:
    """
    Extract meal data from a chat message and create MealLog entries.
    This runs asynchronously and does NOT block the chat response.

    Returns list of created MealLogs.
    """
    if not user_message.strip():
        return []

    # Extract meals using AI
    extracted = await _extract_meals_from_text(user_message, ai_response)

    if not extracted:
        return []

    # Batch check for recent duplicates in a single query
    food_names = [item.get("food_name", "") for item in extracted if item.get("food_name")]
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    recent_foods: set[str] = set()
    if food_names:
        from sqlalchemy import or_
        conditions = [
            MealItem.detected_food_name.ilike(f"%{name}%") for name in food_names
        ]
        dup_result = await db.execute(
            select(MealItem.detected_food_name)
            .join(MealLog)
            .where(
                MealLog.user_id == user_id,
                MealLog.created_at >= cutoff,
            )
            .where(or_(*conditions))
            .distinct()
        )
        recent_foods = {row.lower() for row in dup_result.scalars().all()}

    # Batch-fetch all food matches (cache per food name)
    food_cache: dict[str, tuple[FoodNutrition | None, float]] = {}

    created_logs = []

    for item in extracted:
        food_name = item.get("food_name", "")
        if not food_name or food_name.lower() in recent_foods:
            continue

        # Use cached food lookup instead of per-item DB query
        if food_name not in food_cache:
            food_cache[food_name] = await _find_matching_food(db, food_name)
        food, _ = food_cache[food_name]

        # Infer or use provided meal type
        meal_type_str = item.get("meal_type")
        if meal_type_str:
            try:
                meal_type = MealTypeEnum(meal_type_str)
            except ValueError:
                meal_type = infer_meal_type_from_time()
        else:
            meal_type = infer_meal_type_from_time()

        quantity = float(item.get("quantity", 1))
        unit = item.get("unit", "serving")
        weight_g = _estimate_weight_grams(quantity, unit)

        confidence_str = item.get("confidence", "medium")
        confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
        confidence = confidence_map.get(confidence_str, 0.5)

        meal_item = MealItemCreate(
            food_nutrition_id=food.id if food else None,
            detected_food_name=food_name,
            display_food_name=food.food_name if food else food_name,
            estimated_weight_g=weight_g,
            source=ItemSourceType.nguoi_dung_xac_nhan,
            confidence=confidence,
        )

        meal_log_create = MealLogCreate(
            meal_type=meal_type,
            meal_time=datetime.now(timezone.utc),
            source=MealLogSourceType.chat_extraction,
            items=[meal_item],
        )

        try:
            meal_log = await create_meal_log_with_items(
                db=db,
                payload=meal_log_create,
                user_id=user_id,
            )
            # flush() called inside create_meal_log_with_items — no commit yet
            created_logs.append(meal_log)
            logger.info(f"Created meal log from chat: {food_name}")
        except Exception as e:
            logger.error(f"Failed to create meal log: {e}")

    await db.commit()
    return created_logs


async def process_meal_command(
    db: AsyncSession,
    user_id: UUID,
    food_mention: str,
) -> tuple[MealLog | None, str]:
    """
    Process an explicit meal logging command.
    Called when user says things like "log [food]" or "I just ate [food]".

    Returns (meal_log, confirmation_message).
    """
    # Extract meal details using AI
    extracted = await _extract_meals_from_text(
        user_message=f"I ate {food_mention}",
        ai_response="",
    )

    if not extracted:
        # Fallback: create basic meal log
        meal_item = MealItemCreate(
            detected_food_name=food_mention,
            estimated_weight_g=100,
            source=ItemSourceType.nguoi_dung_xac_nhan,
            confidence=0.5,
        )

        meal_log_create = MealLogCreate(
            meal_type=infer_meal_type_from_time(),
            meal_time=datetime.now(timezone.utc),
            source=MealLogSourceType.chat_command,
            items=[meal_item],
        )

        try:
            meal_log = await create_meal_log_with_items(
                db=db,
                payload=meal_log_create,
                user_id=user_id,
            )
            await db.commit()

            total_cal = meal_log.total_calories
            return meal_log, f"Đã ghi nhận '{food_mention}'. Ước tính: ~{int(total_cal)} kcal. Cần điều chỉnh gì không?"
        except Exception as e:
            logger.error(f"Failed to create meal log: {e}")
            await db.rollback()
            return None, "Xin lỗi, tôi không thể ghi nhận món này lúc này."

    # Use first extracted item
    item = extracted[0]
    food_name = item.get("food_name", food_mention)

    # Find matching food
    food, _ = await _find_matching_food(db, food_name)

    # Calculate nutrition
    meal_type_str = item.get("meal_type")
    if meal_type_str:
        try:
            meal_type = MealTypeEnum(meal_type_str)
        except ValueError:
            meal_type = infer_meal_type_from_time()
    else:
        meal_type = infer_meal_type_from_time()

    quantity = float(item.get("quantity", 1))
    unit = item.get("unit", "serving")
    weight_g = _estimate_weight_grams(quantity, unit)

    confidence_str = item.get("confidence", "medium")
    confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
    confidence = confidence_map.get(confidence_str, 0.5)

    meal_item = MealItemCreate(
        food_nutrition_id=food.id if food else None,
        detected_food_name=food_name,
        display_food_name=food.food_name if food else food_name,
        estimated_weight_g=weight_g,
        source=ItemSourceType.nguoi_dung_xac_nhan,
        confidence=confidence,
    )

    meal_log_create = MealLogCreate(
        meal_type=meal_type,
        meal_time=datetime.now(timezone.utc),
        source=MealLogSourceType.chat_command,
        items=[meal_item],
    )

    try:
        meal_log = await create_meal_log_with_items(
            db=db,
            payload=meal_log_create,
            user_id=user_id,
        )
        await db.commit()

        total_cal = meal_log.total_calories
        calories_str = f"~{int(total_cal)} kcal" if total_cal > 0 else "chưa có dữ liệu dinh dưỡng"

        return meal_log, f"Đã ghi nhận '{food_name}'. Ước tính: {calories_str}. Cần điều chỉnh gì không?"

    except Exception as e:
        logger.error(f"Failed to create meal log: {e}")
        await db.rollback()
        return None, "Xin lỗi, tôi không thể ghi nhận món này lúc này."


def _estimate_weight_grams(quantity: float, unit: str) -> float:
    """Estimate weight in grams from quantity and unit."""
    unit_lower = unit.lower().strip()

    # Common unit mappings
    unit_map = {
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
        "ml": 1.0,
        "milliliter": 1.0,
        "mls": 1.0,
        "kg": 1000.0,
        "kilogram": 1000.0,
        "l": 1000.0,
        "liter": 1000.0,
        "cup": 240.0,
        "cups": 240.0,
        "bowl": 300.0,
        "bowls": 300.0,
        "plate": 400.0,
        "plates": 400.0,
        "piece": 50.0,
        "pieces": 50.0,
        "slice": 30.0,
        "slices": 30.0,
        "serving": 150.0,
        "servings": 150.0,
        "spoon": 15.0,
        "spoons": 15.0,
        "tablespoon": 15.0,
        "tablespoons": 15.0,
        "tbsp": 15.0,
        "teaspoon": 5.0,
        "teaspoons": 5.0,
        "tsp": 5.0,
        "glass": 250.0,
        "glasses": 250.0,
        "can": 330.0,
        "cans": 330.0,
        "bottle": 500.0,
        "bottles": 500.0,
    }

    multiplier = unit_map.get(unit_lower, 150.0)  # Default to 150g per serving
    return quantity * multiplier

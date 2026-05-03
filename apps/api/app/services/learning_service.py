"""
Learning Service — implements the feedback loop for continuous improvement.

Responsibilities:
1. Record food corrections (user edits AI predictions)
2. Infer user preferences from meal history
3. Provide learned corrections to the food mapping pipeline
4. Analyze correction patterns to improve future matches

The feedback loop:
  User corrects food → FoodCorrection stored
    → learning_service learns patterns
    → future match_food_name() uses learned corrections
    → accuracy improves over time
"""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import MealTypeEnum
from app.models.learning import (
    FoodCorrection,
    MealFeedback,
    UserPreferenceLearned,
)
from app.models.meal import MealItem, MealLog
from app.models.food_nutrition import FoodNutrition


# ─── Food Correction Recording ───────────────────────────────────────────────────

async def record_food_correction(
    db: AsyncSession,
    user_id: UUID,
    ai_detected_food_name: str,
    corrected_food_name: str,
    meal_log_id: UUID | None = None,
    meal_item_id: UUID | None = None,
    ai_matched_food_id: UUID | None = None,
    corrected_food_id: UUID | None = None,
    ai_estimated_weight_g: float | None = None,
    corrected_weight_g: float | None = None,
    ai_confidence: float | None = None,
    ai_match_score: float | None = None,
) -> FoodCorrection:
    """
    Record when a user corrects an AI food prediction.
    This is the foundation of the learning feedback loop.
    """
    # Determine correction type
    correction_type = _classify_correction(
        ai_detected_food_name,
        corrected_food_name,
        ai_estimated_weight_g,
        corrected_weight_g,
    )

    correction = FoodCorrection(
        user_id=user_id,
        meal_log_id=meal_log_id,
        meal_item_id=meal_item_id,
        ai_detected_food_name=ai_detected_food_name,
        ai_matched_food_id=ai_matched_food_id,
        ai_estimated_weight_g=ai_estimated_weight_g,
        ai_confidence=ai_confidence,
        ai_match_score=ai_match_score,
        corrected_food_name=corrected_food_name,
        corrected_food_id=corrected_food_id,
        corrected_weight_g=corrected_weight_g,
        correction_type=correction_type,
    )
    db.add(correction)
    await db.flush()
    return correction


def _classify_correction(
    ai_name: str,
    corrected_name: str,
    ai_weight: float | None,
    corrected_weight: float | None,
) -> str:
    """Classify what type of correction was made."""
    name_changed = ai_name.strip().lower() != corrected_name.strip().lower()

    weight_changed = (
        ai_weight is not None
        and corrected_weight is not None
        and abs(ai_weight - corrected_weight) / ai_weight > 0.05  # >5% difference
    )

    if name_changed and weight_changed:
        return "food_replaced"
    elif name_changed:
        return "food_name_changed"
    elif weight_changed:
        return "weight_adjusted"
    else:
        return "food_name_changed"  # fallback


# ─── Learned Correction Lookup ───────────────────────────────────────────────────

async def get_learned_correction(
    db: AsyncSession,
    user_id: UUID,
    ai_detected_food_name: str,
) -> tuple[UUID, float] | None:
    """
    Check if a user has previously corrected this food.
    If yes, return (corrected_food_id, confidence) to boost the correction.

    This makes the system learn from mistakes — if user always changes
    "cơm tấm" to "cơm tấm sườn", next time we suggest the corrected version.
    """
    # Find corrections where user changed the same AI name
    result = await db.execute(
        select(FoodCorrection)
        .where(
            FoodCorrection.user_id == user_id,
            func.lower(func.trim(FoodCorrection.ai_detected_food_name))
            == ai_detected_food_name.strip().lower(),
        )
        .order_by(FoodCorrection.created_at.desc())
        .limit(5)
    )
    corrections = result.scalars().all()

    if not corrections:
        return None

    # Count occurrences of each corrected food
    from collections import Counter
    corrected_ids = [
        (c.corrected_food_id, c.corrected_food_name)
        for c in corrections
        if c.corrected_food_id is not None
    ]
    if not corrected_ids:
        return None

    # Most common corrected food
    id_counts = Counter(str(cid) for cid, _ in corrected_ids)
    most_common_id = UUID(list(id_counts.most_common(1))[0][0])

    # Confidence based on consistency (if user consistently corrects to same food)
    most_common_count = id_counts.most_common(1)[0][1]
    consistency = min(1.0, most_common_count / 3.0)  # 3 corrections = full confidence

    return most_common_id, consistency


# ─── User Preference Inference ───────────────────────────────────────────────────

async def infer_user_preferences(
    db: AsyncSession,
    user_id: UUID,
    min_meals: int = 10,
) -> dict:
    """
    Analyze meal history to infer user preferences.
    Called periodically or on demand to refresh learned preferences.

    Requires at least min_meals to infer patterns reliably.
    """
    # Get user's meal logs with items
    result = await db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items).selectinload(MealItem.food_nutrition_id))
        .where(MealLog.user_id == user_id)
        .order_by(MealLog.meal_time.desc())
        .limit(100)
    )
    meals = result.scalars().all()

    if len(meals) < min_meals:
        return {"sufficient_data": False, "meals_analyzed": len(meals)}

    # ── Typical meal times ──────────────────────────────────────────────────
    from collections import defaultdict
    meal_time_by_type: dict[str, list[time]] = defaultdict(list)

    for meal in meals:
        meal_hour = meal.meal_time.hour
        meal_minute = meal.meal_time.minute
        meal_time_obj = time(meal_hour, meal_minute)
        meal_time_by_type[meal.meal_type.value].append(meal_time_obj)

    typical_times = {}
    for meal_type, times in meal_time_by_type.items():
        if times:
            # Average time (simple median)
            sorted_times = sorted(times)
            mid = len(sorted_times) // 2
            median_time = sorted_times[mid]
            typical_times[meal_type] = median_time.strftime("%H:%M")

    # ── Average calories per meal ───────────────────────────────────────────
    total_calories = sum(float(m.total_calories or 0) for m in meals)
    avg_cal = total_calories / len(meals)

    # ── Frequently vs rarely logged foods ────────────────────────────────────
    food_counts: dict[str, int] = {}
    for meal in meals:
        for item in meal.items:
            name = item.detected_food_name or item.display_food_name
            if name:
                food_counts[name.lower()] = food_counts.get(name.lower(), 0) + 1

    if food_counts:
        sorted_foods = sorted(food_counts.items(), key=lambda x: x[1], reverse=True)
        frequent = [name for name, count in sorted_foods[:20] if count >= 2]
        avoided = [name for name, count in sorted_foods if count == 1]
    else:
        frequent, avoided = [], []

    # ── Confidence in preferences ────────────────────────────────────────────
    confidence = min(1.0, len(meals) / 30.0)  # 30 meals = full confidence

    return {
        "sufficient_data": True,
        "meals_analyzed": len(meals),
        "typical_meal_times": typical_times,
        "avg_calories_per_meal": round(avg_cal, 1),
        "frequently_logged_foods": frequent,
        "avoided_foods": avoided,
        "preference_confidence": round(confidence, 2),
    }


async def upsert_user_preferences(
    db: AsyncSession,
    user_id: UUID,
    inferred: dict,
) -> UserPreferenceLearned:
    """Update or create learned preferences for a user."""
    result = await db.execute(
        select(UserPreferenceLearned).where(UserPreferenceLearned.user_id == user_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        prefs = existing
    else:
        prefs = UserPreferenceLearned(user_id=user_id)

    prefs.typical_meal_times = inferred.get("typical_meal_times")
    prefs.avg_meals_per_day = None  # computed separately
    prefs.avg_calories_per_meal = inferred.get("avg_calories_per_meal")
    prefs.frequently_logged_foods = inferred.get("frequently_logged_foods")
    prefs.avoided_foods = inferred.get("avoided_foods")
    prefs.preference_confidence = inferred.get("preference_confidence")
    prefs.data_points_analyzed = inferred.get("meals_analyzed", 0)

    db.add(prefs)
    await db.flush()
    return prefs


# ─── Meal Feedback ──────────────────────────────────────────────────────────────

async def record_meal_feedback(
    db: AsyncSession,
    user_id: UUID,
    meal_log_id: UUID,
    accuracy_rating: int | None = None,
    nutrition_accurate: bool | None = None,
    comment: str | None = None,
) -> MealFeedback:
    """Record user feedback on a meal log's accuracy."""
    feedback = MealFeedback(
        user_id=user_id,
        meal_log_id=meal_log_id,
        accuracy_rating=accuracy_rating,
        nutrition_accurate=nutrition_accurate,
        comment=comment,
    )
    db.add(feedback)
    await db.flush()
    return feedback


async def get_user_feedback_stats(
    db: AsyncSession,
    user_id: UUID,
    days: int = 30,
) -> dict:
    """Get aggregate feedback statistics for a user."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(func.count(MealFeedback.id), func.avg(MealFeedback.accuracy_rating))
        .where(
            MealFeedback.user_id == user_id,
            MealFeedback.created_at >= cutoff,
        )
    )
    row = result.one()
    count, avg_rating = row

    return {
        "feedback_count": count or 0,
        "avg_accuracy_rating": round(float(avg_rating), 1) if avg_rating else None,
        "period_days": days,
    }

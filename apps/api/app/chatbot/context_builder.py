from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.chatbot.context_policy import DEFAULT_CHATBOT_CONTEXT_POLICY
from app.core.constants import CONDITION_RULES
from app.core.sanitize import sanitize_for_prompt
from app.models.chat import ChatMessage
from app.models.daily_recommendation import DailyRecommendation
from app.models.meal import MealLog
from app.models.nutrition_goal import NutritionGoal
from app.models.user_profile import UserProfile
from app.services.conversation_insights_service import get_active_insights
from app.services.dashboard_service import get_daily_dashboard, get_weekly_dashboard


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, UUID)):
        return str(value)
    return value


def serialize_dict(obj):
    if isinstance(obj, dict):
        return {k: serialize_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_dict(v) for v in obj]
    return serialize_value(obj)


def get_dietary_rules(health_conditions: list[dict] | None) -> list[str]:
    """
    Return list of dietary rule flags based on active health conditions.
    """
    if not health_conditions:
        return []

    active = [
        c.get("condition") for c in health_conditions
        if isinstance(c, dict) and c.get("severity") != "resolved"
    ]

    flags: set[str] = set()
    for cond_id in active:
        if cond_id in CONDITION_RULES:
            flags.update(CONDITION_RULES[cond_id])
    return sorted(flags)


def build_health_context(profile: UserProfile | None) -> str:
    """
    Returns a structured health context string injected into AI system prompt.
    """
    if not profile:
        return ""

    sections: list[str] = []

    # Usage Goal
    usage_goal_val = getattr(profile, "usage_goal", None)
    if usage_goal_val:
        goal_str = usage_goal_val.value if hasattr(usage_goal_val, "value") else str(usage_goal_val)
        sections.append(f"User's primary goal: {goal_str}")

    # Health Conditions
    conditions = getattr(profile, "health_conditions", None)
    if conditions:
        active = [c for c in conditions if isinstance(c, dict) and c.get("severity") != "resolved"]
        if active:
            names = [c.get("condition", "") for c in active]
            sections.append(
                f"MEDICAL CONDITIONS (adjust all advice accordingly): {', '.join(names)}. "
                f"Always recommend consulting a doctor for medical-related nutrition changes."
            )

            # Dietary constraints
            rules = get_dietary_rules(conditions)
            if rules:
                constraint_lines = [
                    f"- {r.replace('_', ' ').title()}" for r in rules
                ]
                sections.append(
                    "DIETARY CONSTRAINTS FOR THIS USER (MUST FOLLOW):\n"
                    + "\n".join(constraint_lines)
                )

    # Allergies
    allergies = getattr(profile, "allergies", None)
    if allergies:
        allergen_list = [a.get("allergen") if isinstance(a, dict) else str(a) for a in allergies]
        sections.append(f"ALLERGIES (never suggest these foods): {', '.join(allergen_list)}")

    # Dietary Restrictions
    dietary_res = getattr(profile, "dietary_restrictions", None)
    if dietary_res:
        sections.append(f"Dietary restrictions: {', '.join(dietary_res)}")

    # Medications
    medications = getattr(profile, "medications", None)
    if medications:
        med_names = [m.get("name") if isinstance(m, dict) else str(m) for m in medications]
        sections.append(
            f"Current medications: {', '.join(med_names)}. "
            f"Be aware of potential food-drug interactions."
        )

    # Taste Preferences
    taste_prefs = getattr(profile, "taste_preferences", None)
    if taste_prefs and isinstance(taste_prefs, dict):
        dominant = [k for k, v in taste_prefs.items() if isinstance(v, (int, float)) and v >= 4]
        avoided = [k for k, v in taste_prefs.items() if isinstance(v, (int, float)) and v <= 1]
        if dominant:
            sections.append(f"Prefers {', '.join(dominant)} flavors (score ≥ 4/5)")
        if avoided:
            sections.append(f"Dislikes {', '.join(avoided)} flavors (score ≤ 1/5)")

    # Disliked Foods
    disliked = getattr(profile, "disliked_foods", None)
    if disliked and isinstance(disliked, list):
        items = [d if isinstance(d, str) else d.get("name", "") for d in disliked]
        sections.append(f"Dislikes these foods: {', '.join(items)}")

    # Cuisine Preferences
    cuisines = getattr(profile, "cuisine_preferences", None)
    if cuisines and isinstance(cuisines, list):
        sections.append(f"Preferred cuisines: {', '.join(cuisines)}")

    # Sleep
    sleep_hours = getattr(profile, "sleep_duration_hours", None)
    sleep_quality = getattr(profile, "sleep_quality", None)
    if sleep_hours:
        sq = sleep_quality.value if hasattr(sleep_quality, "value") else (sleep_quality or "unknown")
        sections.append(
            f"Sleeps ~{sleep_hours}h/night (quality: {sq})"
        )

    # Stress Level
    stress = getattr(profile, "stress_level", None)
    if stress and stress >= 7:
        sections.append(
            "High stress level reported — consider magnesium, B-vitamins, adaptogens in suggestions"
        )

    # Disclaimer when health conditions present
    if conditions:
        sections.append(
            "IMPORTANT DISCLAIMER: Đây là gợi ý dinh dưỡng chung. "
            "Hãy tham khảo bác sĩ hoặc chuyên gia dinh dưỡng trước khi thay đổi chế độ ăn."
        )

    return "\n".join(sections)


async def get_active_goal(db: AsyncSession, user_id: UUID):
    result = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == user_id,
            NutritionGoal.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def build_chatbot_context(
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
    user_question: str,
    target_date: date | None = None,
    timezone_str: str = "Asia/Ho_Chi_Minh",
    policy=DEFAULT_CHATBOT_CONTEXT_POLICY,
) -> dict:
    """
    Gom context cho chatbot bằng Async.
    """
    if target_date is None:
        target_date = date.today()

    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one_or_none()

    active_goal = await get_active_goal(db, user_id)

    today_dashboard = await get_daily_dashboard(
        db=db,
        user_id=user_id,
        target_date=target_date,
        timezone_str=timezone_str,
    )

    weekly_dashboard = None
    if policy.include_weekly_dashboard:
        weekly_dashboard = await get_weekly_dashboard(
            db=db,
            user_id=user_id,
            end_date=target_date,
            timezone_str=timezone_str,
        )

    result_meals = await db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == user_id)
        .order_by(MealLog.meal_time.desc())
        .limit(policy.max_recent_meals)
    )
    recent_meals = result_meals.scalars().all()

    latest_recommendation = None
    if policy.include_daily_recommendation:
        result_rec = await db.execute(
            select(DailyRecommendation)
            .where(DailyRecommendation.user_id == user_id)
            .order_by(DailyRecommendation.recommendation_date.desc())
            .limit(1)
        )
        latest_recommendation = result_rec.scalar_one_or_none()

    result_msgs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(policy.max_chat_history_messages)
    )
    recent_chat_messages = result_msgs.scalars().all()
    recent_chat_messages = list(reversed(recent_chat_messages))

    context = {
        "user_question": user_question,
        "profile": None,
        "active_goal": None,
        "today_dashboard": today_dashboard.model_dump() if hasattr(today_dashboard, 'model_dump') else today_dashboard,
        "weekly_dashboard": weekly_dashboard.model_dump() if weekly_dashboard and hasattr(weekly_dashboard, 'model_dump') else weekly_dashboard,
        "recent_meals": [
            {
                "meal_type": meal.meal_type.value if hasattr(meal.meal_type, "value") else str(meal.meal_type),
                "meal_time": meal.meal_time,
                "total_calories": meal.total_calories,
                "total_protein_g": meal.total_protein_g,
                "total_carb_g": meal.total_carb_g,
                "total_fat_g": meal.total_fat_g,
                "note": meal.note,
            }
            for meal in recent_meals
        ],
        "latest_daily_recommendation": None,
        "recent_chat_history": [
            {
                "role": msg.role,
                # FIX-7 (V-5, V-2): sanitize every historical message content
                # before it enters the prompt. Cumulative multi-turn injection
                # and stored-persistent injection via chat history are both blocked.
                "content": sanitize_for_prompt(msg.content, max_length=500),
                "created_at": msg.created_at,
            }
            for msg in recent_chat_messages
        ],
    }

    if profile:
        # FIX-7 (V-2): Sanitize ALL free-text fields before they reach the AI prompt.
        # Stored-persistent injection via profile fields is blocked here.
        # Guard: skip sanitization for non-string values (Enum, int, float, None).
        def _safe(text, limit=500):
            if isinstance(text, str):
                return sanitize_for_prompt(text, max_length=limit)
            return text

        profile_dict = {
            "gender": profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender),
            "date_of_birth": profile.date_of_birth,
            "height_cm": profile.height_cm,
            "current_weight_kg": profile.current_weight_kg,
            "current_body_fat_percent": profile.current_body_fat_percent,
            "activity_level": profile.activity_level.value if hasattr(profile.activity_level, "value") else str(profile.activity_level),
            "diet_type": profile.diet_type.value if hasattr(profile.diet_type, "value") else str(profile.diet_type),
            # JSONB / list fields — sanitize nested free-text values
            "allergies": [
                {**a, "allergen": _safe(a.get("allergen", ""), 200)}
                if isinstance(a, dict) else _safe(str(a), 200)
                for a in (profile.allergies or [])
            ],
            "allergies_text": _safe(profile.allergies_text, 500),
            "disliked_foods": [
                {**d, "name": _safe(d.get("name", ""), 200)}
                if isinstance(d, dict) else _safe(str(d), 200)
                for d in (profile.disliked_foods or [])
            ],
            "disliked_foods_text": _safe(profile.disliked_foods_text, 500),
            "preferred_foods": [
                {**p, "name": _safe(p.get("name", ""), 200)}
                if isinstance(p, dict) else _safe(str(p), 200)
                for p in (profile.preferred_foods or [])
            ],
            "preferred_foods_text": _safe(profile.preferred_foods_text, 500),
            # Long free-text notes — the primary stored-injection vector
            "health_note": _safe(profile.health_note, 500),
            # Extended fields
            "usage_goal": profile.usage_goal.value if profile.usage_goal and hasattr(profile.usage_goal, "value") else profile.usage_goal,
            "usage_goal_note": _safe(profile.usage_goal_note, 500),
            # Nested JSONB — sanitize condition notes
            "health_conditions": [
                {**c, "note": _safe(c.get("note", ""), 200)}
                if isinstance(c, dict) else c
                for c in (profile.health_conditions or [])
            ],
            "allergies_jsonb": profile.allergies,
            # Medications — sanitize drug names
            "medications": [
                {**m, "name": _safe(m.get("name", ""), 200)}
                if isinstance(m, dict) else _safe(str(m), 200)
                for m in (profile.medications or [])
            ],
            "dietary_restrictions": profile.dietary_restrictions,
            "sleep_duration_hours": profile.sleep_duration_hours,
            "sleep_quality": profile.sleep_quality.value if profile.sleep_quality and hasattr(profile.sleep_quality, "value") else profile.sleep_quality,
            "sleep_schedule": _safe(profile.sleep_schedule, 100),
            "stress_level": profile.stress_level,
            "meal_frequency": profile.meal_frequency.value if profile.meal_frequency and hasattr(profile.meal_frequency, "value") else profile.meal_frequency,
            "cooking_preference": profile.cooking_preference.value if profile.cooking_preference and hasattr(profile.cooking_preference, "value") else profile.cooking_preference,
            "wake_up_time": _safe(profile.wake_up_time, 50),
            "sleep_time": _safe(profile.sleep_time, 50),
            "work_schedule": _safe(profile.work_schedule, 100),
            "taste_preferences": profile.taste_preferences,
            "cuisine_preferences": profile.cuisine_preferences,
            "favorite_foods": profile.favorite_foods,
            "eating_speed": profile.eating_speed,
            "chew_difficulty": profile.chew_difficulty,
        }
        # Inject health context as a structured string for the AI
        profile_dict["_health_context"] = build_health_context(profile)
        context["profile"] = profile_dict
        # Keep ORM object for use by callers (e.g., card_triggers)
        context["_profile_object"] = profile

    if active_goal:
        context["active_goal"] = {
            "goal_type": active_goal.goal_type.value if hasattr(active_goal.goal_type, "value") else str(active_goal.goal_type),
            "daily_calorie_target": active_goal.daily_calorie_target,
            "protein_target_g": active_goal.protein_target_g,
            "carb_target_g": active_goal.carb_target_g,
            "fat_target_g": active_goal.fat_target_g,
            "bmi": getattr(active_goal, "bmi", None),
            "bmr_kcal": getattr(active_goal, "bmr_kcal", None),
            "tdee_kcal": getattr(active_goal, "tdee_kcal", None),
        }

    if latest_recommendation:
        context["latest_daily_recommendation"] = {
            "recommendation_date": latest_recommendation.recommendation_date,
            "calories_target": latest_recommendation.calories_target,
            "protein_target_g": latest_recommendation.protein_target_g,
            "carb_target_g": latest_recommendation.carb_target_g,
            "fat_target_g": latest_recommendation.fat_target_g,
            "meal_suggestion": latest_recommendation.meal_suggestion,
            "workout_suggestion": latest_recommendation.workout_suggestion,
            "lifestyle_suggestion": latest_recommendation.lifestyle_suggestion,
            "ai_summary": latest_recommendation.ai_summary,
        }

    # ── Conversation Insights ───────────────────────────────────────────────────
    active_insights = await get_active_insights(db=db, user_id=user_id)
    # FIX-7 (V-2): conversation_insights are AI-extracted from user messages,
    # so sanitize the free-text fields before they re-enter the prompt.
    if active_insights:
        context["conversation_insights"] = [
            {
                "type": insight.insight_type,
                "key": insight.key,
                "summary": sanitize_for_prompt(insight.summary, max_length=300),
                "value": sanitize_for_prompt(str(insight.value), max_length=200),
            }
            for insight in active_insights
        ]

    return serialize_dict(context)

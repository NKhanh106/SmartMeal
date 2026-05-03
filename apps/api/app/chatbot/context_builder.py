from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.chatbot.context_policy import DEFAULT_CHATBOT_CONTEXT_POLICY
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
                "content": msg.content,
                "created_at": msg.created_at,
            }
            for msg in recent_chat_messages
        ],
    }

    if profile:
        context["profile"] = {
            "gender": profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender),
            "date_of_birth": profile.date_of_birth,
            "height_cm": profile.height_cm,
            "current_weight_kg": profile.current_weight_kg,
            "current_body_fat_percent": profile.current_body_fat_percent,
            "activity_level": profile.activity_level.value if hasattr(profile.activity_level, "value") else str(profile.activity_level),
            "diet_type": profile.diet_type.value if hasattr(profile.diet_type, "value") else str(profile.diet_type),
            "allergies": profile.allergies,
            "disliked_foods": profile.disliked_foods,
            "preferred_foods": profile.preferred_foods,
            "health_note": profile.health_note,
        }

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
    # Thông tin cốt lõi trích xuất từ các cuộc trò chuyện trước đó
    active_insights = await get_active_insights(db=db, user_id=user_id)
    if active_insights:
        context["conversation_insights"] = [
            {
                "type": insight.insight_type,
                "key": insight.key,
                "summary": insight.summary,
                "value": insight.value,
            }
            for insight in active_insights
        ]

    return serialize_dict(context)

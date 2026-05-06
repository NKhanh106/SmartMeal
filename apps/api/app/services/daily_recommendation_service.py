import time
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.ai.factory import get_ai_provider
from app.ai.prompts.daily_planner_prompt import (
    DAILY_PLANNER_PROMPT_VERSION,
    DAILY_PLANNER_SYSTEM_PROMPT,
    build_daily_planner_user_prompt,
)
from app.ai.circuit_breaker import gemini_circuit, groq_circuit
from app.core.cache import cache_get, cache_set, cache_delete, make_cache_key
from app.core.config import settings
from app.core.utils import (
    get_active_goal,
    serialize_dict,
)
from app.models.daily_recommendation import DailyRecommendation
from app.models.nutrition_goal import NutritionGoal
from app.models.user_profile import UserProfile
from app.schemas.daily_recommendation import DailyPlannerAIResult
from app.services.ai_log_service import create_ai_log
from app.services.dashboard_service import get_daily_dashboard, get_weekly_dashboard
from app.services.planner_constraint_engine import (
    build_constraints_from_profile_and_goal,
    build_constraint_guidance,
    validate_recommendation,
)


async def get_active_goal(db: AsyncSession, user_id: UUID):
    result = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == user_id,
            NutritionGoal.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def build_daily_planner_context(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
) -> dict:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    active_goal = await get_active_goal(db=db, user_id=user_id)

    if not active_goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active nutrition goal not found.",
        )

    today = target_date - timedelta(days=1)

    today_dashboard = await get_daily_dashboard(
        db=db,
        user_id=user_id,
        target_date=today,
        timezone_str="Asia/Ho_Chi_Minh",
    )

    weekly_dashboard = await get_weekly_dashboard(
        db=db,
        user_id=user_id,
        end_date=today,
        timezone_str="Asia/Ho_Chi_Minh",
    )

    context = {
        "target_recommendation_date": target_date,
        "profile": {
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
        },
        "active_goal": {
            "goal_type": active_goal.goal_type.value if hasattr(active_goal.goal_type, "value") else str(active_goal.goal_type),
            "daily_calorie_target": active_goal.daily_calorie_target,
            "protein_target_g": active_goal.protein_target_g,
            "carb_target_g": active_goal.carb_target_g,
            "fat_target_g": active_goal.fat_target_g,
            "bmi": getattr(active_goal, "bmi", None),
            "bmr_kcal": getattr(active_goal, "bmr_kcal", None),
            "tdee_kcal": getattr(active_goal, "tdee_kcal", None),
        },
        "today_dashboard": today_dashboard.model_dump() if hasattr(today_dashboard, 'model_dump') else today_dashboard,
        "weekly_dashboard": weekly_dashboard.model_dump() if hasattr(weekly_dashboard, 'model_dump') else weekly_dashboard,
    }

    return serialize_dict(context)


async def upsert_daily_recommendation(
    db: AsyncSession,
    user_id: UUID,
    ai_result: DailyPlannerAIResult,
    raw_response: dict,
    ai_analysis_log_id: UUID | None = None,
) -> DailyRecommendation:
    result = await db.execute(
        select(DailyRecommendation).where(
            DailyRecommendation.user_id == user_id,
            DailyRecommendation.recommendation_date == ai_result.recommendation_date,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        rec = existing
    else:
        rec = DailyRecommendation(
            user_id=user_id,
            recommendation_date=ai_result.recommendation_date,
        )

    rec.calories_target = ai_result.calories_target
    rec.protein_target_g = ai_result.protein_target_g
    rec.carb_target_g = ai_result.carb_target_g
    rec.fat_target_g = ai_result.fat_target_g

    rec.meal_suggestion = ai_result.meal_suggestion
    rec.workout_suggestion = ai_result.workout_suggestion
    rec.lifestyle_suggestion = ai_result.lifestyle_suggestion

    rec.ai_summary = ai_result.summary
    rec.ai_raw_response = raw_response
    rec.ai_analysis_log_id = ai_analysis_log_id
    rec.status = "generated"

    db.add(rec)
    await db.flush()

    return rec


async def invalidate_user_plan_cache(user_id: UUID, target_date: date) -> None:
    """Invalidate cached daily plan when user logs a new meal."""
    cache_key = make_cache_key("daily_plan", str(user_id), target_date.isoformat())
    await cache_delete(cache_key)


async def generate_daily_recommendation(
    db: AsyncSession,
    user_id: UUID,
    target_date: date | None = None,
) -> DailyRecommendation:
    import logging

    logger = logging.getLogger(__name__)

    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    # ── Check Redis cache ──────────────────────────────────────────────────────
    cache_key = make_cache_key("daily_plan", str(user_id), target_date.isoformat())
    cached_data = await cache_get(cache_key)
    if cached_data:
        # Return cached recommendation from DB without calling AI
        logger.info("Daily plan cache HIT for user %s, date %s", user_id, target_date)
        rec = await get_recommendation_by_date(db, user_id, target_date)
        # Mark as cached in memory (not persisted to DB)
        return rec

    logger.info("Daily plan cache MISS for user %s, date %s — generating new plan", user_id, target_date)
    context = await build_daily_planner_context(
        db=db,
        user_id=user_id,
        target_date=target_date,
    )

    user_prompt = build_daily_planner_user_prompt(context)

    provider = get_ai_provider(settings.AI_PLANNER_PROVIDER)

    start_time = time.perf_counter()

    # ── Call AI with circuit breaker ────────────────────────────────────────
    primary_circuit = gemini_circuit if settings.AI_PLANNER_PROVIDER == "gemini" else groq_circuit
    fallback_circuit = groq_circuit if settings.AI_PLANNER_PROVIDER == "gemini" else gemini_circuit

    ai_result = None
    raw_response = None
    last_error: Exception | None = None

    for circuit, _provider_name in [(primary_circuit, settings.AI_PLANNER_PROVIDER), (fallback_circuit, None)]:
        if not circuit.is_available() and _provider_name is not None:
            continue
        try:
            if _provider_name is None:
                # Use fallback
                fallback_provider_name = "gemini" if settings.AI_PLANNER_PROVIDER == "groq" else "groq"
                logger.info("Daily planner: trying fallback provider %s", fallback_provider_name)
                provider = get_ai_provider(fallback_provider_name)

            ai_result, raw_response = await run_in_threadpool(
                provider.generate_json,
                system_prompt=DAILY_PLANNER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_schema=DailyPlannerAIResult,
                temperature=0.3,
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Daily planner AI call failed: %s", exc)
            continue

    if ai_result is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hệ thống AI hiện đang bận, không thể lên kế hoạch. Vui lòng thử lại sau.",
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    model_name = settings.GEMINI_MODEL if settings.AI_PLANNER_PROVIDER == "gemini" else settings.GROQ_TEXT_MODEL

    ai_log = await create_ai_log(
        db=db,
        user_id=user_id,
        task_type="daily_recommendation",
        provider_name=settings.AI_PLANNER_PROVIDER,
        model_name=model_name,
        prompt_version=DAILY_PLANNER_PROMPT_VERSION,
        input_summary=f"provider={settings.AI_PLANNER_PROVIDER}, target_date={target_date}",
        raw_response=raw_response,
        status="success",
        latency_ms=latency_ms,
    )

    recommendation = await upsert_daily_recommendation(
        db=db,
        user_id=user_id,
        ai_result=ai_result,
        raw_response=raw_response,
        ai_analysis_log_id=ai_log.id,
    )
    await db.commit()
    await db.refresh(recommendation)

    # Cache for 12 hours
    await cache_set(cache_key, {"id": str(recommendation.id)}, settings.DAILY_PLAN_CACHE_TTL)

    return recommendation


async def get_recommendation_by_date(
    db: AsyncSession,
    user_id: UUID,
    recommendation_date: date,
) -> DailyRecommendation:
    result = await db.execute(
        select(DailyRecommendation).where(
            DailyRecommendation.user_id == user_id,
            DailyRecommendation.recommendation_date == recommendation_date,
        )
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily recommendation not found.",
        )

    return rec

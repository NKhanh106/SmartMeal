import logging
import time
from datetime import date, timedelta
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
from app.core.cache import cache_get, cache_set, get_redis, make_cache_key
from app.core.config import settings
from app.core.utils import (
    get_active_goal,
    serialize_dict,
)
from app.core.background import create_tracked_task
from app.models.daily_recommendation import DailyRecommendation
from app.models.user_profile import UserProfile
from app.schemas.daily_recommendation import DailyPlannerAIResult
from app.services.ai_log_service import create_ai_log
from app.services.dashboard_service import get_daily_dashboard, get_weekly_dashboard

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


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
    # Store only a debug summary of the AI response (max 500 chars).
    # Full JSON blobs cause DB bloat (KB per record).
    rec.ai_raw_response = str(raw_response)[:500] if raw_response else None  # type: ignore — TEXT column
    rec.ai_analysis_log_id = ai_analysis_log_id
    rec.status = "generated"

    db.add(rec)
    await db.flush()

    return rec


async def invalidate_user_plan_cache(user_id: UUID) -> None:
    """
    Invalidate ALL cached daily plans for a user across all dates.

    Uses Redis SCAN to find all keys matching the user's plan cache prefix,
    then deletes them. This handles:
    - Today and tomorrow (active viewing window)
    - Any past plans still in cache (TTL = 12h, so max 12 stale entries)

    Best-effort: Redis failures are logged and do not propagate.
    """
    try:
        redis = await get_redis()
        user_prefix = "smartmeal:daily_plan:"
        deleted = 0
        async for key in redis.scan_iter(match=f"{user_prefix}*"):
            if str(user_id) in key:
                await redis.delete(key)
                deleted += 1
        if deleted:
            logger.info("Invalidated %d daily plan cache entries for user %s", deleted, user_id)
    except Exception as e:
        logger.warning("Failed to invalidate plan cache for user %s (best-effort): %s", user_id, e)


async def _regenerate_daily_plan(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
) -> dict:
    """
    Core regeneration logic: build context, call AI, persist to DB.
    Called by generate_daily_recommendation under lock.
    Returns the cache value dict (not the ORM object).
    """
    import logging
    logger = logging.getLogger(__name__)

    context = await build_daily_planner_context(
        db=db,
        user_id=user_id,
        target_date=target_date,
    )

    user_prompt = build_daily_planner_user_prompt(context)
    provider = get_ai_provider(settings.AI_PLANNER_PROVIDER)
    start_time = time.perf_counter()

    primary_circuit = gemini_circuit if settings.AI_PLANNER_PROVIDER == "gemini" else groq_circuit
    fallback_circuit = groq_circuit if settings.AI_PLANNER_PROVIDER == "gemini" else gemini_circuit

    ai_result = None
    raw_response = None
    last_error: Exception | None = None

    for circuit, _provider_name in [
        (primary_circuit, settings.AI_PLANNER_PROVIDER),
        (fallback_circuit, None),
    ]:
        if not circuit.is_available() and _provider_name is not None:
            continue
        try:
            if _provider_name is None:
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

    return {"id": str(recommendation.id)}


async def _background_refresh_plan(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    cache_key: str,
) -> None:
    """
    Background refresh: regenerate plan and update cache.
    Called by the early-expiry trigger via create_tracked_task.
    Creates its own DB session so the original request session can close.
    """
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as bg_db:
            # Check cache again — another process may have refreshed it already
            cached = await cache_get(cache_key)
            if cached is not None:
                return  # No need to refresh

            result = await _regenerate_daily_plan(bg_db, user_id, target_date)
            await cache_set(cache_key, result, settings.DAILY_PLAN_CACHE_TTL)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Background plan refresh failed for user %s: %s", user_id, e
        )


async def generate_daily_recommendation(
    db: AsyncSession,
    user_id: UUID,
    target_date: date | None = None,
) -> DailyRecommendation:
    """
    Get or generate daily recommendation with cache stampede protection.

    Uses distributed lock (cache_lock) to ensure only one process regenerates
    a missing cache entry, and probabilistic early expiry to spread regeneration
    over time rather than concentrating it at TTL expiry.
    """
    import logging
    logger = logging.getLogger(__name__)

    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    cache_key = make_cache_key("daily_plan", str(user_id), target_date.isoformat())

    # ── Cache HIT: check early expiry trigger ─────────────────────────────────
    cached_data = await cache_get(cache_key)
    if cached_data:
        logger.info("Daily plan cache HIT for user %s, date %s", user_id, target_date)
        # Trigger background refresh if TTL is below threshold (probabilistic early expiry)
        await _trigger_early_expiry_refresh(
            db=db, user_id=user_id, target_date=target_date,
            cache_key=cache_key,
        )
        return await get_recommendation_by_date(db, user_id, target_date)

    # ── Cache MISS: distributed lock + regeneration ──────────────────────────
    logger.info(
        "Daily plan cache MISS for user %s, date %s — acquiring lock",
        user_id, target_date,
    )

    async def _regen() -> dict:
        """Regenerate plan and cache the result."""
        result = await _regenerate_daily_plan(db, user_id, target_date)
        await cache_set(cache_key, result, settings.DAILY_PLAN_CACHE_TTL)
        return result

    from app.core.cache_stampede import get_or_regenerate_with_lock
    from app.core.cache_lock import CacheLockError

    try:
        await get_or_regenerate_with_lock(
            cache_key=cache_key,
            regenerate_fn=_regen,
            lock_key_prefix="daily_plan_regen",
            lock_ttl=60,
            lock_timeout=5.0,
        )
    except CacheLockError:
        logger.warning(
            "Cache lock timeout for daily_plan user %s date %s — regenerating without lock",
            user_id, target_date,
        )
        await _regen()

    return await get_recommendation_by_date(db, user_id, target_date)


async def _trigger_early_expiry_refresh(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    cache_key: str,
) -> None:
    """
    Probabilistic early expiry: trigger background refresh when TTL < 10% of original.
    This spreads regeneration over time instead of clustering at expiry.
    """
    redis = await get_redis()
    try:
        ttl_remaining = await redis.ttl(cache_key)
        if ttl_remaining < 0:
            return
        threshold = int(settings.DAILY_PLAN_CACHE_TTL * 0.1)
        if ttl_remaining < threshold:
            logger.debug(
                "Early expiry triggered for '%s' (TTL remaining: %ds < %ds threshold)",
                cache_key, ttl_remaining, threshold,
            )
            create_tracked_task(
                _background_refresh_plan(db, user_id, target_date, cache_key),
                task_name=f"plan_refresh:{user_id}:{target_date}",
            )
    except Exception:
        pass  # Non-critical — best-effort only


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

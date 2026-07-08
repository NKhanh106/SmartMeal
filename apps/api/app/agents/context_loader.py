"""
Rich context loader — single source of truth for all data agents need.

Loads ALL user data per request using a SINGLE eager-loaded SELECT from the
User model with selectinload(), eliminating the N+1 sequential query problem.

Returns a FullUserContext dataclass passed to all agents.
Called ONCE per request by the Orchestrator.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import CONDITION_RULES


# ─── Snapshot Dataclasses ────────────────────────────────────────────────────


@dataclass
class NutritionSnapshot:
    """Current nutrition goal vs actual intake."""
    kcal_target: float | None = None
    protein_target_g: float | None = None
    carb_target_g: float | None = None
    fat_target_g: float | None = None
    hydration_target_ml: int | None = None
    goal_type: str | None = None

    avg_kcal_7d: float | None = None
    avg_protein_7d: float | None = None
    avg_carb_7d: float | None = None
    avg_fat_7d: float | None = None

    today_kcal: float = 0
    today_protein_g: float = 0
    today_carb_g: float = 0
    today_fat_g: float = 0
    today_meals: list[dict] = field(default_factory=list)

    recent_daily_totals: list[dict] = field(default_factory=list)

    @property
    def kcal_gap_today(self) -> float | None:
        if self.kcal_target and self.today_kcal is not None:
            return self.kcal_target - self.today_kcal
        return None

    @property
    def kcal_adherence_7d(self) -> str:
        if not self.avg_kcal_7d or not self.kcal_target:
            return "unknown"
        ratio = self.avg_kcal_7d / self.kcal_target
        if ratio < 0.8:   return "significantly_under"
        if ratio < 0.95:  return "slightly_under"
        if ratio > 1.2:   return "significantly_over"
        if ratio > 1.05:  return "slightly_over"
        return "on_track"


@dataclass
class BodySnapshotData:
    """Current physical state from memory + progress logs."""
    weight_kg: float | None = None
    energy_level: str | None = None
    sleep_last_night_hours: float | None = None
    digestion_status: str | None = None
    sore_areas: list[str] = field(default_factory=list)
    injury_areas: list[str] = field(default_factory=list)
    hydration_status: str | None = None

    weight_trend: str | None = None
    weight_change_kg_30d: float | None = None

    active_symptoms: list[dict] = field(default_factory=list)


@dataclass
class FitnessSnapshotData:
    """Current fitness state."""
    fitness_level: str = "intermediate"
    last_workout_date: str | None = None
    workout_frequency_7d: int = 0
    preferred_types: list[str] = field(default_factory=list)
    current_restrictions: list[dict] = field(default_factory=list)
    active_plan_name: str | None = None
    next_planned_workout: str | None = None


# ─── Full Context ─────────────────────────────────────────────────────────────


@dataclass
class FullUserContext:
    """
    Complete user context loaded once per request.
    Passed to ALL agents — each agent picks what it needs.
    """
    user_id: int

    # ── Profile: Identity ──────────────────────────────────────────────
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: str | None = None

    # ── Profile: Goals ───────────────────────────────────────────────
    usage_goal: str | None = None
    usage_goal_note: str | None = None

    # ── Profile: Health ─────────────────────────────────────────────
    health_conditions: list[dict] = field(default_factory=list)
    allergies: list[dict] = field(default_factory=list)
    medications: list[dict] = field(default_factory=list)
    dietary_restrictions: list[str] = field(default_factory=list)
    health_risk_flags: list[str] = field(default_factory=list)

    # ── Profile: Lifestyle ─────────────────────────────────────────
    sleep_duration_hours: float | None = None
    sleep_quality: str | None = None
    sleep_schedule: str | None = None
    stress_level: int | None = None
    meal_frequency: str | None = None
    cooking_preference: str | None = None
    work_schedule: str | None = None
    wake_up_time: str | None = None
    sleep_time: str | None = None
    chew_difficulty: bool | None = None

    # ── Profile: Taste & Food ───────────────────────────────────────
    taste_preferences: dict = field(default_factory=dict)
    cuisine_preferences: list[str] = field(default_factory=list)
    disliked_foods: list[str] = field(default_factory=list)
    favorite_foods: list[str] = field(default_factory=list)
    eating_speed: str | None = None

    # ── Snapshots ──────────────────────────────────────────────────
    body: BodySnapshotData = field(default_factory=BodySnapshotData)
    nutrition: NutritionSnapshot = field(default_factory=NutritionSnapshot)
    fitness: FitnessSnapshotData = field(default_factory=FitnessSnapshotData)

    # ── Memory intelligence ─────────────────────────────────────────
    key_facts: list[str] = field(default_factory=list)
    conversation_summary: str | None = None
    foods_to_avoid: list[dict] = field(default_factory=list)

    # ── Meta ───────────────────────────────────────────────────────
    profile_completeness: float = 0.0
    loaded_at: datetime = field(default_factory=datetime.utcnow)


# ─── Loader ──────────────────────────────────────────────────────────────────


async def load_full_user_context(
    user_id: int,
    db: AsyncSession,
) -> FullUserContext:
    """
    Load ALL user data in a single query via eager loading (selectinload).
    Called ONCE per request by the Orchestrator.
    Returns an empty context if loading fails (e.g., invalid user_id).
    """

    ctx = FullUserContext(user_id=user_id)

    try:
        uid: UUID
        if isinstance(user_id, UUID):
            uid = user_id
        elif isinstance(user_id, int):
            uid = UUID(int=user_id)
        else:
            uid = UUID(str(user_id))
    except (ValueError, TypeError):
        return ctx

    # ── Single query with eager loading of all relationships ─────────────────
    from app.models.user import User  # noqa: F401
    from app.models.user_profile import UserProfile  # noqa: F401
    from app.models.user_memory import UserMemory  # noqa: F401
    from app.models.nutrition_goal import NutritionGoal  # noqa: F401
    from app.models.workout_plan import WorkoutPlan  # noqa: F401
    from app.models.progress_log import ProgressLog  # noqa: F401
    from app.models.meal import MealLog  # noqa: F401

    stmt = (
        select(User)
        .where(User.id == uid)
        .options(
            selectinload(User.profile),
            selectinload(User.memory),
            selectinload(User.nutrition_goals),
            selectinload(User.workout_plans),
            selectinload(User.progress_logs),
            selectinload(User.meal_logs),
        )
    )
    result = await db.execute(stmt)
    user_obj = result.scalar_one_or_none()

    if user_obj is None:
        return ctx

    # ── Resolve resolved-from-eager-load helpers (mimic individual loaders) ─
    profile = user_obj.profile
    memory = user_obj.memory
    active_nutrition_goal = None
    if user_obj.nutrition_goals:
        for g in user_obj.nutrition_goals:
            if getattr(g, "is_active", False):
                active_nutrition_goal = g
                break
    active_workout_plan = None
    if user_obj.workout_plans:
        for p in user_obj.workout_plans:
            if getattr(p, "is_active", False):
                active_workout_plan = p
                break
    # ProgressLog already ordered by log_date.desc() via relationship — slice at app layer
    progress_logs_eager = (user_obj.progress_logs or [])[:5]
    # MealLog cutoff filtered at app layer after eager load
    meal_logs_eager = user_obj.meal_logs or []

    # ── Nutrition snapshot from eager-loaded goal ─────────────────────────────
    nutrition = {}
    if active_nutrition_goal:
        nutrition = {
            "kcal_target": float(active_nutrition_goal.daily_calorie_target),
            "protein_g":   float(active_nutrition_goal.protein_target_g),
            "carb_g":      float(active_nutrition_goal.carb_target_g),
            "fat_g":       float(active_nutrition_goal.fat_target_g),
            "hydration_ml": int(active_nutrition_goal.hydration_goal_ml)
            if active_nutrition_goal.hydration_goal_ml
            else None,
            "goal_type": (
                active_nutrition_goal.goal_type.value
                if hasattr(active_nutrition_goal.goal_type, "value")
                else str(active_nutrition_goal.goal_type)
            ),
        }

    # ── Fitness snapshot from eager-loaded plan ──────────────────────────────
    fitness = {}
    if active_workout_plan:
        fitness = {
            "active_plan_name": active_workout_plan.plan_name,
        }

    # ── Progress snapshot from eager-loaded logs (sliced) ────────────────────
    progress = {}
    weights = [
        float(log.weight_kg)
        for log in progress_logs_eager
        if log.weight_kg
    ]
    if len(weights) >= 2:
        change = round(weights[0] - weights[-1], 1)
        if change < -0.5:   trend = "losing"
        elif change > 0.5:  trend = "gaining"
        else:               trend = "stable"
        progress = {
            "weight_trend":      trend,
            "weight_change_30d": change,
        }

    # ── Meal snapshot from eager-loaded logs (filtered at app layer) ─────────
    cutoff = date.today() - timedelta(days=7)
    meals_in_range = [
        log for log in meal_logs_eager
        if log.meal_time and log.meal_time.date() >= cutoff
    ]
    meals = _aggregate_meal_logs(meals_in_range)

    # ── Profile ───────────────────────────────────────────────────
    if not isinstance(profile, Exception) and profile:
        ctx.age          = _compute_age(profile)
        ctx.gender       = getattr(profile, "gender", None)
        ctx.height_cm    = float(profile.height_cm) if profile.height_cm else None
        ctx.weight_kg    = float(profile.current_weight_kg) if profile.current_weight_kg else None
        ctx.activity_level = getattr(profile, "activity_level", None)
        if ctx.activity_level and hasattr(ctx.activity_level, "value"):
            ctx.activity_level = ctx.activity_level.value

        ctx.usage_goal        = getattr(profile, "usage_goal", None)
        ctx.usage_goal_note   = getattr(profile, "usage_goal_note", None)
        if ctx.usage_goal and hasattr(ctx.usage_goal, "value"):
            ctx.usage_goal = ctx.usage_goal.value

        ctx.health_conditions = getattr(profile, "health_conditions", []) or []
        ctx.allergies        = getattr(profile, "allergies", []) or []
        ctx.medications      = getattr(profile, "medications", []) or []
        ctx.dietary_restrictions = getattr(profile, "dietary_restrictions", []) or []

        ctx.sleep_duration_hours = getattr(profile, "sleep_duration_hours", None)
        ctx.sleep_quality       = getattr(profile, "sleep_quality", None)
        ctx.sleep_schedule      = getattr(profile, "sleep_schedule", None)
        ctx.stress_level        = getattr(profile, "stress_level", None)
        ctx.meal_frequency      = getattr(profile, "meal_frequency", None)
        ctx.cooking_preference = getattr(profile, "cooking_preference", None)
        ctx.work_schedule      = getattr(profile, "work_schedule", None)
        ctx.wake_up_time       = getattr(profile, "wake_up_time", None)
        ctx.sleep_time         = getattr(profile, "sleep_time", None)
        ctx.chew_difficulty    = getattr(profile, "chew_difficulty", None)

        ctx.taste_preferences  = getattr(profile, "taste_preferences", {}) or {}
        ctx.cuisine_preferences = getattr(profile, "cuisine_preferences", []) or []

        disliked_raw = getattr(profile, "disliked_foods", []) or []
        ctx.disliked_foods = [d if isinstance(d, str) else d.get("name", "") for d in disliked_raw]

        fav_raw = getattr(profile, "favorite_foods", []) or []
        ctx.favorite_foods = [f if isinstance(f, str) else f.get("name", "") for f in fav_raw]

        ctx.eating_speed = getattr(profile, "eating_speed", None)

        if ctx.sleep_quality and hasattr(ctx.sleep_quality, "value"):
            ctx.sleep_quality = ctx.sleep_quality.value
        if ctx.meal_frequency and hasattr(ctx.meal_frequency, "value"):
            ctx.meal_frequency = ctx.meal_frequency.value
        if ctx.cooking_preference and hasattr(ctx.cooking_preference, "value"):
            ctx.cooking_preference = ctx.cooking_preference.value

        # Health risk flags
        for condition in ctx.health_conditions:
            cid = condition.get("condition", "")
            if cid in CONDITION_RULES:
                ctx.health_risk_flags.extend(CONDITION_RULES[cid])
        ctx.health_risk_flags = list(set(ctx.health_risk_flags))

        ctx.name = (
            getattr(profile, "full_name", None) or
            getattr(profile, "display_name", None) or
            None
        )

        ctx.profile_completeness = _compute_completeness(profile)

    # ── Memory ─────────────────────────────────────────────────────
    if not isinstance(memory, Exception) and memory:
        snap = memory.body_snapshot or {}
        muscle = snap.get("muscle_status", {})

        # Priority: canonical data (UserProfile / NutritionGoal) first, then
        # AI-extracted data (UserMemory) as fallback. Canonical data is user-verified
        # and more reliable than AI-inferred values from conversation.
        ctx.body.weight_kg = ctx.weight_kg or snap.get("weight")
        ctx.body.energy_level           = snap.get("energy_level")
        ctx.body.sleep_last_night_hours = snap.get("sleep_last_night")
        ctx.body.digestion_status       = snap.get("digestion_status", "normal")
        ctx.body.sore_areas             = muscle.get("sore_areas", [])
        ctx.body.injury_areas           = muscle.get("injury_areas", [])
        ctx.body.hydration_status       = snap.get("hydration")

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        events = memory.health_events or []
        ctx.body.active_symptoms = [
            e for e in events
            if not e.get("resolved") and str(e.get("date", "")) >= cutoff
        ]

        facts = memory.key_facts or []
        ctx.key_facts = [
            f["fact"] for f in facts
            if f.get("confidence") in ("high", "medium")
        ][:8]

        ctx.conversation_summary = memory.conversation_summary

        nutrition_mem = memory.nutrition_memory or {}
        ctx.foods_to_avoid = nutrition_mem.get("foods_to_avoid", [])
        ctx.nutrition.avg_kcal_7d = nutrition_mem.get("avg_daily_kcal_7d")

        fit_mem = memory.fitness_memory or {}
        ctx.fitness.fitness_level         = fit_mem.get("fitness_level", "intermediate")
        ctx.fitness.last_workout_date    = fit_mem.get("last_workout_date")
        ctx.fitness.workout_frequency_7d = fit_mem.get("workout_frequency_7d", 0)
        ctx.fitness.preferred_types      = fit_mem.get("preferred_workout_types", [])
        ctx.fitness.current_restrictions  = fit_mem.get("current_restrictions", [])

    # ── Nutrition Goal ─────────────────────────────────────────────
    if not isinstance(nutrition, Exception) and nutrition:
        ctx.nutrition.kcal_target       = nutrition.get("kcal_target")
        ctx.nutrition.protein_target_g  = nutrition.get("protein_g")
        ctx.nutrition.carb_target_g    = nutrition.get("carb_g")
        ctx.nutrition.fat_target_g     = nutrition.get("fat_g")
        ctx.nutrition.hydration_target_ml = nutrition.get("hydration_ml")
        ctx.nutrition.goal_type        = nutrition.get("goal_type")

    # ── Progress ───────────────────────────────────────────────────
    if not isinstance(progress, Exception) and progress:
        ctx.body.weight_trend         = progress.get("weight_trend")
        ctx.body.weight_change_kg_30d = progress.get("weight_change_30d")

    # ── Meal Logs ──────────────────────────────────────────────────
    if not isinstance(meals, Exception) and meals:
        today = date.today()
        today_str = today.isoformat()

        today_meals = [m for m in meals if m.get("date") == today_str]
        # Cast totals to float to avoid Decimal-vs-float TypeError when
        # computing kcal_gap_today = float(kcal_target) - today_kcal below.
        # Decimal propagates from SQLAlchemy Numeric columns (e.g.
        # MealLog.total_calories). The annotation today_kcal: float
        # documents intent but Python dataclasses don't coerce, so we
        # must do it explicitly here.
        ctx.nutrition.today_meals       = today_meals
        ctx.nutrition.today_kcal        = float(sum(m.get("kcal", 0) for m in today_meals))
        ctx.nutrition.today_protein_g   = float(sum(m.get("protein_g", 0) for m in today_meals))
        ctx.nutrition.today_carb_g      = float(sum(m.get("carb_g", 0) for m in today_meals))
        ctx.nutrition.today_fat_g       = float(sum(m.get("fat_g", 0) for m in today_meals))

        ctx.nutrition.recent_daily_totals = meals[:7]

        if meals and ctx.nutrition.avg_kcal_7d is None:
            dates_with_data = {m.get("date") for m in meals if m.get("kcal", 0) > 0}
            if dates_with_data:
                daily = {}
                for m in meals:
                    d = m.get("date")
                    if d:
                        daily.setdefault(d, 0)
                        daily[d] += m.get("kcal", 0)
                if daily:
                    ctx.nutrition.avg_kcal_7d = round(sum(daily.values()) / len(daily))

    return ctx


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _aggregate_meal_logs(logs: list) -> list[dict]:
    """Aggregate meal log records into daily totals."""
    daily_totals: dict[str, dict] = {}
    for log in logs:
        d = log.meal_time.date().isoformat()
        if d not in daily_totals:
            daily_totals[d] = {
                "date": d, "kcal": 0, "protein_g": 0, "carb_g": 0, "fat_g": 0, "meals": 0
            }
        daily_totals[d]["kcal"]      += log.total_calories or 0
        daily_totals[d]["protein_g"] += log.total_protein_g or 0
        daily_totals[d]["carb_g"]    += log.total_carb_g or 0
        daily_totals[d]["fat_g"]     += log.total_fat_g or 0
        daily_totals[d]["meals"]     += 1
    return list(daily_totals.values())


def _compute_age(profile) -> int | None:
    dob = getattr(profile, "date_of_birth", None)
    if dob:
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return None


def _compute_completeness(profile) -> float:
    score = 0.0
    if getattr(profile, "current_weight_kg", None):    score += 0.15
    if getattr(profile, "height_cm", None):          score += 0.15
    if getattr(profile, "usage_goal", None):         score += 0.20
    if getattr(profile, "health_conditions", None):  score += 0.20
    if getattr(profile, "sleep_duration_hours", None): score += 0.15
    if getattr(profile, "taste_preferences", None): score += 0.15
    return min(score, 1.0)


# ─── Sensitive Demographics Detection ───────────────────────────────────────────


PREGNANCY_KEYWORDS = [
    "mang thai", "có thai", "đang bầu", "thai kỳ",
    "tuần thai", "tháng thai", "thai nhi", "bầu bí",
    "pregnant", "pregnancy", "trimester",
]

BREASTFEEDING_KEYWORDS = [
    "cho con bú", "đang cho bú", "nuôi con bằng sữa mẹ",
    "breastfeeding", "lactating",
]


def detect_sensitive_demographics(
    profile,
    memory,
    current_message: str,
    full_context=None,
) -> dict[str, bool]:
    """
    Detect sensitive demographic flags from profile data and message text.

    Returns a dict with:
      - is_pregnant       : True if pregnancy keywords in message or profile conditions
      - is_breastfeeding   : True if breastfeeding keywords in message
      - is_minor          : True if age < 18
      - is_elderly        : True if age >= 65
    """
    flags: dict[str, bool] = {
        "is_pregnant": False,
        "is_breastfeeding": False,
        "is_minor": False,
        "is_elderly": False,
    }

    msg_lower = current_message.lower()

    # Pregnancy — from message text
    if any(kw in msg_lower for kw in PREGNANCY_KEYWORDS):
        flags["is_pregnant"] = True

    # Pregnancy — from profile health_conditions
    profile_conditions: list = getattr(profile, "health_conditions", []) or []
    for cond in profile_conditions:
        cond_str = str(cond).lower()
        if any(kw in cond_str for kw in PREGNANCY_KEYWORDS):
            flags["is_pregnant"] = True
            break

    # Breastfeeding — from message
    if any(kw in msg_lower for kw in BREASTFEEDING_KEYWORDS):
        flags["is_breastfeeding"] = True

    # Age-based flags — from full_context.age (preferred) or profile DOB
    age: int | None = None
    if full_context is not None:
        age = getattr(full_context, "age", None)
    if age is None:
        dob = getattr(profile, "date_of_birth", None)
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age is not None:
        if age < 18:
            flags["is_minor"] = True
        if age >= 65:
            flags["is_elderly"] = True

    return flags

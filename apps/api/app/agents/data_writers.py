"""
Data writers for the UpdateProposal system.
Each writer takes a confirmed UpdateProposal and writes to the correct DB table.
Called ONLY after user confirms via UpdateProposalCard.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory_service import apply_memory_updates, get_or_create_memory
from app.models import MealItem, MealLog, NutritionGoal, ProgressLog, UserProfile
from app.models.enums import MealLogSourceType, MealTypeEnum
from app.schemas.meal import MealLogCreate, MealItemCreate
from app.schemas.update_proposal import UpdateProposal, UpdateTarget
from app.services.daily_recommendation_service import invalidate_user_plan_cache
from app.services.meal_service import create_meal_log_with_items, recalculate_meal_totals

logger = logging.getLogger(__name__)

# ── Biological safety constants ───────────────────────────────────────────────────
# Absolute minimum calories — below these values is clinically unsafe.
# These are conservative floors regardless of individual BMR.
MIN_DAILY_CALORIES = 1000   # kcal — absolute clinical minimum (hard floor)
MIN_WEIGHT_KG = 20.0        # kg  — below ~44 lbs is biologically implausible
MAX_WEIGHT_KG = 300.0       # kg  — above ~660 lbs is biologically implausible
MAX_PROTEIN_G = 300        # g   — reasonable upper bound for any individual
MAX_FAT_G = 200             # g   — reasonable upper bound
MAX_CARB_G = 900            # g   — reasonable upper bound
MAX_TOTAL_CALORIES = 6000   # kcal — reasonable upper bound for any individual

logger = logging.getLogger(__name__)


class DataWriteResult(BaseModel):
    success: bool
    target: UpdateTarget
    message: str
    records_created: int = 0
    records_updated: int = 0
    error: str | None = None


async def execute_confirmed_update(
    proposal: UpdateProposal,
    user_id: int,
    db: AsyncSession,
) -> DataWriteResult:
    writers = {
        UpdateTarget.MEAL_LOG: _write_meal_log,
        UpdateTarget.BODY_WEIGHT: _write_body_weight,
        UpdateTarget.BODY_MEASUREMENT: _write_body_measurement,
        UpdateTarget.HEALTH_SYMPTOM: _write_health_symptom,
        UpdateTarget.HEALTH_RECOVERY: _write_health_recovery,
        UpdateTarget.WORKOUT_LOG: _write_workout_log,
        UpdateTarget.MUSCLE_SORENESS: _write_muscle_soreness,
        UpdateTarget.PROFILE_METRIC: _write_profile_metric,
        UpdateTarget.SLEEP_LOG: _write_sleep_log,
        UpdateTarget.NUTRITION_GOAL: _write_nutrition_goal,
    }

    writer = writers.get(proposal.target)
    if not writer:
        return DataWriteResult(
            success=False,
            target=proposal.target,
            message="Khong ho tro loai cap nhat nay",
            error=f"No writer for {proposal.target}",
        )

    try:
        result = await writer(proposal.raw_data, user_id, db)
        await db.commit()
        await invalidate_user_plan_cache(_user_uuid(user_id))
        return result
    except Exception as e:
        await db.rollback()
        logger.exception(f"DataWriter failed for {proposal.target}: {e}")
        return DataWriteResult(
            success=False,
            target=proposal.target,
            message="Luu du lieu that bai, vui long thu lai",
            error=str(e),
        )


def _user_uuid(user_id: int | uuid.UUID) -> uuid.UUID:
    """Convert user_id to UUID. Handles both int (PK) and UUID forms."""
    if isinstance(user_id, uuid.UUID):
        return user_id
    if isinstance(user_id, int):
        return uuid.UUID(int=user_id)
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise ValueError(f"Cannot convert {user_id!r} to UUID")


def _user_int(user_id: int | uuid.UUID) -> int:
    if isinstance(user_id, int):
        return user_id
    return user_id.int


async def _write_meal_log(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    raw_items = data.get("items", [])
    if not raw_items:
        return DataWriteResult(
            success=False, target=UpdateTarget.MEAL_LOG,
            message="Khong co thong tin mon an",
            error="No items in raw_data",
        )

    user_uuid = _user_uuid(user_id)
    meal_time_str = data.get("logged_at")
    meal_time = datetime.fromisoformat(meal_time_str) if meal_time_str else datetime.utcnow()

    meal_type_raw = data.get("meal_type", "khac")
    try:
        meal_type = MealTypeEnum(meal_type_raw)
    except (ValueError, TypeError):
        meal_type = MealTypeEnum.bua_trua

    source_raw = data.get("source", "chat_extraction")
    try:
        source = MealLogSourceType(source_raw)
    except (ValueError, TypeError):
        source = MealLogSourceType.chat_extraction

    meal_log_payload = MealLogCreate(
        meal_type=meal_type,
        meal_time=meal_time,
        source=source,
        note=data.get("notes"),
        items=[
            MealItemCreate(
                detected_food_name=item.get("detected_food_name", item.get("food_name", "Unknown")),
                estimated_weight_g=item.get("estimated_weight_g", item.get("quantity", 100)),
            )
            for item in raw_items
        ],
    )

    try:
        meal_log = await create_meal_log_with_items(db, meal_log_payload, user_uuid)
    except Exception as e:
        return DataWriteResult(
            success=False, target=UpdateTarget.MEAL_LOG,
            message=f"Khong the tao ban ghi bua an: {e}",
            error=str(e),
        )

    meal_type_vn = {
        MealTypeEnum.bua_sang: "Bua sang",
        MealTypeEnum.bua_trua: "Bua trua",
        MealTypeEnum.bua_toi: "Bua toi",
        MealTypeEnum.an_vat: "Bua phu",
        MealTypeEnum.khac: "Bua an",
    }.get(meal_log.meal_type, "Bua an")

    return DataWriteResult(
        success=True, target=UpdateTarget.MEAL_LOG,
        message=f"Da luu {meal_type_vn} (~{meal_log.total_calories:.0f} kcal)",
        records_created=1 + len(raw_items),
    )


async def _write_body_weight(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    weight = data.get("weight_kg")
    if not weight:
        return DataWriteResult(
            success=False, target=UpdateTarget.BODY_WEIGHT,
            message="Khong co du lieu can nang",
            error="Missing weight_kg",
        )

    # Weight range validation (biomedical safety floors)
    try:
        weight_val = float(weight)
    except (TypeError, ValueError):
        return DataWriteResult(
            success=False, target=UpdateTarget.BODY_WEIGHT,
            message="Gia tri can nang khong hop le",
            error=f"weight_kg={weight!r} cannot be converted to float",
        )

    if not (MIN_WEIGHT_KG <= weight_val <= MAX_WEIGHT_KG):
        logger.warning(
            "[DataWriter] Weight %.1f kg outside safe range [%.0f-%.0f] for user %s",
            weight_val, MIN_WEIGHT_KG, MAX_WEIGHT_KG, user_id
        )
        return DataWriteResult(
            success=False, target=UpdateTarget.BODY_WEIGHT,
            message=f"Can nang phai trong khoang {MIN_WEIGHT_KG}-{MAX_WEIGHT_KG} kg",
            error=f"weight_kg={weight_val} outside safe range [{MIN_WEIGHT_KG}, {MAX_WEIGHT_KG}]",
        )

    user_uuid = _user_uuid(user_id)
    await db.execute(
        update(UserProfile)
        .where(UserProfile.user_id == user_uuid)
        .values(current_weight_kg=weight)
    )

    log_date = date.fromisoformat(data.get("measured_at", date.today().isoformat()))
    progress = ProgressLog(
        user_id=user_uuid, log_date=log_date, weight_kg=weight
    )
    db.add(progress)

    await apply_memory_updates(
        _user_int(user_id), {"body_snapshot": {"weight": weight}}, db,
        agent_name=None,
    )

    return DataWriteResult(
        success=True, target=UpdateTarget.BODY_WEIGHT,
        message=f"Da cap nhat can nang: {weight} kg",
        records_updated=1, records_created=1,
    )


async def _write_body_measurement(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    user_uuid = _user_uuid(user_id)
    progress = ProgressLog(
        user_id=user_uuid,
        log_date=date.fromisoformat(data.get("logged_date", date.today().isoformat())),
        waist_cm=data.get("waist_cm"),
        chest_cm=data.get("chest_cm"),
        hip_cm=data.get("hip_cm"),
        body_fat_percent=data.get("body_fat_pct"),
    )
    db.add(progress)

    parts = []
    if data.get("waist_cm"): parts.append(f"eo {data['waist_cm']}cm")
    if data.get("chest_cm"): parts.append(f"nguc {data['chest_cm']}cm")
    if data.get("body_fat_pct"): parts.append(f"mo {data['body_fat_pct']}%")

    return DataWriteResult(
        success=True, target=UpdateTarget.BODY_MEASUREMENT,
        message=f"Da luu so do: {', '.join(parts) if parts else 'so do'}",
        records_created=1,
    )


async def _write_health_symptom(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    new_event = {
        "event_id": str(uuid.uuid4()),
        "date": data.get("date", date.today().isoformat()),
        "type": "symptom",
        "category": data.get("category", "other"),
        "description": data.get("description", ""),
        "severity": data.get("severity", "mild"),
        "resolved": False,
        "source_session_id": data.get("session_id", ""),
        "extracted_at": datetime.utcnow().isoformat(),
    }
    await apply_memory_updates(
        _user_int(user_id), {"health_events": [new_event]}, db,
        agent_name=None,
    )

    return DataWriteResult(
        success=True, target=UpdateTarget.HEALTH_SYMPTOM,
        message=f"Da ghi nhan: {data.get('description', 'trieu chung')}",
        records_created=1,
    )


async def _write_health_recovery(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    memory = await get_or_create_memory(_user_int(user_id), db)
    events = memory.health_events or []
    description = data.get("description", "").lower()
    updated = 0
    for event in events:
        if not event.get("resolved"):
            event_desc = event.get("description", "").lower()
            if any(word in event_desc for word in description.split()[:3] if len(word) > 2):
                event["resolved"] = True
                event["resolved_at"] = datetime.utcnow().isoformat()
                updated += 1
    if updated:
        await apply_memory_updates(
            _user_int(user_id), {"health_events": events}, db,
            agent_name=None,
        )

    return DataWriteResult(
        success=True, target=UpdateTarget.HEALTH_RECOVERY,
        message="Da cap nhat: ban da hoi phuc",
        records_updated=updated,
    )


async def _write_workout_log(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    await apply_memory_updates(
        _user_int(user_id),
        {
            "fitness_memory": {
                "last_workout_date": date.today().isoformat(),
                "last_workout_type": data.get("workout_type", ""),
                "last_workout_duration": data.get("duration_minutes"),
            }
        },
        db,
        agent_name=None,
    )
    duration = data.get("duration_minutes")
    workout_type = data.get("workout_type", "buoi tap")
    msg = f"Da luu: {workout_type}"
    if duration:
        msg += f" ({duration} phut)"

    return DataWriteResult(
        success=True, target=UpdateTarget.WORKOUT_LOG,
        message=msg, records_created=1,
    )


async def _write_muscle_soreness(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    areas = data.get("sore_areas", [])
    action = data.get("action", "add")
    memory = await get_or_create_memory(_user_int(user_id), db)
    snap = memory.body_snapshot or {}
    muscle = snap.get("muscle_status", {})
    existing = muscle.get("sore_areas", [])

    if action == "remove":
        updated_areas = [a for a in existing if a not in areas]
    else:
        updated_areas = list(set(existing + areas))

    await apply_memory_updates(
        _user_int(user_id),
        {"body_snapshot": {"muscle_status": {"sore_areas": updated_areas}}},
        db,
        agent_name=None,
    )
    action_vn = "Da ghi nhan" if action == "add" else "Da xoa"
    return DataWriteResult(
        success=True, target=UpdateTarget.MUSCLE_SORENESS,
        message=f"{action_vn} vung dau: {', '.join(areas)}",
        records_updated=1,
    )


async def _write_profile_metric(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    field_mapping = {
        "height_cm": "height_cm",
        "weight_kg": "current_weight_kg",
    }
    updates = {}
    for raw_field, db_field in field_mapping.items():
        if raw_field in data:
            updates[db_field] = data[raw_field]

    if not updates:
        return DataWriteResult(
            success=False, target=UpdateTarget.PROFILE_METRIC,
            message="Khong co thong tin de cap nhat",
            error="No valid fields",
        )

    await db.execute(
        update(UserProfile)
        .where(UserProfile.user_id == _user_uuid(user_id))
        .values(**updates)
    )
    parts = [f"{k}: {v}" for k, v in updates.items()]
    return DataWriteResult(
        success=True, target=UpdateTarget.PROFILE_METRIC,
        message=f"Da cap nhat ho so: {', '.join(parts)}",
        records_updated=1,
    )


async def _write_sleep_log(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    hours = data.get("hours")
    quality = data.get("quality")
    updates = {}
    if hours:
        updates["sleep_last_night"] = hours
    if quality:
        updates["sleep_quality_last_night"] = quality
    if updates:
        await apply_memory_updates(
            _user_int(user_id), {"body_snapshot": updates}, db,
            agent_name=None,
        )

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if quality:
        parts.append(quality)

    return DataWriteResult(
        success=True, target=UpdateTarget.SLEEP_LOG,
        message=f"Da ghi nhan giac ngu: {', '.join(parts) if parts else 'giac ngu'}",
        records_updated=1 if updates else 0,
    )


async def _write_nutrition_goal(
    data: dict[str, Any], user_id: int, db: AsyncSession
) -> DataWriteResult:
    field_mapping = {
        "daily_calories": "daily_calorie_target",
        "protein_g": "protein_target_g",
        "carb_g": "carb_target_g",
        "fat_g": "fat_target_g",
        "hydration_goal_ml": "hydration_goal_ml",
    }
    updates = {}
    for raw_field, db_field in field_mapping.items():
        if raw_field in data:
            value = data[raw_field]
            # ── D-2 / A-5: Application-layer range validation ─────────────────────
            if db_field == "daily_calorie_target":
                try:
                    cal_val = float(value)
                except (TypeError, ValueError):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Gia tri calories khong hop le",
                        error=f"daily_calorie_target={value!r} not numeric",
                    )
                if not (MIN_DAILY_CALORIES <= cal_val <= MAX_TOTAL_CALORIES):
                    logger.warning(
                        "[DataWriter] daily_calorie_target=%.0f outside safe range "
                        "[%d-%d] for user %s", cal_val, MIN_DAILY_CALORIES,
                        MAX_TOTAL_CALORIES, user_id
                    )
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message=f"Calories phai trong khoang {MIN_DAILY_CALORIES}-{MAX_TOTAL_CALORIES}",
                        error=f"daily_calorie_target={cal_val} outside safe range",
                    )
            if db_field == "protein_target_g":
                try:
                    p_val = float(value)
                except (TypeError, ValueError):
                    p_val = None
                if p_val is not None and not (0 <= p_val <= MAX_PROTEIN_G):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message=f"Protein phai trong khoang 0-{MAX_PROTEIN_G}g",
                        error=f"protein_target_g={p_val} outside safe range",
                    )
            if db_field == "fat_target_g":
                try:
                    f_val = float(value)
                except (TypeError, ValueError):
                    f_val = None
                if f_val is not None and not (0 <= f_val <= MAX_FAT_G):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message=f"Fat phai trong khoang 0-{MAX_FAT_G}g",
                        error=f"fat_target_g={f_val} outside safe range",
                    )
            # Explicit application-layer range validation for carbs and hydration
            if db_field == "carb_target_g":
                try:
                    c_val = float(value)
                except (TypeError, ValueError):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Gia tri carbohydrate khong hop le",
                        error=f"carb_target_g={value!r} not numeric",
                    )
                if not (0 <= c_val <= 1500):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Carbohydrate target phai trong khoang 0-1500g",
                        error="Carbohydrate target out of biomedical safe bounds [0, 1500]g",
                    )
            if db_field == "hydration_goal_ml":
                try:
                    h_val = float(value)
                except (TypeError, ValueError):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Gia tri hydration khong hop le",
                        error=f"hydration_goal_ml={value!r} not numeric",
                    )
                if not (500 <= h_val <= 10000):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Hydration target phai trong khoang 500-10000ml",
                        error="Hydration target out of safe bounds [500, 10000]ml",
                    )
            updates[db_field] = value

    if not updates:
        return DataWriteResult(
            success=False, target=UpdateTarget.NUTRITION_GOAL,
            message="Khong co thong tin muc tieu de cap nhat",
        )

    await db.execute(
        update(NutritionGoal)
        .where(NutritionGoal.user_id == _user_uuid(user_id))
        .where(NutritionGoal.is_active == True)
        .values(**updates)
    )
    return DataWriteResult(
        success=True, target=UpdateTarget.NUTRITION_GOAL,
        message="Da cap nhat muc tieu dinh duong",
        records_updated=1,
    )
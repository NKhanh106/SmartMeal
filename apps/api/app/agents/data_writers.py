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
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory_service import apply_memory_updates, get_or_create_memory
from app.models import MealItem, MealLog, NutritionGoal, ProgressLog, UserProfile
from app.models.enums import ItemSourceType, MealLogSourceType, MealLogStatus, MealTypeEnum
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
            message="Không hỗ trợ loại cập nhật này",
            error=f"No writer for {proposal.target}",
        )

    try:
        # Pass session_id so writers can locate the PENDING preview record
        # the background extractor created for this proposal and update it
        # in place instead of inserting a duplicate row.
        result = await writer(
            proposal.raw_data, user_id, db,
            session_id=proposal.session_id or None,
        )
        await db.commit()
        await invalidate_user_plan_cache(_user_uuid(user_id))
        return result
    except Exception as e:
        await db.rollback()
        logger.exception(f"DataWriter failed for {proposal.target}: {e}")
        return DataWriteResult(
            success=False,
            target=proposal.target,
            message="Lưu dữ liệu thất bại, vui lòng thử lại",
            error=str(e),
        )


def _user_uuid(user_id: int | uuid.UUID | str) -> uuid.UUID:
    """Convert user_id to UUID. Handles int (PK), UUID, and str forms."""
    if isinstance(user_id, uuid.UUID):
        return user_id
    if isinstance(user_id, int):
        return uuid.UUID(int=user_id)
    # Handle string input - common case when data comes from Redis/API
    s = str(user_id)
    try:
        return uuid.UUID(s)
    except ValueError:
        raise ValueError(f"Cannot convert {user_id!r} to UUID")


def _user_int(user_id: int | uuid.UUID | str) -> int:
    if isinstance(user_id, int):
        return user_id
    if isinstance(user_id, uuid.UUID):
        return user_id.int
    # Try parsing as int first (handles "1", "123")
    try:
        return int(user_id)
    except (ValueError, TypeError):
        pass
    # Try parsing as UUID string
    try:
        return uuid.UUID(str(user_id)).int
    except (ValueError, TypeError):
        raise ValueError(f"Cannot convert {user_id!r} to int")


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    """Convert a string/UUID into a UUID object; return None on bad input."""
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


async def _write_meal_log(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
) -> DataWriteResult:
    raw_items = data.get("items", [])
    if not raw_items:
        return DataWriteResult(
            success=False, target=UpdateTarget.MEAL_LOG,
            message="Không có thông tin món ăn",
            error="No items in raw_data",
        )

    user_uuid = _user_uuid(user_id)
    meal_time_str = data.get("logged_at")
    meal_time = datetime.fromisoformat(meal_time_str) if meal_time_str else datetime.utcnow()

    meal_type_raw = data.get("meal_type", "khac")
    # Map extractor output (English) → MealTypeEnum (Vietnamese snake_case).
    # ExtractorAgent schema returns "breakfast|lunch|dinner|snack|empty".
    # proposal_builder.py also maps these for display, but the writer must
    # also translate before passing to MealTypeEnum — otherwise the value
    # raises ValueError and falls back to bua_trua (wrong meal).
    meal_type_aliases = {
        "breakfast": MealTypeEnum.bua_sang,
        "bua_sang":  MealTypeEnum.bua_sang,
        "lunch":     MealTypeEnum.bua_trua,
        "bua_trua":  MealTypeEnum.bua_trua,
        "dinner":    MealTypeEnum.bua_toi,
        "bua_toi":   MealTypeEnum.bua_toi,
        "snack":     MealTypeEnum.an_vat,
        "an_vat":    MealTypeEnum.an_vat,
        "empty":     MealTypeEnum.khac,
    }
    raw_str = str(meal_type_raw).lower().strip() if meal_type_raw else "khac"
    meal_type = meal_type_aliases.get(raw_str)
    if meal_type is None:
        try:
            meal_type = MealTypeEnum(raw_str)
        except (ValueError, TypeError):
            meal_type = MealTypeEnum.bua_trua

    source_raw = data.get("source", "chat_extraction")
    try:
        source = MealLogSourceType(source_raw)
    except (ValueError, TypeError):
        source = MealLogSourceType.chat_extraction

    # Promote the PENDING "preview" record the background extractor created
    # for this same chat session, so we don't end up with two rows (PENDING
    # + APPROVED) for one confirmed meal. If no PENDING matches the session
    # (e.g. legacy flow, manual entry, or extractor was disabled) fall back
    # to inserting a fresh row.
    promoted = await _promote_pending_meal_log(
        db=db,
        user_uuid=user_uuid,
        session_id=session_id,
        raw_items=raw_items,
        meal_type=meal_type,
        meal_time=meal_time,
        source=source,
        note=data.get("notes"),
    )
    if promoted is not None:
        logger.info(
            "[DataWriter] Promoted existing PENDING MealLog to APPROVED "
            "for user %s session %s meal_type=%s meal_time=%s",
            user_uuid, session_id, meal_type, meal_time
        )
        return promoted

    # No PENDING found — create a new APPROVED MealLog directly
    logger.info(
        "[DataWriter] No PENDING MealLog found, creating new APPROVED MealLog "
        "for user %s session %s meal_type=%s meal_time=%s",
        user_uuid, session_id, meal_type, meal_time
    )

    meal_log_payload = MealLogCreate(
        meal_type=meal_type,
        meal_time=meal_time,
        source=source,
        note=data.get("notes"),
        # Persist session_id inside extracted_data so any subsequent
        # `_promote_pending_meal_log` call for the same chat session still
        # matches this APPROVED row (e.g. if the user re-confirms or
        # re-extracts from the same session later). Without this, the JSONB
        # lookup has nothing to key on and the writer creates a fresh row
        # every time, leaving orphan PENDING previews behind.
        extracted_data=(
            {
                "session_id": str(session_id) if session_id is not None else None,
                "items": raw_items,
            }
            if session_id is not None
            else None
        ),
        items=[
            MealItemCreate(
                detected_food_name=item.get("detected_food_name", item.get("food_name", "Unknown")),
                estimated_weight_g=item.get("estimated_weight_g", item.get("quantity", 100)),
                food_nutrition_id=_coerce_uuid(item.get("food_nutrition_id")),
                # Persist AI/DB-computed nutrition so the MealLog row keeps
                # non-zero totals even if food_nutrition_id is unset (food
                # not in catalog). Without this, total_calories silently
                # resets to 0 on dashboard.
                calories=item.get("calories"),
                protein_g=item.get("protein_g"),
                carb_g=item.get("carb_g"),
                fat_g=item.get("fat_g"),
            )
            for item in raw_items
        ],
    )

    try:
        meal_log = await create_meal_log_with_items(db, meal_log_payload, user_uuid)
    except Exception as e:
        return DataWriteResult(
            success=False, target=UpdateTarget.MEAL_LOG,
            message=f"Không thể tạo bản ghi bữa ăn: {e}",
            error=str(e),
        )

    meal_type_vn = _meal_type_vn(meal_log.meal_type)

    return DataWriteResult(
        success=True, target=UpdateTarget.MEAL_LOG,
        message=f"Đã lưu {meal_type_vn} (~{meal_log.total_calories:.0f} kcal)",
        records_created=1 + len(raw_items),
    )


async def _promote_pending_meal_log(
    db: AsyncSession,
    user_uuid: uuid.UUID,
    session_id: str | None,
    raw_items: list[dict[str, Any]],
    meal_type: MealTypeEnum,
    meal_time: datetime,
    source: MealLogSourceType,
    note: str | None,
) -> DataWriteResult | None:
    """Find the PENDING MealLog the background extractor pre-wrote for this
    session and promote it to APPROVED with the confirmed items attached.

    Returns None when there is no matching PENDING so the caller can fall
    back to creating a fresh MealLog row.
    """
    if not session_id:
        return None

    from sqlalchemy import cast, type_coerce
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.types import String

    # The background extractor stores session_id inside the extracted_data
    # JSONB column. Match on that so we update the preview row in place.
    stmt = select(MealLog).where(
        MealLog.user_id == user_uuid,
        MealLog.status == MealLogStatus.PENDING,
        cast(
            type_coerce(MealLog.extracted_data, JSONB)["session_id"],
            String,
        ) == str(session_id),
    ).order_by(MealLog.created_at.desc()).limit(1)

    pending = (await db.execute(stmt)).scalar_one_or_none()
    if pending is None:
        logger.debug(
            "[DataWriter] No PENDING MealLog found for user %s session %s "
            "(will create new APPROVED row directly)",
            user_uuid, session_id
        )
        return None

    logger.info(
        "[DataWriter] Found PENDING MealLog id=%s for user %s session %s, promoting to APPROVED",
        pending.id, user_uuid, session_id
    )

    # Replace stale preview MealItem rows (PENDING pre-writes usually have
    # none, but defend against any future schema that pre-populates them).
    await db.execute(
        delete(MealItem).where(MealItem.meal_log_id == pending.id)
    )

    # Update the MealLog itself.
    pending.status = MealLogStatus.APPROVED
    pending.meal_type = meal_type
    pending.meal_time = meal_time
    pending.source = source
    if note:
        pending.note = note
    # Totals will be recalculated from the freshly-attached MealItem rows.
    pending.total_calories = 0
    pending.total_protein_g = 0
    pending.total_carb_g = 0
    pending.total_fat_g = 0
    await db.flush()

    # Attach the confirmed MealItem rows.
    for item in raw_items:
        food_id = _coerce_uuid(item.get("food_nutrition_id"))
        db.add(MealItem(
            meal_log_id=pending.id,
            food_nutrition_id=food_id,
            detected_food_name=item.get("detected_food_name", item.get("food_name", "Unknown")),
            display_food_name=item.get("display_food_name"),
            estimated_weight_g=float(item.get("estimated_weight_g") or item.get("quantity") or 100),
            calories=float(item.get("calories") or 0),
            protein_g=float(item.get("protein_g") or 0),
            carb_g=float(item.get("carb_g") or 0),
            fat_g=float(item.get("fat_g") or 0),
            confidence=float(item.get("confidence")) if item.get("confidence") is not None else None,
            source=item.get("source") or ItemSourceType.ai_nhan_dien,
        ))

    # Sum attached items into MealLog totals so dashboard reads the right
    # value without an extra roundtrip.
    await recalculate_meal_totals(db, pending.id)

    meal_type_vn = _meal_type_vn(pending.meal_type)
    return DataWriteResult(
        success=True, target=UpdateTarget.MEAL_LOG,
        message=f"Đã lưu {meal_type_vn} (~{pending.total_calories:.0f} kcal)",
        records_created=len(raw_items),
        records_updated=1,
    )


def _meal_type_vn(meal_type: MealTypeEnum) -> str:
    return {
        MealTypeEnum.bua_sang: "Bữa sáng",
        MealTypeEnum.bua_trua: "Bữa trưa",
        MealTypeEnum.bua_toi: "Bữa tối",
        MealTypeEnum.an_vat: "Ăn vặt",
        MealTypeEnum.khac: "Bữa ăn",
    }.get(meal_type, "Bữa ăn")


async def _write_body_weight(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
) -> DataWriteResult:
    weight = data.get("weight_kg")
    if not weight:
        return DataWriteResult(
            success=False, target=UpdateTarget.BODY_WEIGHT,
            message="Không có dữ liệu cân nặng",
            error="Missing weight_kg",
        )

    # Weight range validation (biomedical safety floors)
    try:
        weight_val = float(weight)
    except (TypeError, ValueError):
        return DataWriteResult(
            success=False, target=UpdateTarget.BODY_WEIGHT,
            message="Giá trị cân nặng không hợp lệ",
            error=f"weight_kg={weight!r} cannot be converted to float",
        )

    if not (MIN_WEIGHT_KG <= weight_val <= MAX_WEIGHT_KG):
        logger.warning(
            "[DataWriter] Weight %.1f kg outside safe range [%.0f-%.0f] for user %s",
            weight_val, MIN_WEIGHT_KG, MAX_WEIGHT_KG, user_id
        )
        return DataWriteResult(
            success=False, target=UpdateTarget.BODY_WEIGHT,
            message=f"Cân nặng phải trong khoảng {MIN_WEIGHT_KG}-{MAX_WEIGHT_KG} kg",
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
        message=f"Đã cập nhật cân nặng: {weight} kg",
        records_updated=1, records_created=1,
    )


async def _write_body_measurement(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
    if data.get("chest_cm"): parts.append(f"ngực {data['chest_cm']}cm")
    if data.get("body_fat_pct"): parts.append(f"mỡ {data['body_fat_pct']}%")

    return DataWriteResult(
        success=True, target=UpdateTarget.BODY_MEASUREMENT,
        message=f"Đã lưu số đo: {', '.join(parts) if parts else 'số đo'}",
        records_created=1,
    )


async def _write_health_symptom(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
        message=f"Đã ghi nhận: {data.get('description', 'triệu chứng')}",
        records_created=1,
    )


async def _write_health_recovery(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
        message="Đã cập nhật: bạn đã hồi phục",
        records_updated=updated,
    )


async def _write_workout_log(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
    workout_type = data.get("workout_type", "buổi tập")
    msg = f"Đã lưu: {workout_type}"
    if duration:
        msg += f" ({duration} phút)"

    return DataWriteResult(
        success=True, target=UpdateTarget.WORKOUT_LOG,
        message=msg, records_created=1,
    )


async def _write_muscle_soreness(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
    action_vn = "Đã ghi nhận" if action == "add" else "Đã xóa"
    return DataWriteResult(
        success=True, target=UpdateTarget.MUSCLE_SORENESS,
        message=f"{action_vn} vùng đau: {', '.join(areas)}",
        records_updated=1,
    )


async def _write_profile_metric(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
            message="Không có thông tin để cập nhật",
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
        message=f"Đã cập nhật hồ sơ: {', '.join(parts)}",
        records_updated=1,
    )


async def _write_sleep_log(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
        message=f"Đã ghi nhận giấc ngủ: {', '.join(parts) if parts else 'giấc ngủ'}",
        records_updated=1 if updates else 0,
    )


async def _write_nutrition_goal(
    data: dict[str, Any], user_id: int, db: AsyncSession,
    session_id: str | None = None,
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
                        message="Giá trị calories không hợp lệ",
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
                        message=f"Calories phải trong khoảng {MIN_DAILY_CALORIES}-{MAX_TOTAL_CALORIES}",
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
                        message=f"Protein phải trong khoảng 0-{MAX_PROTEIN_G}g",
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
                        message=f"Fat phải trong khoảng 0-{MAX_FAT_G}g",
                        error=f"fat_target_g={f_val} outside safe range",
                    )
            # Explicit application-layer range validation for carbs and hydration
            if db_field == "carb_target_g":
                try:
                    c_val = float(value)
                except (TypeError, ValueError):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Giá trị carbohydrate không hợp lệ",
                        error=f"carb_target_g={value!r} not numeric",
                    )
                if not (0 <= c_val <= 1500):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Carbohydrate target phải trong khoảng 0-1500g",
                        error="Carbohydrate target out of biomedical safe bounds [0, 1500]g",
                    )
            if db_field == "hydration_goal_ml":
                try:
                    h_val = float(value)
                except (TypeError, ValueError):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Giá trị hydration không hợp lệ",
                        error=f"hydration_goal_ml={value!r} not numeric",
                    )
                if not (500 <= h_val <= 10000):
                    return DataWriteResult(
                        success=False, target=UpdateTarget.NUTRITION_GOAL,
                        message="Hydration target phải trong khoảng 500-10000ml",
                        error="Hydration target out of safe bounds [500, 10000]ml",
                    )
            updates[db_field] = value

    if not updates:
        return DataWriteResult(
            success=False, target=UpdateTarget.NUTRITION_GOAL,
            message="Không có thông tin mục tiêu để cập nhật",
        )

    await db.execute(
        update(NutritionGoal)
        .where(NutritionGoal.user_id == _user_uuid(user_id))
        .where(NutritionGoal.is_active == True)
        .values(**updates)
    )
    return DataWriteResult(
        success=True, target=UpdateTarget.NUTRITION_GOAL,
        message="Đã cập nhật mục tiêu dinh dưỡng",
        records_updated=1,
    )
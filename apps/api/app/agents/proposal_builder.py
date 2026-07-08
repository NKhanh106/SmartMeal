"""
Proposal builder — converts ExtractorAgent output into UpdateProposals.

Called by ExtractorAgent after extraction completes. Produces proposals
for user confirmation via UpdateProposalCard before any DB write happens.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, date
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.update_proposal import UpdateProposal, UpdateTarget, UpdateField
from app.agents.context_loader import FullUserContext
from app.services.food_mapping_service import (
    calculate_nutrition_per_item,
    match_food_name,
)

logger = logging.getLogger(__name__)


async def _has_pending_proposal_for_target(
    user_id: str,
    target: str,
    description_key: str = "description",
    new_description: str = "",
) -> bool:
    """
    Check if there's already a pending proposal in Redis for the same target.
    Prevents creating duplicate HEALTH_SYMPTOM proposals when user sends
    multiple messages about the same symptom before confirming.

    For HEALTH_SYMPTOM, also checks if the new description shares a token
    with an existing pending proposal's description (catches "tiêu chảy"
    duplicated across turns).
    """
    try:
        from app.core.cache import get_redis
        redis = await get_redis()
        pattern = f"smartmeal:proposal:{user_id}:*"
        keys = []
        async for key in redis.scan_iter(match=pattern, count=100):
            keys.append(key)
        if not keys:
            return False

        import json as _json
        pipe = redis.pipeline(transaction=False)
        for key in keys:
            pipe.get(key)
        results = await pipe.execute()

        from app.schemas.update_proposal import UpdateTarget as _UT
        target_value = target if isinstance(target, str) else target.value

        for raw in results:
            if not raw:
                continue
            try:
                data = _json.loads(raw) if isinstance(raw, str) else raw
                if data.get("target") != target_value:
                    continue
                # For symptom dedup, compare tokens
                if target_value == _UT.HEALTH_SYMPTOM.value and new_description:
                    existing_desc = ""
                    if data.get("raw_data"):
                        existing_desc = data["raw_data"].get(description_key, "")
                    elif data.get("detail"):
                        existing_desc = data["detail"]
                    if existing_desc and _symptom_duplicate_of(
                        new_description,
                        [{"description": existing_desc, "resolved": False}],
                    ):
                        return True
                    # Even if token match fails, any pending HEALTH_SYMPTOM blocks
                    # a new one (only one unresolved symptom popup at a time).
                    return True
                else:
                    return True
            except Exception:
                continue
        return False
    except Exception as e:
        logger.debug("[proposal_builder] Pending proposal check failed (best-effort): %s", e)
        return False

# Mental-health descriptors that should NEVER be turned into a physical-symptom
# proposal — they are either crisis language (handled by HealthMonitor separately)
# or generic distress that doesn't belong on the user's health-symptom timeline.
# Mirrors the same scope used in health_monitor_agent to keep detection and
# proposal filtering in lockstep; if you add a keyword there, add it here too.
_MH_NON_SYMPTOM_KEYWORDS = (
    "tự tử", "muốn chết", "không muốn sống", "muốn tự làm hại",
    "làm hại bản thân", "kết thúc tất cả", "không còn lý do sống",
    "chán nản", "tuyệt vọng", "mất hứng sống", "cuộc sống vô nghĩa",
    "không còn cảm giác", "trầm cảm", "depression",
)


# ── Health-symptom dedup helpers ────────────────────────────────────────────────
# Vietnamese stopwords — too common to be a useful dedup signal.
_VN_STOPWORDS = frozenset({
    "tôi", "mình", "bị", "có", "đang", "và", "là", "thì", "mà", "cho",
    "với", "không", "rồi", "nữa", "ạ", "nhé", "ơi", "đó", "đây", "này",
    "kia", "vậy", "thế", "thôi", "được", "như", "bị", "để", "trong", "trên",
    "nhẹ", "nặng", "vừa", "mới", "cũ", "từ", "sang", "qua", "hôm", "qua",
    "uống", "dùng", "thuốc", "chữa", "trị", "điều", "trị", "kiêng",
})

# Token regex: any run of word chars (Vietnamese diacritics included via \w in
# Unicode mode keeps the same behavior as Python's default str tokens).
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _symptom_tokens(text: str) -> set[str]:
    """Extract meaningful tokens from a symptom description for dedup.

    Drops stopwords, numbers, and tokens shorter than 3 chars so that
    "viêm tai giữa" and "thuốc kháng viêm nhẹ" share the token "viêm" but
    "uống thuốc" alone does not collide with everything.
    """
    if not text:
        return set()
    raw = _TOKEN_RE.findall(text.lower())
    return {t for t in raw if len(t) >= 3 and t not in _VN_STOPWORDS}


def _symptom_duplicate_of(
    new_description: str,
    active_symptoms: list[dict],
) -> bool:
    """True if `new_description` is already represented by an unresolved
    active health_event.

    Two descriptions are considered duplicates when they share at least one
    meaningful token. This catches the common case where the user follows up
    on an already-logged symptom (e.g. "uống thuốc kháng viêm" right after
    confirming "viêm tai giữa") without re-confirming the underlying
    condition.
    """
    new_tokens = _symptom_tokens(new_description)
    if not new_tokens:
        return False
    for ev in active_symptoms or []:
        if ev.get("resolved"):
            continue
        existing = _symptom_tokens(ev.get("description") or "")
        if existing and (new_tokens & existing):
            return True
    return False


async def build_proposals_from_extraction(
    extraction: dict,
    user_message: str,
    session_id: str,
    current_context: FullUserContext | None,
    db: AsyncSession | None = None,
    user_id=None,
) -> list[UpdateProposal]:
    proposals: list[UpdateProposal] = []

    # Me
    meals = extraction.get("meals", [])
    for meal in meals:
        if meal.get("confidence") == "low":
            continue
        raw_items = meal.get("items", [])
        if not raw_items:
            continue

        # ── Resolve calories & food_nutrition_id from DB ─────────────────────────
        # The AI extractor often returns calories=0 because it lacks exact food
        # data. Look up each item in FoodNutrition so the popup and the saved
        # MealLog use real per-100g values instead of LLM guesses.
        enriched_items = []
        total_kcal = 0.0
        item_names = []
        for item in raw_items:
            food_name = item.get("food_name") or item.get("detected_food_name") or ""
            item_names.append(food_name)

            # Weight resolution order (deterministic):
            #  1. LLM-supplied estimated_weight_g (truthful: user said "200g cơm").
            #  2. quantity × default weight-per-unit (truthful: "5 quả trứng" → 250g).
            #  3. quantity × 100g (last-resort fallback for unknown units).
            # This guarantees the popup shows the same kcal for the same message
            # across runs — the prior `or`-chain silently dropped LLM weight
            # because Python's `or` treats any non-zero int as truthy but only
            # when it's a real number; falsy weights from LLM were leaking
            # through, then quantity*100 took over and produced ~700 kcal for
            # "5 quả trứng" instead of the correct ~250g*155=387.
            quantity = float(item.get("quantity") or 1)
            unit = (item.get("unit") or "").strip().lower()
            llm_weight = item.get("estimated_weight_g")
            estimated_weight = _resolve_item_weight(quantity, unit, llm_weight)

            matched_food = None
            food_id = None
            if db is not None and food_name:
                try:
                    match = await match_food_name(
                        db, food_name, user_id=user_id, limit=1
                    )
                    if match.matched_food and match.match_status in ("matched", "partial"):
                        matched_food = match.matched_food
                        food_id = match.matched_food_id
                except Exception:
                    matched_food = None
                    food_id = None

            nutrition = calculate_nutrition_per_item(matched_food, estimated_weight)
            # Prefer DB-calculated kcal; fall back to AI estimate only when no match.
            if matched_food is not None and nutrition["calories"] > 0:
                item_kcal = nutrition["calories"]
            else:
                item_kcal = float(item.get("calories", 0) or 0)
            total_kcal += item_kcal

            enriched_items.append({
                **item,
                "food_name": food_name,
                "detected_food_name": food_name,
                "estimated_weight_g": estimated_weight,
                "food_nutrition_id": str(food_id) if food_id else None,
                "calories": item_kcal,
                "protein_g": nutrition["protein_g"] if matched_food else float(item.get("protein_g", 0) or 0),
                "carb_g": nutrition["carb_g"] if matched_food else float(item.get("carb_g", 0) or 0),
                "fat_g": nutrition["fat_g"] if matched_food else float(item.get("fat_g", 0) or 0),
            })

        meal_type = meal.get("meal_type") or _infer_meal_type()

        meal_type_vn = {
            "breakfast": "Bữa sáng", "bua_sang": "Bữa sáng",
            "lunch": "Bữa trưa", "bua_trua": "Bữa trưa",
            "dinner": "Bữa tối", "bua_toi": "Bữa tối",
            "snack": "Bữa phụ", "an_vat": "Bữa phụ",
        }.get(meal_type, "Bữa ăn")

        # Cross-turn dedup: don't stack meal popups when user mentions the
        # same meal across multiple turns before confirming. Different
        # meal_types (e.g. snack after lunch) are allowed to coexist.
        if user_id and await _has_pending_proposal_for_target(
            str(user_id), UpdateTarget.MEAL_LOG
        ):
            logger.info(
                "[proposal_builder] Skipping duplicate MEAL_LOG proposal "
                "for user %s meal_type=%s — pending proposal already exists",
                user_id, meal_type,
            )
            continue

        proposals.append(UpdateProposal(
            target=UpdateTarget.MEAL_LOG,
            fields=[
                UpdateField(
                    label="Bữa ăn",
                    value=meal_type,
                    unit=None,
                    display=f"{meal_type_vn}: {', '.join(item_names[:3])}"
                ),
                UpdateField(
                    label="Calories",
                    value=total_kcal,
                    unit="kcal",
                    display=f"~{total_kcal:.0f} kcal"
                ),
            ],
            summary=f"Mình vừa ghi nhận {meal_type_vn} của bạn",
            detail=f"{', '.join(item_names[:4])} -- {total_kcal:.0f} kcal",
            confidence=0.9 if meal.get("confidence") == "high" else 0.7,
            raw_data={
                "meal_type": meal_type,
                # Prefer the AI-extracted date (user may say "ăn trưa hôm
                # qua" → AI returns "YYYY-MM-DD"). Fall back to the moment
                # the extractor ran so /today dashboard still groups the
                # entry under today when no date is implied.
                "logged_at": _resolve_logged_at(meal.get("date")),
                "source": "chat_extraction",
                "items": enriched_items,
            },
            source_message=user_message,
            session_id=session_id,
        ))

    # Body weight
    body_state = extraction.get("body_state", {})
    new_weight = body_state.get("weight_kg")
    if new_weight and isinstance(new_weight, (int, float)):
        current_weight = current_context.weight_kg if current_context else None
        if not current_weight or abs(new_weight - current_weight) > 0.1:
            change_str = ""
            if current_weight:
                diff = new_weight - current_weight
                sign = "+" if diff > 0 else ""
                change_str = f" ({sign}{diff:.1f} kg)"

            proposals.append(UpdateProposal(
                target=UpdateTarget.BODY_WEIGHT,
                fields=[
                UpdateField(
                    label="Cân nặng",
                    value=new_weight,
                    unit="kg",
                    display=f"{new_weight} kg{change_str}"
                )
            ],
            summary="Mình vừa ghi nhận cân nặng mới của bạn",
                detail=f"{new_weight} kg{change_str}",
                confidence=0.95,
                raw_data={
                    "weight_kg": new_weight,
                    "measured_at": date.today().isoformat(),
                },
                source_message=user_message,
                session_id=session_id,
            ))

    # Health symptoms
    health_events = extraction.get("health_events", [])
    active_symptoms = (
        current_context.body.active_symptoms
        if (current_context and current_context.body)
        else []
    )
    for event in health_events:
        if event.get("confidence") == "low":
            continue
        if event.get("type") != "symptom":
            continue

        # Skip mental-health descriptions — the proposal UI surfaces the
        # description verbatim as a "tình trạng sức khỏe" update, which
        # produces a confusing pop-up (and pollutes the profile with
        # self-harm text) when the user mentions a crisis keyword in a
        # non-medical context (e.g. quoting past dialogue or health notes).
        description = (event.get("description") or "").lower()
        if any(kw in description for kw in _MH_NON_SYMPTOM_KEYWORDS):
            continue

        # De-duplicate against unresolved symptoms already on the user's
        # profile. Without this check, every follow-up message that re-uses
        # the same condition vocabulary ("đang uống thuốc kháng viêm" after
        # "viêm tai giữa" was already confirmed) re-spawns the
        # UpdateProposalCard popup because the LLM extractor treats each
        # utterance as a fresh health_event.
        if _symptom_duplicate_of(event.get("description", ""), active_symptoms):
            continue

        # Cross-turn dedup: prevent duplicate popup when user sends multiple
        # messages about the same symptom before confirming the existing
        # proposal. Without this, each extraction adds another
        # HEALTH_SYMPTOM proposal in Redis, stacking popups one on top of
        # another in the UI. Memory-based dedup above can't catch this
        # because memory is only updated on confirm.
        if user_id and await _has_pending_proposal_for_target(
            str(user_id),
            UpdateTarget.HEALTH_SYMPTOM,
            description_key="description",
            new_description=event.get("description", ""),
        ):
            logger.info(
                "[proposal_builder] Skipping duplicate HEALTH_SYMPTOM proposal "
                "for user %s — pending proposal already exists for '%s'",
                user_id, event.get("description", "")
            )
            continue

        severity_vn = {
            "mild": "nhẹ", "moderate": "vừa", "severe": "nặng"
        }.get(event.get("severity", "mild"), "nhẹ")

        proposals.append(UpdateProposal(
            target=UpdateTarget.HEALTH_SYMPTOM,
            fields=[
                UpdateField(
                    label="Triệu chứng",
                    value=event.get("description", ""),
                    unit=None,
                    display=f"{event.get('description', '')} [{severity_vn}]"
                )
            ],
            summary="Mình vừa ghi nhận tình trạng sức khỏe của bạn",
            detail=f"{event.get('description', '')} -- mức độ {severity_vn}",
            confidence=0.85,
            raw_data={
                "description": event.get("description", ""),
                "category": event.get("category", "other"),
                "severity": event.get("severity", "mild"),
                "date": date.today().isoformat(),
                "session_id": session_id,
            },
            source_message=user_message,
            session_id=session_id,
        ))

    # Muscle soreness
    fitness_data = extraction.get("fitness", {})
    new_sore = fitness_data.get("new_sore_areas", [])
    if new_sore:
        current_sore = current_context.body.sore_areas if (current_context and current_context.body) else []
        actually_new = [a for a in new_sore if a not in current_sore]

        if actually_new:
            area_vn = {
                "right_arm": "cánh tay phải", "left_arm": "cánh tay trái",
                "lower_back": "lưng dưới", "neck": "cổ",
                "shoulder": "vai", "knee": "đầu gối",
                "leg": "chân", "chest": "ngực",
            }
            areas_display = [area_vn.get(a, a) for a in actually_new]

            # Cross-turn dedup for muscle soreness popups
            if user_id and await _has_pending_proposal_for_target(
                str(user_id), UpdateTarget.MUSCLE_SORENESS
            ):
                logger.info(
                    "[proposal_builder] Skipping duplicate MUSCLE_SORENESS proposal "
                    "for user %s — pending proposal already exists",
                    user_id,
                )
            else:
                proposals.append(UpdateProposal(
                    target=UpdateTarget.MUSCLE_SORENESS,
                    fields=[
                    UpdateField(
                        label="Vùng đau/mỏi",
                        value=actually_new,
                        unit=None,
                        display=f"{', '.join(areas_display)}"
                    )
                ],
                summary="Ghi nhận vùng cơ đang đau/mỏi",
                detail=f"Đau/mỏi: {', '.join(areas_display)}",
                    confidence=0.85,
                    raw_data={
                        "sore_areas": actually_new,
                        "action": "add",
                    },
                    source_message=user_message,
                    session_id=session_id,
                ))

    # Workout completed
    workout_done = fitness_data.get("workout_completed")
    if workout_done:
        # Cross-turn dedup: avoid stacking duplicate workout popups when
        # the user mentions the same workout in follow-up messages
        # (e.g. "tôi tập gym 2 tiếng" + "nên ăn gì" before confirming).
        if user_id and await _has_pending_proposal_for_target(
            str(user_id), UpdateTarget.WORKOUT_LOG
        ):
            logger.info(
                "[proposal_builder] Skipping duplicate WORKOUT_LOG proposal "
                "for user %s — pending proposal already exists",
                user_id,
            )
        else:
            workout_type = fitness_data.get("workout_type", "Tập luyện")
            duration = fitness_data.get("duration_minutes")
            detail = workout_type
            if duration:
                detail += f" {duration} phút"

            proposals.append(UpdateProposal(
                target=UpdateTarget.WORKOUT_LOG,
                fields=[
                    UpdateField(
                        label="Buổi tập",
                        value=workout_type,
                        unit=None,
                        display=detail
                    )
                ],
                summary="Ghi nhận buổi tập hôm nay",
                detail=detail,
                confidence=0.9,
                raw_data={
                    "workout_type": workout_type,
                    "duration_minutes": duration,
                    "date": date.today().isoformat(),
                },
                source_message=user_message,
                session_id=session_id,
            ))

    # Sleep
    sleep_hours = body_state.get("sleep_last_night")
    if sleep_hours and isinstance(sleep_hours, (int, float)):
        # Cross-turn dedup for sleep popups
        if user_id and await _has_pending_proposal_for_target(
            str(user_id), UpdateTarget.SLEEP_LOG
        ):
            logger.info(
                "[proposal_builder] Skipping duplicate SLEEP_LOG proposal "
                "for user %s — pending proposal already exists",
                user_id,
            )
        else:
            proposals.append(UpdateProposal(
                target=UpdateTarget.SLEEP_LOG,
                fields=[
                    UpdateField(
                        label="Giấc ngủ",
                        value=sleep_hours,
                        unit="giờ",
                        display=f"{sleep_hours} giờ"
                    )
                ],
                summary="Ghi nhận giấc ngủ tối qua",
                detail=f"Ngủ {sleep_hours} giờ",
                confidence=0.9,
                raw_data={"hours": sleep_hours},
                source_message=user_message,
                session_id=session_id,
            ))

    return [p for p in proposals if p.confidence >= 0.7]


def _infer_meal_type() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 10:
        return "bua_sang"
    if 10 <= hour < 14:
        return "bua_trua"
    if 17 <= hour < 21:
        return "bua_toi"
    return "an_vat"


def _resolve_logged_at(extracted_date: str | None) -> str:
    """Convert the AI-extracted 'YYYY-MM-DD' date into a full ISO timestamp.

    Returns the current UTC time when the date is missing/blank so the
    MealLog still appears under /today on the dashboard. The current
    *time* is intentionally retained — only the calendar day would shift
    if the AI told us the meal was yesterday/last week.
    """
    now = datetime.utcnow()
    if not extracted_date or not extracted_date.strip():
        return now.isoformat()
    try:
        day = date.fromisoformat(extracted_date.strip())
        # Combine calendar day with current UTC clock time.
        return datetime.combine(day, now.time()).isoformat()
    except ValueError:
        return now.isoformat()


# Default gram weight for one unit when the user counts/portions rather than
# weighing (e.g. "5 quả trứng", "2 bát cơm"). Mirrors the table embedded in
# the ExtractorAgent prompt so behavior is consistent whether the LLM
# estimates or the code falls back here.
_UNIT_DEFAULT_GRAMS: dict[str, float] = {
    "quả": 50.0,      # trứng gà; vịt default 70 (LLM handles special cases)
    "trứng": 50.0,
    "bát": 150.0,     # cơm bát nhỏ
    "chén": 250.0,    # canh
    "tô": 300.0,
    "đĩa": 200.0,
    "phần": 300.0,
    "ổ": 60.0,        # bánh mì
    "lát": 35.0,
    "miếng": 100.0,
    "con": 100.0,     # cá nhỏ
    "khúc": 150.0,
    "ly": 250.0,
    "cốc": 200.0,
    "gói": 80.0,
    "cup": 100.0,
}


def _resolve_item_weight(quantity: float, unit: str, llm_weight) -> float:
    """Pick a deterministic weight for one food item.

    Priority: explicit LLM weight > unit-table × quantity > quantity × 100g.
    Returns grams. The unit-table branch is what fixes the
    "5 quả trứng → 250g → ~387 kcal" case the user reported (was producing
    400/700/1250 depending on the LLM's mood).
    """
    if llm_weight is not None:
        try:
            w = float(llm_weight)
            if w > 0:
                return w
        except (TypeError, ValueError):
            # LLM sometimes emits arithmetic like "6 * 50" into a JSON string
            # despite schema constraints. Parse it with a tiny arithmetic
            # regex rather than eval() to keep this safe and simple.
            import re
            match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)\s*", str(llm_weight))
            if match:
                lhs, op, rhs = match.group(1), match.group(2), match.group(3)
                try:
                    a, b = float(lhs), float(rhs)
                    expr = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if rhs != "0" else 0.0}[op]
                    if expr > 0:
                        return float(expr)
                except Exception:
                    pass
    per_unit = _UNIT_DEFAULT_GRAMS.get(unit)
    if per_unit is not None:
        return quantity * per_unit
    return quantity * 100.0
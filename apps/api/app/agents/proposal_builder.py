"""
Proposal builder — converts ExtractorAgent output into UpdateProposals.

Called by ExtractorAgent after extraction completes. Produces proposals
for user confirmation via UpdateProposalCard before any DB write happens.
"""

from __future__ import annotations

from datetime import datetime, date
from app.schemas.update_proposal import UpdateProposal, UpdateTarget, UpdateField
from app.agents.context_loader import FullUserContext


def build_proposals_from_extraction(
    extraction: dict,
    user_message: str,
    session_id: str,
    current_context: FullUserContext | None,
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

        total_kcal = sum(i.get("calories", 0) for i in raw_items)
        item_names = [i.get("food_name", "") or i.get("detected_food_name", "") for i in raw_items]
        meal_type = meal.get("meal_type") or _infer_meal_type()

        meal_type_vn = {
            "breakfast": "Bua sang", "bua_sang": "Bua sang",
            "lunch": "Bua trua", "bua_trua": "Bua trua",
            "dinner": "Bua toi", "bua_toi": "Bua toi",
            "snack": "Bua phu", "an_vat": "Bua phu",
        }.get(meal_type, "Bua an")

        proposals.append(UpdateProposal(
            target=UpdateTarget.MEAL_LOG,
            fields=[
                UpdateField(
                    label="Bua an",
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
            summary=f"Minh vua ghi nhan {meal_type_vn} cua ban",
            detail=f"{', '.join(item_names[:4])} -- {total_kcal:.0f} kcal",
            confidence=0.9 if meal.get("confidence") == "high" else 0.7,
            raw_data={
                "meal_type": meal_type,
                "logged_at": datetime.utcnow().isoformat(),
                "source": "chat_extraction",
                "items": raw_items,
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
                        label="Can nang",
                        value=new_weight,
                        unit="kg",
                        display=f"{new_weight} kg{change_str}"
                    )
                ],
                summary="Minh vua ghi nhan can nang moi cua ban",
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
    for event in health_events:
        if event.get("confidence") == "low":
            continue
        if event.get("type") != "symptom":
            continue

        severity_vn = {
            "mild": "nhe", "moderate": "vua", "severe": "nang"
        }.get(event.get("severity", "mild"), "nhe")

        proposals.append(UpdateProposal(
            target=UpdateTarget.HEALTH_SYMPTOM,
            fields=[
                UpdateField(
                    label="Trieu chung",
                    value=event.get("description", ""),
                    unit=None,
                    display=f"{event.get('description', '')} [{severity_vn}]"
                )
            ],
            summary="Minh vua ghi nhan tinh trang suc khoe cua ban",
            detail=f"{event.get('description', '')} -- muc do {severity_vn}",
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
                "right_arm": "canh tay phai", "left_arm": "canh tay trai",
                "lower_back": "lung duoi", "neck": "co",
                "shoulder": "vai", "knee": "dau goi",
                "leg": "chan", "chest": "nguc",
            }
            areas_display = [area_vn.get(a, a) for a in actually_new]

            proposals.append(UpdateProposal(
                target=UpdateTarget.MUSCLE_SORENESS,
                fields=[
                    UpdateField(
                        label="Vung dau/moi",
                        value=actually_new,
                        unit=None,
                        display=f"{', '.join(areas_display)}"
                    )
                ],
                summary="Ghi nhan vung co dang dau/moi",
                detail=f"Dau/moi: {', '.join(areas_display)}",
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
        workout_type = fitness_data.get("workout_type", "Tap luyen")
        duration = fitness_data.get("duration_minutes")
        detail = workout_type
        if duration:
            detail += f" {duration} phut"

        proposals.append(UpdateProposal(
            target=UpdateTarget.WORKOUT_LOG,
            fields=[
                UpdateField(
                    label="Buoi tap",
                    value=workout_type,
                    unit=None,
                    display=detail
                )
            ],
            summary="Ghi nhan buoi tap hom nay",
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
        proposals.append(UpdateProposal(
            target=UpdateTarget.SLEEP_LOG,
            fields=[
                UpdateField(
                    label="Giac ngu",
                    value=sleep_hours,
                    unit="gio",
                    display=f"{sleep_hours} gio"
                )
            ],
            summary="Ghi nhan giac ngu toi qua",
            detail=f"Ngu {sleep_hours} gio",
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
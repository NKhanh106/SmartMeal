"""
Service for reading and writing UserMemory.

All agents use this — never write to user_memory directly.

Provides:
- get_or_create_memory  : fetch or create an empty UserMemory record
- apply_memory_updates  : deep-merge AgentResult.memory_updates into the DB record
- get_memory_context_for_agent : return only the memory slices relevant to each agent
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory


# ── Field Ownership Map ───────────────────────────────────────────────────────
# Defines which agent "owns" each sub-field of UserMemory JSONB fields.
# apply_memory_updates enforces: agent can only update its owned fields.
# Orchestrator (agent_name=None) can update any field.

FIELD_OWNERSHIP = {
    "body_snapshot": {
        "weight":            ["extractor"],
        "energy_level":      ["extractor"],
        "sleep_last_night":  ["extractor"],
        "digestion_status":  ["extractor", "health_monitor"],
        "muscle_status":     ["extractor", "health_monitor", "fitness_coach"],
        "hydration":         ["extractor"],
        "current_status":    ["health_monitor"],
    },
    "health_events":  ["extractor", "health_monitor"],
    "nutrition_memory": {
        "recent_meals":         ["extractor"],
        "foods_to_avoid":       ["extractor", "nutrition_advisor"],
        "common_deficiencies":   ["nutrition_advisor"],
        "preferred_foods":      ["extractor"],
    },
    "fitness_memory": {
        "current_restrictions":  ["fitness_coach", "health_monitor"],
        "last_workout_date":     ["extractor"],
        "fitness_level":         ["extractor", "fitness_coach"],
        "preferred_workout_types": ["extractor"],
    },
    "key_facts":             ["extractor"],
    "conversation_summary":  ["extractor"],
}


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, update: dict) -> dict:
    """
    Recursively merge update into base dict.
    - Dicts: merged recursively
    - Lists: caller handles with specific merge logic per field
    - Scalars: update overwrites base
    """
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _confidence_value(confidence: str) -> int:
    """Convert confidence string to numeric value for comparison."""
    mapping = {"high": 3, "medium": 2, "low": 1}
    return mapping.get(str(confidence).lower(), 2)


# ── Read ──────────────────────────────────────────────────────────────────────────

async def get_or_create_memory(
    user_id: int | str,
    db: AsyncSession,
) -> UserMemory:
    """
    Return the existing UserMemory for user_id, or create a blank one.

    Always returns exactly one UserMemory record per user.
    """
    if isinstance(user_id, uuid.UUID):
        user_uuid: uuid.UUID = user_id
    else:
        try:
            user_uuid = uuid.UUID(str(user_id))
        except ValueError:
            user_uuid = uuid.UUID(user_id)

    result = await db.execute(
        select(UserMemory).where(UserMemory.user_id == user_uuid)
    )
    memory = result.scalar_one_or_none()

    if memory is None:
        memory = UserMemory(
            user_id=user_uuid,
            body_snapshot={},
            health_events=[],
            nutrition_memory={},
            fitness_memory={},
            key_facts=[],
            conversation_summary="",
            extraction_version=1,
        )
        db.add(memory)
        await db.flush()

    return memory


async def get_memory_context_for_agent(
    user_id: int | str,
    agent_name: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Return only the memory fields relevant to a specific agent.

    Extractor      → conversation_summary, key_facts
    HealthMonitor  → body_snapshot, health_events, key_facts
    NutritionAdvisor → nutrition_memory, health_events, key_facts, body_snapshot
    FitnessCoach   → fitness_memory, body_snapshot, health_events
    Orchestrator   → all fields (summarized)
    """
    memory = await get_or_create_memory(user_id, db)

    if agent_name == "extractor":
        return {
            "conversation_summary": memory.conversation_summary or "",
            "key_facts": memory.key_facts or [],
        }

    if agent_name == "health_monitor":
        return {
            "body_snapshot": memory.body_snapshot or {},
            "health_events": memory.health_events or [],
            "key_facts": memory.key_facts or [],
        }

    if agent_name == "nutrition_advisor":
        return {
            "nutrition_memory": memory.nutrition_memory or {},
            "health_events": memory.health_events or [],
            "key_facts": memory.key_facts or [],
            "body_snapshot": memory.body_snapshot or {},
        }

    if agent_name == "fitness_coach":
        return {
            "fitness_memory": memory.fitness_memory or {},
            "body_snapshot": memory.body_snapshot or {},
            "health_events": memory.health_events or [],
        }

    if agent_name == "orchestrator":
        return {
            "body_snapshot": memory.body_snapshot or {},
            "health_events": (memory.health_events or [])[:10],
            "nutrition_memory": memory.nutrition_memory or {},
            "fitness_memory": memory.fitness_memory or {},
            "conversation_summary": memory.conversation_summary or "",
            "key_facts": memory.key_facts or [],
        }

    if agent_name == "web_researcher":
        return {
            "key_facts": memory.key_facts or [],
            "nutrition_memory": memory.nutrition_memory or {},
        }

    # Default: return all non-null fields
    return {
        "body_snapshot": memory.body_snapshot or {},
        "health_events": memory.health_events or [],
        "nutrition_memory": memory.nutrition_memory or {},
        "fitness_memory": memory.fitness_memory or {},
        "conversation_summary": memory.conversation_summary or "",
        "key_facts": memory.key_facts or [],
    }


# ── Write ─────────────────────────────────────────────────────────────────────────

async def apply_memory_updates(
    user_id: int | str,
    updates: dict[str, Any],
    db: AsyncSession,
) -> UserMemory:
    """
    Merge updates from AgentResult.memory_updates into the user's UserMemory.

    Merge strategy per field:
    - health_events : prepend new events, keep max 50 (drop oldest when full)
    - key_facts     : upsert by fact text, update confidence if already present
    - recent_meals   : prepend new meals, keep max 30 (dedup by date+meal_type)
    - body_snapshot : deep-merge with additive sore/injury area merging
    - nutrition_memory / fitness_memory : shallow merge of top-level keys
    - conversation_summary : replace if new value is longer
    - scalar fields (last_extraction_at, etc.) : replace
    """
    if isinstance(user_id, uuid.UUID):
        user_uuid: uuid.UUID = user_id
    else:
        try:
            user_uuid = uuid.UUID(str(user_id))
        except ValueError:
            user_uuid = uuid.UUID(user_id)

    memory = await get_or_create_memory(user_uuid, db)

    now = datetime.now(timezone.utc)

    # ── Health Events ───────────────────────────────────────────────────────────
    if "health_events" in updates:
        new_events: list[dict] = updates["health_events"]
        if not isinstance(new_events, list):
            new_events = [new_events]

        existing = list(memory.health_events or [])
        for event in new_events:
            # Ensure each event has a UUID and timestamp
            if "event_id" not in event:
                event["event_id"] = str(uuid.uuid4())
            if "extracted_at" not in event:
                event["extracted_at"] = now.isoformat()

        merged = new_events + existing
        memory.health_events = merged[:50]

    # ── Key Facts ──────────────────────────────────────────────────────────────
    if "key_facts" in updates:
        new_facts: list[dict] = updates["key_facts"]
        if not isinstance(new_facts, list):
            new_facts = [new_facts]

        existing_facts = {(f.get("fact") or ""): f for f in (memory.key_facts or [])}

        for incoming in new_facts:
            fact_text = incoming.get("fact", "")
            if not fact_text:
                continue
            if fact_text in existing_facts:
                # Upsert: keep the higher confidence
                existing = existing_facts[fact_text]
                new_conf = _confidence_value(incoming.get("confidence", "medium"))
                old_conf = _confidence_value(existing.get("confidence", "medium"))
                if new_conf >= old_conf:
                    existing_facts[fact_text] = incoming
            else:
                if "first_seen" not in incoming:
                    incoming["first_seen"] = now.strftime("%Y-%m-%d")
                existing_facts[fact_text] = incoming

        memory.key_facts = list(existing_facts.values())

    # ── Recent Meals ────────────────────────────────────────────────────────────
    if "recent_meals" in updates:
        new_meals: list[dict] = updates["recent_meals"]
        if not isinstance(new_meals, list):
            new_meals = [new_meals]

        nutrition = dict(memory.nutrition_memory or {})
        existing_meals: list[dict] = nutrition.get("recent_meals", [])
        existing_keys: set[tuple[str, str]] = {
            (m.get("date") or "", m.get("meal_type") or "")
            for m in existing_meals
        }

        # Prepend new meals (avoid duplicate date+meal_type)
        for meal in new_meals:
            key = (meal.get("date") or "", meal.get("meal_type") or "")
            if key not in existing_keys:
                existing_meals.insert(0, meal)
                existing_keys.add(key)

        nutrition["recent_meals"] = existing_meals[:30]

        # Recompute avg daily kcal
        if existing_meals:
            kcal_by_date: dict[str, list[int]] = {}
            for m in existing_meals[:30]:
                d = m.get("date", "")
                kcal = m.get("estimated_kcal", 0)
                if d and kcal:
                    kcal_by_date.setdefault(d, []).append(int(kcal))
            if kcal_by_date:
                avg = sum(sum(v) for v in kcal_by_date.values()) / len(kcal_by_date)
                nutrition["avg_daily_kcal_7d"] = round(avg)

        memory.nutrition_memory = nutrition

    # ── Body Snapshot ───────────────────────────────────────────────────────────
    if "body_snapshot" in updates:
        incoming = updates["body_snapshot"]
        existing = memory.body_snapshot or {}

        # Special handling for muscle_status — additive merge for sore/injury areas
        if "muscle_status" in incoming:
            existing_muscle = existing.get("muscle_status", {})
            incoming_muscle = incoming["muscle_status"]

            # Additive merge for sore_areas
            existing_sore = existing_muscle.get("sore_areas", [])
            new_sore = incoming_muscle.get("sore_areas", [])
            merged_sore = list(dict.fromkeys(existing_sore + new_sore))

            # Additive merge for injury_areas
            existing_injuries = existing_muscle.get("injury_areas", [])
            new_injuries = incoming_muscle.get("injury_areas", [])
            merged_injuries = list(dict.fromkeys(existing_injuries + new_injuries))

            incoming_muscle = _deep_merge(existing_muscle, incoming_muscle)
            incoming_muscle["sore_areas"] = merged_sore
            incoming_muscle["injury_areas"] = merged_injuries

        memory.body_snapshot = _deep_merge(existing, incoming)
        memory.body_snapshot["last_updated"] = now.isoformat()

    # ── Nutrition Memory ───────────────────────────────────────────────────────
    if "nutrition_memory" in updates:
        nutrition = dict(memory.nutrition_memory or {})
        nutrition.update(updates["nutrition_memory"])
        memory.nutrition_memory = nutrition

    # ── Fitness Memory ─────────────────────────────────────────────────────────
    if "fitness_memory" in updates:
        fitness = dict(memory.fitness_memory or {})
        fitness.update(updates["fitness_memory"])
        memory.fitness_memory = fitness

    # ── Conversation Summary ───────────────────────────────────────────────────
    if "conversation_summary" in updates:
        new_summary = updates["conversation_summary"] or ""
        current = memory.conversation_summary or ""
        # Replace if new summary is longer (more complete)
        if len(new_summary) >= len(current):
            memory.conversation_summary = new_summary

    # ── Meta ───────────────────────────────────────────────────────────────────
    if "last_extraction_at" in updates:
        memory.last_extraction_at = updates["last_extraction_at"] or now
    else:
        memory.last_extraction_at = now

    memory.extraction_version = (memory.extraction_version or 1) + 1

    await db.flush()
    return memory

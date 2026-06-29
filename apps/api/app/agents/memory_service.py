"""
Service for reading and writing UserMemory.

All agents use this — never write to user_memory directly.

Provides:
- get_or_create_memory  : fetch or create an empty UserMemory record
- apply_memory_updates  : deep-merge AgentResult.memory_updates into the DB record
- get_memory_context_for_agent : return only the memory slices relevant to each agent
- MemoryWriteEngine     : CENTRALIZED write authority — Phase 1 refactor
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory

logger = logging.getLogger(__name__)


# ── Field Ownership Map (HARD — single canonical owner) ────────────────────────
# Each field has EXACTLY ONE authorized writer. All other agents attempting to
# write will have their writes BLOCKED (not silently dropped). MemoryWriteEngine
# (agent_name=None) is the ONLY entity allowed to bypass ownership checks.

MEMORY_OWNERSHIP: dict[str, str] = {
    # Canonical owners — each field has exactly ONE authoritative source
    "body_snapshot":         "health_monitor",
    "health_events":        "health_monitor",
    "nutrition_memory":      "nutrition_advisor",
    "fitness_memory":       "fitness_coach",
    "key_facts":             "extractor",
    "conversation_summary":   "extractor",
    "recent_meals":          "extractor",
}

# Agents that bypass ALL ownership checks (orchestrator, data_writers, MemoryWriteEngine)
SUPER_AGENTS: set[str | None] = {"orchestrator", "data_writer", None}


def _is_field_owned(agent_name: str | None, field_path: str) -> bool:
    """Return True if agent_name is authorized to write field_path."""
    if agent_name in SUPER_AGENTS:
        return True
    owner = MEMORY_OWNERSHIP.get(field_path)
    return owner == agent_name


def _validate_ownership(
    agent_name: str | None,
    updates: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    Filter updates to only fields the agent is allowed to write.
    HARD mode: unauthorized writes are BLOCKED (not silently dropped).

    Returns (authorized_updates, blocked_fields).
    Agents not in SUPER_AGENTS get BLOCKED, not filtered.
    """
    if agent_name in SUPER_AGENTS:
        return updates, []

    authorized: dict[str, Any] = {}
    blocked: list[str] = []

    for field_path, value in updates.items():
        if _is_field_owned(agent_name, field_path):
            authorized[field_path] = value
        else:
            blocked.append(field_path)
            logger.warning(
                "[MemoryWriteEngine] BLOCKED unauthorized write — "
                "agent '%s' attempted to write '%s' (owner: '%s')",
                agent_name, field_path, MEMORY_OWNERSHIP.get(field_path, "unknown"),
            )

    return authorized, blocked


# ── MemoryWriteEngine (CENTRALIZED write authority) ───────────────────────────
#
# RULES:
#   1. ONLY this engine writes to UserMemory (no direct agent writes)
#   2. Each field has exactly ONE canonical owner (see MEMORY_OWNERSHIP above)
#   3. Unauthorized writes are BLOCKED (not silently ignored)
#   4. All Phase 2 agents return memory_proposals in AgentResult.memory_updates
#      and the orchestrator routes them through this engine
#
# Agent → memory_proposal → MemoryWriteEngine.apply() → DB
#                          └── validates ownership
#                          └── merges into UserMemory


class MemoryWriteEngine:
    """
    Centralized memory write authority for Phase 1.
    All memory writes from all agents flow through here.

    Usage:
        engine = MemoryWriteEngine(user_id, session_factory)
        await engine.apply("health_monitor", {"body_snapshot": {...}})
        await engine.commit()
    """

    def __init__(
        self,
        user_id: int | str | uuid.UUID,
        session_factory,
    ) -> None:
        if isinstance(user_id, uuid.UUID):
            self._user_uuid = user_id
        else:
            s = str(user_id)
            try:
                self._user_uuid = uuid.UUID(s)
            except ValueError:
                self._user_uuid = uuid.UUID(user_id)

        self._session_factory = session_factory
        self._pending_updates: dict[str, Any] = {}

    async def apply(
        self,
        agent_name: str | None,
        updates: dict[str, Any],
    ) -> bool:
        """
        Accumulate memory_updates from an agent.
        Validates ownership before accumulating.
        Returns True if all writes were authorized, False if some were blocked.

        NOTE: This does NOT write to DB yet. Call commit() to finalize.
        """
        if not updates:
            return True

        authorized, blocked = _validate_ownership(agent_name, updates)

        if blocked:
            logger.warning(
                "[MemoryWriteEngine] Blocked %d field(s) from '%s': %s",
                len(blocked), agent_name, blocked
            )
            if not authorized:
                return False

        for field, value in authorized.items():
            if field in self._pending_updates:
                self._pending_updates[field] = self._deep_merge_pending(
                    self._pending_updates[field], value
                )
            else:
                self._pending_updates[field] = value

        return len(blocked) == 0

    def _deep_merge_pending(self, existing: Any, incoming: Any) -> Any:
        """Deep-merge incoming value into existing pending value."""
        if isinstance(existing, dict) and isinstance(incoming, dict):
            result = existing.copy()
            for k, v in incoming.items():
                result[k] = self._deep_merge_pending(result.get(k), v)
            return result
        return incoming

    async def commit(self) -> bool:
        """
        Write all accumulated pending updates to DB.
        Creates its own session from session_factory.

        Returns True on success, False on failure.
        """
        if not self._pending_updates:
            return True

        async with self._session_factory() as db:
            try:
                success = await apply_memory_updates(
                    self._user_uuid,
                    self._pending_updates,
                    db,
                    agent_name=None,  # MemoryWriteEngine bypasses ownership check
                )
                if success:
                    await db.commit()
                    logger.info(
                        "[MemoryWriteEngine] Committed %d fields for user %s",
                        len(self._pending_updates), self._user_uuid
                    )
                else:
                    await db.rollback()
                    logger.error(
                        "[MemoryWriteEngine] apply_memory_updates returned False for user %s",
                        self._user_uuid
                    )
                self._pending_updates = {}
                return success
            except Exception as e:
                await db.rollback()
                logger.exception(
                    "[MemoryWriteEngine] Commit failed for user %s: %s",
                    self._user_uuid, e
                )
                self._pending_updates = {}
                return False

    def has_pending(self) -> bool:
        return bool(self._pending_updates)

    async def commit_with_session(self, db: AsyncSession) -> bool:
        """
        Write all accumulated pending updates using an EXISTING session (no commit/rollback).
        Caller manages the transaction boundary — this only flushes.

        Use this when the caller needs atomicity with other DB operations
        (e.g., _mark_session_extracted on the same session).
        """
        if not self._pending_updates:
            return True

        try:
            success = await apply_memory_updates(
                self._user_uuid,
                self._pending_updates,
                db,
                agent_name=None,
            )
            self._pending_updates = {}
            if not success:
                logger.error(
                    "[MemoryWriteEngine] apply_memory_updates returned False for user %s",
                    self._user_uuid
                )
            return success
        except Exception as e:
            logger.exception(
                "[MemoryWriteEngine] commit_with_session failed for user %s: %s",
                self._user_uuid, e
            )
            self._pending_updates = {}
            return False


def memory_write_engine(
    user_id: int | str | uuid.UUID,
    session_factory,
) -> MemoryWriteEngine:
    """
    Factory: create a ready-to-use MemoryWriteEngine for one-shot or
    deferred writes from any call site (ExtractorAgent, HealthMonitorAgent,
    orchestrator Phase 1/2).

    Usage:
        engine = memory_write_engine(user_id, session_factory)
        engine.apply("extractor", {"key_facts": [...], "recent_meals": [...]})
        await engine.commit()
    """
    return MemoryWriteEngine(user_id, session_factory)


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
    elif isinstance(user_id, int):
        user_uuid = uuid.UUID(int=user_id)
    else:
        s = str(user_id)
        try:
            user_uuid = uuid.UUID(s)
        except ValueError:
            raise ValueError(f"Cannot convert {user_id!r} to UUID")

    result = await db.execute(
        # Row-level lock — second writer blocks until first commits/rolls back.
        # Serializes concurrent apply_memory_updates() calls at DB level.
        # For UPDATE only locks EXISTING rows. Missing rows are created in-step
        # with the INSERT below and then immediately returned.
        select(UserMemory).where(UserMemory.user_id == user_uuid).with_for_update()
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

MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.05  # 50ms — short enough for fast retries


class OptimisticLockConflict(Exception):
    """Raised when UserMemory write fails after MAX_RETRIES attempts."""
    pass


async def apply_memory_updates_with_retry(
    user_id: int | str,
    updates: dict[str, Any],
    db: AsyncSession,
    agent_name: str | None = None,
    max_retries: int = MAX_RETRIES,
) -> bool:
    """
    apply_memory_updates with optimistic locking and automatic retry.

    Reads the current extraction_version BEFORE applying updates, then passes it to
    apply_memory_updates. If another writer committed a newer version in between
    (StaleObjectError pattern), apply_memory_updates returns False and we retry
    with the new version.

    Retry loop:
      1. Read memory.extraction_version (no lock held — that's the point)
      2. Pass expected_version to apply_memory_updates
      3. If apply_memory_updates returns True  → success
      4. If it returns False (conflict)       → re-read version, retry
      5. If retries exhausted                → raise OptimisticLockConflict

    The retry window is tiny (~50ms base), so the chance of a third conflict
    is negligible under normal load. With bg_limit=4, concurrent writes to the
    same user's UserMemory are serialized by the Redis queue worker (one extractor
    at a time), so conflicts are extremely rare.

    Raises:
        OptimisticLockConflict: if all retries are exhausted.
    """
    import asyncio
    import random
    from sqlalchemy import select
    from app.models.user_memory import UserMemory

    if isinstance(user_id, uuid.UUID):
        user_uuid: uuid.UUID = user_id
    elif isinstance(user_id, int):
        user_uuid = uuid.UUID(int=user_id)
    else:
        s = str(user_id)
        try:
            user_uuid = uuid.UUID(s)
        except ValueError:
            raise ValueError(f"Cannot convert {user_id!r} to UUID")

    for attempt in range(1, max_retries + 1):
        # Read current version snapshot — no lock, that's intentional
        result = await db.execute(
            select(UserMemory.extraction_version)
            .where(UserMemory.user_id == user_uuid)
        )
        row = result.scalar_one_or_none()
        current_version = row if row is not None else 0

        # Attempt the write with the captured version
        success = await apply_memory_updates(
            user_id=user_uuid,
            updates=updates,
            db=db,
            agent_name=agent_name,
            expected_version=current_version,
        )

        if success:
            return True

        # Conflict: another writer committed between our read and write.
        if attempt < max_retries:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            # Authentic ±30% uniform jitter — prevents synchronized
            # retry storms by spreading contention across time.
            jitter = delay * random.uniform(-0.3, 0.3)
            total_delay = delay + jitter
            logger.debug(
                "UserMemory conflict (attempt %d/%d) for user %s — retrying in %.0fms",
                attempt, max_retries, user_uuid, total_delay * 1000
            )
            await asyncio.sleep(total_delay)

    raise OptimisticLockConflict(
        f"UserMemory write failed after {max_retries} retries for user {user_uuid}"
    )


async def apply_memory_updates(
    user_id: int | str,
    updates: dict[str, Any],
    db: AsyncSession,
    agent_name: str | None = None,
    expected_version: int | None = None,
) -> bool:
    """
    Merge updates from AgentResult.memory_updates into the user's UserMemory.

    Returns True on success, False on conflict (version mismatch when expected_version
    is provided). Callers should decide retry strategy on conflict.

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
    elif isinstance(user_id, int):
        user_uuid = uuid.UUID(int=user_id)
    else:
        s = str(user_id)
        try:
            user_uuid = uuid.UUID(s)
        except ValueError:
            raise ValueError(f"Cannot convert {user_id!r} to UUID")

    memory = await get_or_create_memory(user_uuid, db)

    # ── Optimistic Concurrency: version check ──────────────────────────────────
    if expected_version is not None:
        actual = memory.extraction_version or 1
        if actual != expected_version:
            logger.warning(
                "UserMemory write conflict detected",
                extra={
                    "user_id": str(user_uuid),
                    "agent": agent_name,
                    "expected_version": expected_version,
                    "actual_version": actual,
                },
            )
            return False  # Caller decides retry strategy

    # ── Field ownership validation ────────────────────────────────────────────
    updates = _validate_ownership(agent_name, updates)[0]

    if not updates:
        return True  # nothing to do after filtering

    now = datetime.now(timezone.utc)

    # ── Health Events ───────────────────────────────────────────────────────────
    if "health_events" in updates:
        new_events: list[dict] = updates["health_events"]
        if not isinstance(new_events, list):
            new_events = [new_events]

        existing = list(memory.health_events or [])
        for event in new_events:
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

        for meal in new_meals:
            key = (meal.get("date") or "", meal.get("meal_type") or "")
            if key not in existing_keys:
                existing_meals.insert(0, meal)
                existing_keys.add(key)

        nutrition["recent_meals"] = existing_meals[:30]

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

        if "muscle_status" in incoming:
            existing_muscle = existing.get("muscle_status", {})
            incoming_muscle = incoming["muscle_status"]

            existing_sore = existing_muscle.get("sore_areas", [])
            new_sore = incoming_muscle.get("sore_areas", [])
            merged_sore = list(dict.fromkeys(existing_sore + new_sore))

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

    # ── Conversation Summary ────────────────────────────────────────────────────
    if "conversation_summary" in updates:
        new_summary = updates["conversation_summary"] or ""
        current = memory.conversation_summary or ""
        if len(new_summary) >= len(current):
            memory.conversation_summary = new_summary

    # ── Meta ───────────────────────────────────────────────────────────────────
    if "last_extraction_at" in updates:
        memory.last_extraction_at = updates["last_extraction_at"] or now
    else:
        memory.last_extraction_at = now

    memory.extraction_version = (memory.extraction_version or 1) + 1

    await db.flush()
    return True

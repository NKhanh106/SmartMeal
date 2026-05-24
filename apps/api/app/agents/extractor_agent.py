"""
Agent 1 — Information Extractor.

Runs silently after EVERY user message.
Extracts structured facts from the conversation turn and updates UserMemory.
Never talks to the user directly.

Trigger:
- After every user message (async, non-blocking)
- Also runs on session end to update conversation_summary
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.chat import ChatSession
from app.models.user_memory import UserMemory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a precise medical and nutritional information extractor.
Your job is to read a conversation turn and extract ONLY facts that are
clearly stated or strongly implied. Never infer beyond what's said.
Extract these categories if present:

MEALS: foods eaten, quantities, meal type, time of day
BODY STATE: energy level, sleep, digestion, pain, soreness, illness symptoms
HEALTH EVENTS: new symptoms, illness, recovery, measurements (weight/BP/etc)
FACTS: stable personal facts (allergies, preferences, habits, schedule)
FITNESS: workouts done, injuries, soreness locations, physical state

For each extracted item, assign:
confidence: "high" (explicitly stated) | "medium" (implied) | "low" (guessed)

Return ONLY valid JSON. No explanation. No markdown.
Schema: { meals: [...], body_state: {...}, health_events: [...], facts: [...], fitness: {...} }
If nothing to extract in a category, return empty array/object for that key.

IMPORTANT RULES:
- For body_state: include energy_level, sleep_hours, digestion_status, hydration
- For sore_areas in body_state: include specific body part (e.g. "right_arm", "lower_back", "knees")
- For health_events: include date, type, category, description, severity
- Severity mapping: "hơi", "nhẹ", "một chút" → "mild"; "khá", "vừa" → "moderate"; "rất", "nặng", "nghiêm trọng" → "severe"
- For fitness: include workout_type, duration_min, soreness_areas, injuries
- Foods that caused bad reactions (tiêu chảy, dị ứng, buồn nôn) → include in facts as "food_to_avoid" with reason
"""

EXTRACTION_SCHEMA = """
{
  "meals": [
    {
      "date": "YYYY-MM-DD or empty",
      "meal_type": "breakfast|lunch|dinner|snack|empty",
      "items": ["food item 1", "food item 2"],
      "estimated_kcal": 0,
      "confidence": "high|medium|low"
    }
  ],
  "body_state": {
    "energy_level": "low|normal|high|null",
    "sleep_hours": 0,
    "digestion_status": "normal|bloated|diarrhea|constipated|null",
    "hydration": "low|normal|high|null",
    "sore_areas": ["body_part_1", "body_part_2"],
    "mood": "string or null"
  },
  "health_events": [
    {
      "date": "YYYY-MM-DD or today",
      "type": "symptom|illness|recovery|measurement|note",
      "category": "digestive|muscular|metabolic|respiratory|mental|other",
      "description": "exact or near-exact phrase from user",
      "severity": "mild|moderate|severe"
    }
  ],
  "facts": [
    {
      "fact": "verbatim or summary of the fact",
      "category": "allergy|preference|habit|schedule|food_reaction|other",
      "confidence": "high|medium|low"
    }
  ],
  "fitness": {
    "workout_type": "gym|running|swimming|cycling|yoga|other|null",
    "duration_min": 0,
    "muscle_groups_worked": ["chest", "back", "legs"],
    "new_soreness": ["body_part"],
    "injuries": ["body_part"],
    "fitness_level": "beginner|intermediate|advanced|null"
  }
}
"""


class ExtractorAgent(BaseAgent):
    name = "extractor"

    async def run(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        run = self._log_start(
            context=context,
            trigger="post_user_message",
            input_summary=context.current_message[:200],
            db=db,
        )

        try:
            # 1. Build the extraction prompt from last 2 conversation turns
            extraction_turns = self._build_extraction_context(context.conversation_history)
            user_message = context.current_message

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            user_prompt = f"""Today is {today}.
Extract information from the following user message:

USER MESSAGE:
"{user_message}"

Previous conversation turn (if any):
{extraction_turns}

Return valid JSON following this schema:
{EXTRACTION_SCHEMA}

Rules:
- Only extract what is EXPLICITLY stated or STRONGLY implied. Never guess.
- Use "high" confidence for direct statements, "medium" for strong implications, "low" for guesses
- Map severity words: "hơi/nhẹ/một chút" → mild, "khá/vừa" → moderate, "rất/nặng/nghiêm trọng" → severe
- Foods causing bad reactions (tiêu chảy, dị ứng, buồn nôn) → include in facts with category "food_reaction"
- Do NOT include weight unless user explicitly stated a number
- sore_areas: add new areas, never replace existing list
"""

            # 2. Call AI
            raw_response = await self._call_ai(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_format="json",
                max_tokens=800,
            )

            # 3. Parse JSON safely
            try:
                extracted = raw_response if isinstance(raw_response, dict) else json.loads(raw_response)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("ExtractorAgent: failed to parse JSON: %s. Raw: %s", exc, str(raw_response)[:200])
                await self._log_complete(run, AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="extraction",
                    content={},
                    confidence=0.0,
                    memory_updates={},
                ), db)
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="extraction",
                    content={},
                    confidence=0.0,
                    memory_updates={},
                )

            # 4. Build memory_updates
            memory_updates = self._build_memory_updates(extracted, today, context)

            # 5. Update conversation_summary if session has 5+ messages
            msg_count = len(context.conversation_history) + 1
            if msg_count >= 5:
                summary_text = await self._summarize_session(context, db)
                if summary_text:
                    memory_updates["conversation_summary"] = summary_text

            # 6. Apply updates to DB and mark session — ONLY after successful write
            try:
                await self._update_memory(str(context.user.id), memory_updates, db)
                await self._mark_session_extracted(context.session_id, db)
            except Exception as e:
                logger.error(f"[Extractor] Memory update failed — session will retry: {e}")
                # Do NOT mark as extracted — allow retry on next message
                raise

            await self._log_complete(run, AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="extraction",
                content=extracted,
                confidence=0.8,
                memory_updates=memory_updates,
            ), db)

            return AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="extraction",
                content=extracted,
                confidence=0.8,
                memory_updates=memory_updates,
            )

        except Exception as exc:
            logger.error("ExtractorAgent: unexpected error: %s", exc, exc_info=True)
            await self._log_complete(run, AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="extraction",
                content={},
                confidence=0.0,
                memory_updates={},
                error=str(exc),
            ), db)
            return AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="extraction",
                content={},
                confidence=0.0,
                memory_updates={},
                error=str(exc),
            )

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _build_extraction_context(self, history: list[dict[str, Any]]) -> str:
        """Build context string from last 2 conversation turns."""
        if not history:
            return "(no previous messages in this session)"

        turns = history[-2:] if len(history) >= 2 else history[-1:]
        lines = []
        for turn in turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            lines.append(f"[{role.upper()}]: {content[:300]}")
        return "\n".join(lines)

    def _build_memory_updates(
        self,
        extracted: dict[str, Any],
        today: str,
        context: AgentContext,
    ) -> dict[str, Any]:
        """
        Convert AI extraction output into memory_updates dict.
        Applies the special routing rules:
        - meals → recent_meals
        - body_state → body_snapshot (merge, not replace)
        - health_events → health_events (prepend)
        - facts → key_facts (upsert)
        - fitness → fitness_memory
        - low-confidence items go to key_facts, not body_snapshot
        """
        updates: dict[str, Any] = {}

        # ── Meals ────────────────────────────────────────────────────────────────
        meals = extracted.get("meals") or []
        if meals:
            valid_meals = []
            for meal in meals:
                if not isinstance(meal, dict):
                    continue
                items = meal.get("items") or []
                if not items:
                    continue
                valid_meals.append({
                    "date": meal.get("date") or today,
                    "meal_type": meal.get("meal_type") or "snack",
                    "items": items,
                    "estimated_kcal": meal.get("estimated_kcal") or 0,
                    "confidence": meal.get("confidence", "medium"),
                    "source_session_id": context.session_id,
                })
            if valid_meals:
                updates["recent_meals"] = valid_meals

        # ── Body State ───────────────────────────────────────────────────────────
        body_state = extracted.get("body_state") or {}
        if body_state:
            existing_snapshot = {}
            if context.memory and context.memory.body_snapshot:
                existing_snapshot = dict(context.memory.body_snapshot)

            # Sore areas: ADD new areas, don't replace (unless user says no longer sore)
            new_sore_areas = body_state.get("sore_areas") or []
            if new_sore_areas:
                existing_sore = existing_snapshot.get("sore_areas") or []
                merged_sore = self._merge_sore_areas(existing_sore, new_sore_areas)
                body_state["sore_areas"] = merged_sore

            # Only update weight if explicitly stated (will be handled separately)
            if "weight" in body_state:
                weight_val = body_state.get("weight")
                if isinstance(weight_val, (int, float)):
                    body_state["weight_updated_at"] = today
                else:
                    del body_state["weight"]

            existing_snapshot.update(body_state)
            existing_snapshot["last_updated"] = datetime.now(timezone.utc).isoformat()
            updates["body_snapshot"] = existing_snapshot

        # ── Health Events ───────────────────────────────────────────────────────
        health_events = extracted.get("health_events") or []
        if health_events:
            valid_events = []
            for event in health_events:
                if not isinstance(event, dict):
                    continue
                desc = event.get("description", "")
                if not desc:
                    continue
                valid_events.append({
                    "date": event.get("date") or today,
                    "type": event.get("type", "symptom"),
                    "category": event.get("category", "other"),
                    "description": desc,
                    "severity": event.get("severity", "mild"),
                    "resolved": False,
                    "source_session_id": context.session_id,
                })
            if valid_events:
                updates["health_events"] = valid_events

        # ── Facts (key_facts upsert) ───────────────────────────────────────────
        facts = extracted.get("facts") or []
        if facts:
            valid_facts = []
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                fact_text = fact.get("fact", "")
                if not fact_text:
                    continue
                valid_facts.append({
                    "fact": fact_text,
                    "confidence": fact.get("confidence", "medium"),
                    "category": fact.get("category", "other"),
                    "first_seen": today,
                })
            if valid_facts:
                updates["key_facts"] = valid_facts

        # ── Fitness ─────────────────────────────────────────────────────────────
        fitness = extracted.get("fitness") or {}
        if fitness:
            existing_fitness = {}
            if context.memory and context.memory.fitness_memory:
                existing_fitness = dict(context.memory.fitness_memory)

            # Merge new workout info
            if fitness.get("workout_type"):
                existing_fitness["last_workout_date"] = today
            if fitness.get("new_soreness"):
                existing_sore = existing_fitness.get("current_restrictions", [])
                if not isinstance(existing_sore, list):
                    existing_sore = []
                for area in fitness["new_soreness"]:
                    if not any(r.get("area") == area for r in existing_sore):
                        existing_sore.append({
                            "area": area,
                            "reason": "muscle_soreness",
                            "since": today,
                        })
                existing_fitness["current_restrictions"] = existing_sore
            if fitness.get("workout_type"):
                existing_fitness["preferred_workout_types"] = [fitness["workout_type"]]

            existing_fitness.update({k: v for k, v in fitness.items() if v is not None})
            updates["fitness_memory"] = existing_fitness

        return updates

    def _merge_sore_areas(
        self,
        existing: list[str],
        new: list[str],
    ) -> list[str]:
        """Add new sore areas to existing list without duplicates."""
        result = list(existing)
        for area in new:
            if area not in result:
                result.append(area)
        return result

    async def _summarize_session(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> str | None:
        """Summarize the entire session and append to conversation_summary."""
        history_text = ""
        for turn in context.conversation_history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            history_text += f"\n[{role.upper()}]: {content[:200]}"

        summary_prompt = f"""Summarize the following conversation into a concise summary (max 200 tokens).
Focus on: key facts mentioned, health events, meals, and user goals.
Keep it factual and brief.

Conversation:
{history_text}

[{context.current_message}]

Respond with only the summary text in Vietnamese. No JSON, no explanation."""

        try:
            raw = await self._call_ai(
                system_prompt="You are a conversation summarizer. Summarize briefly in Vietnamese.",
                user_prompt=summary_prompt,
                response_format="text",
                max_tokens=300,
            )
            summary = str(raw).strip()
        except Exception as exc:
            logger.warning("ExtractorAgent: summary failed: %s", exc)
            return None

        if not summary:
            return None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_entry = f"[{today_str}] Session summary: {summary}"

        # Load existing summary and append (max 800 tokens ~ 2000 chars)
        existing = ""
        if context.memory and context.memory.conversation_summary:
            existing = context.memory.conversation_summary

        # Truncate if combined exceeds 800 tokens
        combined = (existing + "\n" + new_entry) if existing else new_entry
        max_chars = 2000
        if len(combined) > max_chars:
            combined = "...[earlier history trimmed]...\n" + combined[-(max_chars - 35):]

        return combined

    async def _mark_session_extracted(self, session_id: str, db: AsyncSession) -> None:
        """Set needs_extraction = False on the current chat session."""
        try:
            await db.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(needs_extraction=False)
            )
            await db.commit()
        except Exception as exc:
            logger.warning("ExtractorAgent: failed to mark session extracted: %s", exc)

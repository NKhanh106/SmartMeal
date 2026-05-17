"""
Agent 4 — Fitness Coach.

Workout recommendations and schedule adjustments based on:
- Fitness memory (fitness level, workout history, restrictions)
- Body snapshot (sore areas, injuries)
- Health Monitor fitness_clearance output
- Active health events (illness, symptoms)

Safety principles:
- Never override rest for severe illness
- Work around sore/injured areas
- Recovery days are productive training days

Trigger:
- When user message contains fitness/exercise keywords
- When body has active health events
"""

import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.memory_service import get_memory_context_for_agent

logger = logging.getLogger(__name__)


class FitnessCoachAgent(BaseAgent):
    name = "fitness_coach"

    async def run(self, context: AgentContext, db: AsyncSession) -> AgentResult:
        run = self._log_start(
            context=context,
            trigger="fitness_keyword_detected",
            input_summary=context.current_message[:200],
            db=db,
        )
        start_time = time.time()

        try:
            # 1. Get fitness memory + body snapshot
            memory_ctx = await get_memory_context_for_agent(
                context.user.id, "fitness_coach", db
            )
            body_snapshot = memory_ctx.get("body_snapshot") or {}
            fitness_memory = memory_ctx.get("fitness_memory") or {}

            # 2. Get health_monitor fitness_clearance (REQUIRED — safety first)
            health_result = getattr(context, "agent_results", {}).get("health")
            fitness_clearance = None
            active_issues = []
            if health_result and health_result.success:
                fitness_clearance = health_result.content.get("fitness_clearance", {})
                active_issues = health_result.content.get("active_issues", [])

            # 3. Determine current restrictions
            muscle_status = body_snapshot.get("muscle_status") or {}
            sore_areas = muscle_status.get("sore_areas", [])
            injury_areas = muscle_status.get("injury_areas", [])
            illness_active = False
            illness_severity = "none"

            # Check health_events for active illness
            health_events = memory_ctx.get("health_events") or []
            for event in health_events:
                if (not event.get("resolved") and
                    event.get("type") == "symptom" and
                    event.get("category") in ("digestive", "respiratory", "metabolic")):
                    illness_active = True
                    illness_severity = event.get("severity", "mild")
                    break

            # 4. Determine workout type based on state
            if illness_active and illness_severity in ("moderate", "severe"):
                forced_type = "rest"
            elif illness_active and illness_severity == "mild":
                forced_type = "light_activity"
            else:
                forced_type = None

            # 5. Build fitness context
            profile = context.profile
            fitness_level = fitness_memory.get("fitness_level", "intermediate")
            preferred_types = fitness_memory.get("preferred_workout_types", ["gym"])
            last_workout = fitness_memory.get("last_workout_date")
            current_plan_id = fitness_memory.get("current_plan_id")

            # 6. Build prompt
            prompt = self._build_prompt(
                user_message=context.current_message,
                fitness_level=fitness_level,
                preferred_types=preferred_types,
                sore_areas=sore_areas,
                injury_areas=injury_areas,
                illness_active=illness_active,
                illness_severity=illness_severity,
                forced_type=forced_type,
                fitness_clearance=fitness_clearance,
                active_issues=active_issues,
                last_workout=last_workout,
                profile=profile,
            )

            # 7. Call AI
            raw = await self._call_ai(
                system_prompt=self._system_prompt(),
                user_prompt=prompt,
                response_format="text",
                max_tokens=800
            )

            # 8. Parse safely
            result_data = self._parse_json_safe(raw)

            # 9. Override if forced_type set (safety — never override rest for severe illness)
            if forced_type == "rest":
                if "workout_recommendation" not in result_data:
                    result_data["workout_recommendation"] = {}
                result_data["workout_recommendation"]["type"] = "rest"
                if "schedule_adjustment" not in result_data:
                    result_data["schedule_adjustment"] = {}
                result_data["schedule_adjustment"]["skip_today"] = True
                result_data["schedule_adjustment"]["reason"] = (
                    f"Đang có triệu chứng {illness_severity} — cần nghỉ ngơi hoàn toàn"
                )

            # 10. Build memory updates
            memory_updates = {}
            if sore_areas:
                memory_updates["fitness_memory"] = {
                    "current_restrictions": [
                        {"area": a, "reason": "muscle_soreness"}
                        for a in sore_areas
                    ]
                }

            latency = int((time.time() - start_time) * 1000)
            agent_result = AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="fitness_recommendation",
                content=result_data,
                confidence=0.85,
                priority=5,
                text_for_orchestrator=result_data.get("user_facing_summary", ""),
                memory_updates=memory_updates,
                suggested_card=None,
                error=None
            )
            await self._log_complete(run, agent_result, db, latency_ms=latency)
            return agent_result

        except Exception as e:
            logger.error(f"FitnessCoachAgent failed: {e}")
            err_result = AgentResult(
                agent_name=self.name, success=False,
                insight_type="fitness_recommendation", content={},
                confidence=0.0, priority=5, text_for_orchestrator="",
                memory_updates={}, suggested_card=None, error=str(e)
            )
            await self._log_complete(run, err_result, db)
            return err_result

    def _system_prompt(self) -> str:
        return """
You are a certified personal trainer with sports medicine knowledge.
You specialize in adaptive fitness programming.

Principles (MUST follow):
1. Safety first — never push through serious illness or injury
2. Adaptive programming — modify around sore/injured areas, don't cancel entirely
3. Recovery is training — rest days are productive
4. Specific context — suggest exercises available in Vietnam (gym, home, park)

When user has illness:
- mild → light walking, gentle stretching only
- moderate/severe → full rest, focus recovery

When user has muscle soreness:
- Work AROUND the sore area
- Suggest antagonist muscle training
- Light blood-flow movement of sore area (no load)

Output ONLY valid JSON. No explanation. No markdown fences.

Schema:
{
  "workout_recommendation": {
    "type": "full_workout|modified|light_activity|rest|recovery",
    "title": "...",
    "duration_minutes": 0,
    "intensity": "low|moderate|high",
    "exercises": [
      {
        "name": "...",
        "sets": null,
        "reps": null,
        "duration_seconds": null,
        "notes": "...",
        "avoid_if": []
      }
    ],
    "avoid_exercises": [{"exercise": "...", "reason": "..."}],
    "recovery_focus": [],
    "motivation": "..."
  },
  "schedule_adjustment": {
    "skip_today": false,
    "reschedule_to": null,
    "reason": null
  },
  "user_facing_summary": "2-3 câu tiếng Việt"
}
"""

    def _build_prompt(self, **kwargs) -> str:
        parts = [f"User message: {kwargs['user_message']}\n"]
        parts.append(f"Fitness level: {kwargs['fitness_level']}")
        parts.append(f"Preferred workout types: {', '.join(kwargs['preferred_types'])}")

        if kwargs["sore_areas"]:
            parts.append(f"SORE AREAS (work around these): {', '.join(kwargs['sore_areas'])}")
        if kwargs["injury_areas"]:
            parts.append(f"INJURED AREAS (avoid completely): {', '.join(kwargs['injury_areas'])}")
        if kwargs["illness_active"]:
            parts.append(f"ACTIVE ILLNESS — severity: {kwargs['illness_severity']}")
        if kwargs["fitness_clearance"]:
            cleared = kwargs["fitness_clearance"].get("cleared_for", [])
            avoid = kwargs["fitness_clearance"].get("avoid", [])
            if cleared:
                parts.append(f"Health monitor cleared for: {', '.join(cleared)}")
            if avoid:
                parts.append(f"Health monitor says avoid: {', '.join(avoid)}")
        if kwargs["forced_type"]:
            parts.append(f"OVERRIDE: workout type must be '{kwargs['forced_type']}'")
        if kwargs["last_workout"]:
            parts.append(f"Last workout: {kwargs['last_workout']}")

        return "\n".join(parts)

    def _verify_recovery_day(self, data: dict) -> dict:
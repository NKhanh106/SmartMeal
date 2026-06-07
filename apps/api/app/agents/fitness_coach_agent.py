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
import re as _re
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.memory_service import get_memory_context_for_agent
from app.agents.output_guardrails import append_medical_disclaimer
from app.agents.prompt_builder import build_fitness_coach_context
from app.agents.safety_matrix import SafetyResult, apply_safety_overrides

logger = logging.getLogger(__name__)


class FitnessCoachAgent(BaseAgent):
    name = "fitness_coach"
    _ctx: AgentContext | None = None

    async def execute(self, context: AgentContext, db: AsyncSession) -> AgentResult:
        self._ctx = context
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
                fitness_result = health_result.content
                fitness_clearance = fitness_result.get("fitness_clearance", {})
                active_issues = fitness_result.get("active_issues", [])

            # 3. Determine current restrictions
            muscle_status = body_snapshot.get("muscle_status") or {}
            sore_areas = muscle_status.get("sore_areas", [])
            injury_areas = muscle_status.get("injury_areas", [])

            # 3.5. Evaluate Injury Safety Matrix — MANDATORY cross-agent safety gate.
            # Runs BEFORE the LLM prompt is built. It blocks dangerous exercises
            # even if the AI model is permissive.
            safety_result = apply_safety_overrides(
                active_issues=active_issues,
                sore_areas=sore_areas,
                injury_areas=injury_areas,
                fitness_clearance=fitness_clearance or {},
            )

            illness_active = False
            illness_severity = "none"

            # 4. Check health_events for active illness
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

            # 5. Demographic safety — pregnancy and elderly override clearance level
            fitness_disclaimer = ""
            pregnancy_mode = False
            demo_flags = getattr(context, "demographic_flags", {})
            if demo_flags.get("is_pregnant"):
                pregnancy_mode = True
                forced_type = "light_activity"
                fitness_disclaimer = (
                    "Người dùng đang MANG THAI. "
                    "Chỉ gợi ý bài tập nhẹ nhàng phù hợp thai kỳ. "
                    "Tham khảo bác sĩ sản khoa trước khi tập."
                )
            elif demo_flags.get("is_breastfeeding"):
                fitness_disclaimer = (
                    "Người dùng đang cho con bú — đảm bảo đủ năng lượng và thời gian nghỉ ngơi."
                )
            elif demo_flags.get("is_minor"):
                fitness_disclaimer = (
                    "Người dùng dưới 18 tuổi — tránh bài tập cường độ cao "
                    "và thiếu giám sát. Ưu tiên bài tập phát triển thể chất cân đối."
                )
            elif demo_flags.get("is_elderly"):
                # Elderly users get light_activity at most. Do NOT override
                # "rest" if illness already forced it — rest has the highest priority.
                if forced_type != "rest":
                    forced_type = "light_activity"
                fitness_disclaimer = (
                    "Người dùng trên 65 tuổi (người cao tuổi). "
                    "BLOCKED: HIIT, nâng tạ nặng, cardio cường độ cao, "
                    "tập cường độ khắc nghiệt, chạy bộ, nhảy, bài tập va chạm cao. "
                    "ALLOWED: Đi bộ nhẹ, Yoga người lớn tuổi, stretching, "
                    "thái cực quyền, tập thở, bơi lội nhẹ nhàng. "
                    "Luôn nhắc: tham khảo ý kiến bác sĩ trước khi tập."
                )

            # 6. Build fitness context
            profile = context.profile
            fitness_level = fitness_memory.get("fitness_level", "intermediate")
            preferred_types = fitness_memory.get("preferred_workout_types", ["gym"])
            last_workout = fitness_memory.get("last_workout_date")
            current_plan_id = fitness_memory.get("current_plan_id")

            # 6. Build prompt (safety result injected into context)
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
                active_goal=context.active_goal,
                full_context=context.full_context,
                safety_result=safety_result,
            )

            # 7. Call AI
            raw = await self._call_ai(
                system_prompt=self._system_prompt(
                    fitness_disclaimer=fitness_disclaimer,
                    pregnancy_mode=pregnancy_mode,
                    is_elderly=bool(demo_flags.get("is_elderly")),
                ),
                user_prompt=prompt,
                response_format="text",
                max_tokens=800
            )

            # 8. Parse safely
            result_data = self._parse_json_safe(raw)

            # 9. Override if forced_type set (safety — never override rest for severe illness)
            if forced_type in ("rest", "light_activity"):
                rec = result_data.get("workout_recommendation", {})

                if forced_type == "rest":
                    rec["type"] = "rest"
                    # Clear ALL exercise data — contradicts rest type
                    rec["exercises"] = []
                    rec["avoid_exercises"] = []
                    rec["duration_minutes"] = 0
                    rec["intensity"] = "none"
                    rec["recovery_focus"] = ["sleep", "hydration", "light_stretching"]
                    rec["motivation"] = (
                        "Hôm nay nghỉ ngơi hoàn toàn là điều cơ thể cần nhất. "
                        "Phục hồi tốt = tập tốt hơn ngày mai"
                    )
                    if "schedule_adjustment" not in result_data:
                        result_data["schedule_adjustment"] = {}
                    result_data["schedule_adjustment"]["skip_today"] = True
                    result_data["schedule_adjustment"]["reason"] = (
                        f"Đang có triệu chứng {illness_severity} — "
                        f"cần nghỉ ngơi hoàn toàn để phục hồi"
                    )

                elif forced_type == "light_activity":
                    # Keep duration but limit intensity and replace heavy exercises
                    rec["intensity"] = "low"
                    rec["duration_minutes"] = min(rec.get("duration_minutes", 30), 20)
                    rec["exercises"] = [
                        ex for ex in rec.get("exercises", [])
                        if ex.get("notes", "").lower() not in ("high", "heavy", "intense")
                    ]
                    if not rec["exercises"]:
                        rec["exercises"] = [
                            {
                                "name": "Đi bộ nhẹ",
                                "sets": None,
                                "reps": None,
                                "duration_seconds": 900,
                                "notes": "Tốc độ thoải mái, thở đều",
                                "avoid_if": []
                            }
                        ]

                result_data["workout_recommendation"] = rec

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

            # Ensure safety overrides are reflected in output even if the LLM didn't respect them
            result_data = self._enforce_safety_result(result_data, safety_result)

            # Append medical disclaimer to fitness output
            user_facing = result_data.get("user_facing_summary", "")
            if user_facing:
                user_facing = append_medical_disclaimer(user_facing, context="fitness")

            agent_result = AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="fitness_recommendation",
                content=result_data,
                confidence=0.85,
                priority=5,
                text_for_orchestrator=user_facing,
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

    def _system_prompt(
        self,
        fitness_disclaimer: str = "",
        pregnancy_mode: bool = False,
        is_elderly: bool = False,
    ) -> str:
        # Pregnancy and elderly disclaimer goes FIRST so it overrides every other instruction.
        extra_safety = ""
        if pregnancy_mode:
            extra_safety = """
╔══════════════════════════════════════════════════════════════╗
║  PREGNANCY MODE — ALL OTHER INSTRUCTIONS SUSPENDED        ║
╠══════════════════════════════════════════════════════════════╣
║  ALLOWED: Đi bộ nhẹ, Yoga thai sản, Bơi lội nhẹ,         ║
║              Stretching nhẹ, Tai chi, Pilates thai kỳ        ║
║  BLOCKED:  HIIT, nâng tạ nặng, burpee, plank sau        ║
║              tuần 16, bài tập nằm ngửa, bơi lội cường độ    ║
║              cao, chạy bộ, nhảy, bài tập va chạm            ║
║  Always remind: consult obstetrician before exercising.      ║
╚══════════════════════════════════════════════════════════════╝

"""
        elif is_elderly:
            extra_safety = """
╔══════════════════════════════════════════════════════════════╗
║  ELDERLY USER MODE — ALL OTHER INSTRUCTIONS SUSPENDED    ║
╠══════════════════════════════════════════════════════════════╣
║  ALLOWED:  Đi bộ nhẹ, Yoga người lớn tuổi, Stretching,  ║
║               Thái cực quyền, Tập thở, Bơi lội nhẹ nhàng    ║
║  BLOCKED:  HIIT, nâng tạ nặng, cardio cường độ cao,      ║
║               chạy bộ, nhảy, bài tập va chạm cao,          ║
║               tập cường độ khắc nghiệt                      ║
║  Always remind: consult doctor before exercising.             ║
╚══════════════════════════════════════════════════════════════╝

"""
        elif fitness_disclaimer:
            extra_safety = f"\n{fitness_disclaimer}\n"

        return extra_safety + """
You are a certified personal trainer with sports medicine knowledge.
You specialize in adaptive fitness programming. SAFETY IS YOUR #1 PRIORITY.

## CORE PRINCIPLES (MUST follow — no exceptions):
1. Safety first — never push through serious illness or injury
2. NEVER include an exercise that has been blocked by the Safety Matrix
3. Adaptive programming — modify around sore/injured areas, don't cancel entirely
4. Recovery is training — rest days are productive
5. Specific context — suggest exercises available in Vietnam (gym, home, park)

## SAFETY OVERRIDE RULES (MANDATORY when safety_overrides_applied=true):
When the system detects musculoskeletal injuries, you MUST:

### Back / Spine injuries (đau lưng, thoát vị đĩa đệm):
- BLOCK: Barbell Squat, Deadlift, Overhead Press, Bent Over Row, Jump Squat
- REPLACE WITH: Leg Press (tựa lưng), Leg Extension, Lying Leg Curl, Romanian Deadlift

### Shoulder / Rotator injuries (đau vai, chấn thương vai):
- BLOCK: Bench Press, Plank, Push-up, Shoulder Press, Burpee
- REPLACE WITH: Incline Dumbbell Press, Knee Push-up, Lateral Raise, Face Pull

### Knee / Ligament injuries (đau gối, dây chằng):
- BLOCK: Jump Squat, Burpee, Lunge nặng, Box Jump, Running
- REPLACE WITH: Goblet Squat, Leg Press, Hip Thrust, Đạp xe, Bơi lội

### Wrist / Hand injuries:
- BLOCK: Push-up, Plank, Bench Press
- REPLACE WITH: Knee Push-up, Wall Push-up, Dumbbell Press ngang ngực, Machine Chest Press

### Hip injuries:
- BLOCK: Deadlift, Lunge, Hip Thrust nặng
- REPLACE WITH: Hip Thrust bodyweight, Glute Bridge, Clamshell, Goblet Squat

### Illness / Fever (cảm sốt):
- BLOCK: Running, HIIT, Burpee, any high-intensity cardio
- REPLACE WITH: Đi bộ nhẹ, Đạp xe chậm, Yoga stretch nhẹ, Thở diaphragmatic

## WORKOUT TYPE DECISION:
- Severe injury/illness → type="rest", no exercises
- Mild soreness or limited clearance → type="light_activity", duration ≤ 20 min, low intensity
- Normal clearance → type="full_workout" or "modified"

Output ONLY valid JSON. No explanation. No markdown fences.

Schema:
{
  "safety_overrides_applied": true,
  "blocked_exercises": ["Barbell Squat", "Deadlift"],
  "alternative_exercises": ["Leg Press (tựa lưng)", "Leg Extension"],
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

        # Inject mandatory safety overrides from the Injury Safety Matrix
        safety_result: SafetyResult | None = kwargs.get("safety_result")
        if safety_result and safety_result.applied:
            parts.append("=== MANDATORY SAFETY OVERRIDE (MUST RESPECT) ===")
            if safety_result.all_blocked:
                parts.append(
                    f"BLOCKED EXERCISES: {', '.join(safety_result.all_blocked_vi)}"
                    f" ({', '.join(safety_result.all_blocked)})"
                )
            if safety_result.all_alternatives:
                parts.append(
                    "SAFE ALTERNATIVES (use these instead): "
                    f"{', '.join(safety_result.all_alternatives)}"
                )
            if safety_result.forced_workout_type:
                parts.append(
                    f"OVERRIDE: workout type must be '{safety_result.forced_workout_type}'"
                )
            parts.append("=== END SAFETY OVERRIDE ===\n")

        # Use rich context when available
        full_ctx = kwargs.get("full_context")
        if full_ctx:
            from app.agents.prompt_builder import build_fitness_coach_context
            parts.append(build_fitness_coach_context(full_ctx))
        else:
            # Legacy path
            profile = kwargs.get("profile")
            if profile:
                gender_val = profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender)
                parts.append(f"DEMOGRAPHICS: Age: {profile.date_of_birth} | Gender: {gender_val} | Height: {profile.height_cm}cm | Weight: {profile.current_weight_kg}kg")

            active_goal = kwargs.get("active_goal")
            if active_goal:
                goal_type = active_goal.goal_type.value if hasattr(active_goal.goal_type, "value") else str(active_goal.goal_type)
                parts.append(f"GOAL: {goal_type} | Daily Target: {active_goal.daily_calorie_target} kcal")

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

    def _enforce_safety_result(
        self,
        result_data: dict[str, Any],
        safety_result: SafetyResult,
    ) -> dict[str, Any]:
        """
        Post-process LLM output to ensure safety overrides are faithfully reflected.
        This is the final line of defense — even if the LLM is permissive,
        we guarantee blocked exercises never appear in the response.

        Matching strategy:
          - Normalize exercise names: strip emoji, strip extra whitespace, lowercase
          - Use regex substring matching: block if ANY blocked keyword
            appears as a word-boundary match inside the exercise name
          - This catches "Squat lưng", "Back Squat", "Barbell Squat nâng cao",
            "Squat", "Gánh tạ" (Deadlift synonym), etc.
        """
        if not safety_result.applied:
            result_data["safety_overrides_applied"] = False
            result_data["blocked_exercises"] = []
            result_data["alternative_exercises"] = []
            return result_data

        result_data["safety_overrides_applied"] = True
        result_data["blocked_exercises"] = safety_result.all_blocked
        result_data["alternative_exercises"] = safety_result.all_alternatives

        # Enforce forced workout type from safety matrix (stricter than illness-only check)
        if safety_result.forced_workout_type:
            forced = safety_result.forced_workout_type
            rec = result_data.get("workout_recommendation", {})
            rec["type"] = forced
            if forced == "rest":
                rec["exercises"] = []
                rec["avoid_exercises"] = []
                rec["duration_minutes"] = 0
                rec["intensity"] = "none"
                rec["recovery_focus"] = ["sleep", "hydration", "light_stretching"]
                rec["motivation"] = (
                    "Hệ thống an toàn đã được kích hoạt. "
                    "Nghỉ ngơi hoàn toàn là cách tốt nhất để phục hồi."
                )
                sched = result_data.get("schedule_adjustment", {})
                sched["skip_today"] = True
                sched["reason"] = "Chấn thương hoặc bệnh lý nghiêm trọng được phát hiện — nghỉ ngơi bắt buộc"
                result_data["schedule_adjustment"] = sched
            result_data["workout_recommendation"] = rec

        # Hard-block any blocked exercises that snuck into the exercise list
        rec = result_data.get("workout_recommendation", {})
        exercises = rec.get("exercises", [])
        if exercises and (safety_result.all_blocked or safety_result.all_blocked_vi):
            blocked_keywords = list(safety_result.all_blocked) + list(safety_result.all_blocked_vi)
            # Compile regex patterns: case-insensitive substring match.
            # We deliberately do NOT use \b word boundaries — Vietnamese diacritics
            # (ư, ơ, ặ, etc.) are non-ASCII word characters and \b fails to match
            # at those boundaries. A plain substring match (re.search with the escaped
            # keyword) catches "Back Squat", "Squat lưng", etc.
            blocked_patterns = [
                _re.compile(_re.escape(kw.lower()), _re.IGNORECASE)
                for kw in blocked_keywords
            ]

            def _exercise_is_blocked(ex: dict[str, Any]) -> bool:
                name_raw = ex.get("name", "")
                # Strip emoji and strip special chars before matching
                name_normalized = _strip_emoji(name_raw).lower().strip()
                for pat in blocked_patterns:
                    if pat.search(name_normalized):
                        return True
                return False

            filtered = [ex for ex in exercises if not _exercise_is_blocked(ex)]
            rec["exercises"] = filtered
            result_data["workout_recommendation"] = rec

        return result_data


def _strip_emoji(text: str) -> str:
    """Remove emoji characters from exercise name before regex matching."""
    emoji_pattern = _re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "]+",
        flags=_re.UNICODE,
    )
    return emoji_pattern.sub("", text)

"""
Agent 2 — Health Monitor.

Medical-focused agent that reads UserMemory and current message to assess
the user's current health state. Outputs structured health assessment.
Runs in parallel with other specialist agents.

Trigger:
- When user message contains health/body keywords
- When body_snapshot has unresolved health events
- When explicitly requested by Orchestrator
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a knowledgeable health and wellness monitor, similar to a
general practitioner doing a preliminary assessment. You are NOT
a doctor and must always recommend consulting a real doctor for
serious conditions.
You have access to the user's health history and current state.
Your job is to:

1. Assess the user's current physical state
2. Identify any concerning patterns or changes
3. Flag anything that needs immediate attention
4. Provide health context to other specialist agents

Guidelines:

- Be conservative: when in doubt, flag for medical consultation
- Distinguish between "monitor closely" vs "see a doctor now"
- Consider interactions between conditions (e.g. diarrhea + dehydration)
- Track trends, not just single data points
- Vietnamese output for user-facing text

Output as JSON only with this exact schema."""

ASSESSMENT_SCHEMA = """
{
  "current_status": {
    "overall": "good|monitor|concerning|urgent",
    "energy": "low|normal|high",
    "digestion": "normal|mild_issue|issue",
    "musculoskeletal": "normal|sore|injured",
    "metabolic": "normal|watch|concern"
  },
  "active_issues": [
    {
      "issue": "short name in Vietnamese",
      "since": "YYYY-MM-DD or today",
      "severity": "mild|moderate|severe",
      "recommendation": "plain Vietnamese advice",
      "dietary_restriction": ["list of restriction codes"],
      "fitness_restriction": ["list of restriction codes"],
      "see_doctor_if": "condition for escalation"
    }
  ],
  "nutritional_needs": {
    "increase": ["electrolytes", "probiotics", "water"],
    "decrease": ["fat", "fiber", "spicy"],
    "avoid": ["dairy", "spicy", "high_fat"]
  },
  "fitness_clearance": {
    "cleared_for": ["light_walk", "stretching", "no_exercise"],
    "avoid": ["high_intensity", "heavy_lifting", "core_exercises"],
    "reason": "plain Vietnamese reason"
  },
  "alerts": ["urgent alert messages in Vietnamese"],
  "user_facing_note": "1-2 sentences in Vietnamese for orchestrator to optionally include"
}
"""

URGENT_KEYWORDS = [
    "đau ngực",
    "khó thở",
    "ngất",
    "co giật",
    "nôn ra máu",
    "đi ngoài ra máu",
    "đau đầu dữ dội",
    "mờ mắt",
]


class HealthMonitorAgent(BaseAgent):
    name = "health_monitor"

    async def run(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        run = self._log_start(
            context=context,
            trigger="health_keyword_detected",
            input_summary=context.current_message[:200],
            db=db,
        )

        try:
            # ── 1. Urgent keyword check (rule-based, before AI call) ─────────────
            msg_lower = context.current_message.lower()
            if any(kw in msg_lower for kw in URGENT_KEYWORDS):
                alert_text = "⚠️ URGENT: User reports serious symptoms. Recommend immediate medical attention."
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="health_status",
                    content={
                        "alerts": ["URGENT: Triệu chứng nghiêm trọng — cần gặp bác sĩ ngay"],
                        "current_status": {
                            "overall": "urgent",
                            "energy": "unknown",
                            "digestion": "unknown",
                            "musculoskeletal": "unknown",
                            "metabolic": "unknown",
                        },
                        "active_issues": [],
                        "nutritional_needs": {},
                        "fitness_clearance": {
                            "cleared_for": ["no_exercise"],
                            "avoid": [],
                            "reason": "Có triệu chứng cấp cứu — không tập luyện",
                        },
                        "user_facing_note": "⚠️ Tôi khuyến cáo bạn nên gặp bác sĩ ngay lập tức cho các triệu chứng này.",
                    },
                    confidence=1.0,
                    priority=1,
                    text_for_orchestrator=alert_text,
                    memory_updates={},
                )
                await self._log_complete(run, result, db)
                return result

            # ── 2. Load health-relevant memory ────────────────────────────────────
            memory = context.memory
            body_snapshot = memory.body_snapshot if memory else {}
            health_events = memory.health_events if memory else []
            key_facts = memory.key_facts if memory else []
            profile = context.profile

            # Filter events to last 7 days
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_events = [
                e for e in health_events
                if self._event_is_recent(e, seven_days_ago)
            ]

            # ── 3. Build health context string (max 500 tokens) ─────────────────
            health_context = self._build_health_context(
                body_snapshot=body_snapshot,
                recent_events=recent_events,
                key_facts=key_facts,
                profile=profile,
            )

            # ── 4. Call AI with health context ──────────────────────────────────
            user_prompt = f"""User's current message: "{context.current_message}"

Health context (last 7 days):
{health_context}

Assess the user's health state based on the above context and the current message.
Return ONLY valid JSON following this exact schema:
{ASSESSMENT_SCHEMA}

If there are no active health issues, return:
{{"current_status": {{"overall": "good", "energy": "normal", "digestion": "normal", "musculoskeletal": "normal", "metabolic": "normal"}}, "active_issues": [], "nutritional_needs": {{"increase": [], "decrease": [], "avoid": []}}, "fitness_clearance": {{"cleared_for": ["normal_activity"], "avoid": [], "reason": "Không có hạn chế"}}, "alerts": [], "user_facing_note": ""}}
"""

            try:
                raw_response = await self._call_ai(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_format="json",
                    max_tokens=800,
                )
                assessment = raw_response if isinstance(raw_response, dict) else {}
            except Exception as exc:
                logger.warning("HealthMonitorAgent: AI call failed: %s", exc)
                assessment = {}

            # ── 5. Build memory_updates ──────────────────────────────────────────
            memory = context.memory
            memory_updates = self._build_memory_updates(assessment, body_snapshot, memory)

            if memory_updates:
                await self._update_memory(str(context.user.id), memory_updates, db)

            # ── 6. Build text_for_orchestrator ──────────────────────────────────
            user_facing = assessment.get("user_facing_note", "")
            alerts = assessment.get("alerts") or []
            current_status = assessment.get("current_status", {})
            overall = current_status.get("overall", "good")

            if alerts:
                text_parts = [f"[Health Alert] {a}" for a in alerts]
                if user_facing:
                    text_parts.append(user_facing)
                text_for_orch = " ".join(text_parts)
            elif overall == "good":
                text_for_orch = ""
            elif overall in ("monitor", "concerning"):
                text_for_orch = user_facing or f"[Health Monitor] Trạng thái sức khỏe: {overall}"
            else:
                text_for_orch = f"[Health] {user_facing}" if user_facing else ""

            priority = self._status_to_priority(overall)

            result = AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="health_status",
                content=assessment,
                confidence=0.8,
                priority=priority,
                text_for_orchestrator=text_for_orch,
                memory_updates=memory_updates,
            )
            await self._log_complete(run, result, db)
            return result

        except Exception as exc:
            logger.error("HealthMonitorAgent: unexpected error: %s", exc, exc_info=True)
            await self._log_complete(run, AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="health_status",
                content={},
                confidence=0.0,
                priority=5,
                memory_updates={},
                error=str(exc),
            ), db)
            return AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="health_status",
                content={},
                confidence=0.0,
                priority=5,
                memory_updates={},
                error=str(exc),
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _event_is_recent(self, event: dict, cutoff: datetime) -> bool:
        """Return True if event date is within the cutoff window."""
        try:
            date_str = event.get("date", "")
            if not date_str:
                return True
            event_date = datetime.strptime(str(date_str), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return event_date >= cutoff
        except (ValueError, TypeError):
            return True

    def _build_health_context(
        self,
        body_snapshot: dict,
        recent_events: list[dict],
        key_facts: list[dict],
        profile: Any,
    ) -> str:
        """Build a concise health context string (max ~500 tokens)."""
        parts = []

        # Body snapshot
        if body_snapshot:
            snapshot_parts = []
            if body_snapshot.get("energy_level"):
                snapshot_parts.append(f"- Mức năng lượng: {body_snapshot['energy_level']}")
            if body_snapshot.get("sleep_last_night"):
                snapshot_parts.append(f"- Giấc ngủ: {body_snapshot['sleep_last_night']} giờ")
            if body_snapshot.get("digestion_status"):
                snapshot_parts.append(f"- Tiêu hóa: {body_snapshot['digestion_status']}")
            if body_snapshot.get("sore_areas"):
                parts_str = ", ".join(body_snapshot["sore_areas"])
                snapshot_parts.append(f"- Vùng đau nhức: {parts_str}")
            if snapshot_parts:
                parts.append("BODY SNAPSHOT:\n" + "\n".join(snapshot_parts))

        # Recent health events
        if recent_events:
            event_parts = []
            for e in recent_events[:10]:
                severity = e.get("severity", "")
                desc = e.get("description", "")
                event_parts.append(f"- [{severity.upper()}] {desc}")
            parts.append("RECENT HEALTH EVENTS (7 ngày):\n" + "\n".join(event_parts))

        # Key facts (health-related)
        health_facts = [
            f for f in key_facts
            if f.get("category") in ("allergy", "food_reaction", "habit")
        ]
        if health_facts:
            fact_parts = [f"- {f.get('fact', '')}" for f in health_facts[:5]]
            parts.append("KEY FACTS:\n" + "\n".join(fact_parts))

        # Profile health conditions
        if profile and hasattr(profile, "health_conditions"):
            conditions = profile.health_conditions
            if conditions:
                cond_parts = [f"- {c.get('condition', '')}" for c in conditions]
                parts.append("CHRONIC CONDITIONS:\n" + "\n".join(cond_parts))

        result = "\n\n".join(parts) if parts else "(Không có dữ liệu sức khỏe)"
        # Rough token estimate: 1 token ≈ 4 chars; 500 tokens ≈ 2000 chars
        if len(result) > 2000:
            result = result[:2000]
        return result

    def _build_memory_updates(
        self,
        assessment: dict[str, Any],
        existing_snapshot: dict,
        memory: Any,
    ) -> dict[str, Any]:
        """Update body_snapshot from assessment.current_status fields."""
        updates: dict[str, Any] = {}
        current_status = assessment.get("current_status") or {}
        if not current_status:
            return updates

        new_snapshot = dict(existing_snapshot)

        if "energy" in current_status:
            new_snapshot["energy_level"] = current_status["energy"]
        if "digestion" in current_status:
            mapping = {
                "normal": "normal",
                "mild_issue": "bloated",
                "issue": "diarrhea",
            }
            new_snapshot["digestion_status"] = mapping.get(
                current_status["digestion"], current_status["digestion"]
            )
        if "musculoskeletal" in current_status:
            if current_status["musculoskeletal"] == "injured":
                new_snapshot["muscle_status"] = dict(
                    existing_snapshot.get("muscle_status", {})
                )
                new_snapshot["muscle_status"]["injury_areas"] = (
                    existing_snapshot.get("muscle_status", {})
                    .get("injury_areas", [])
                )

        new_snapshot["last_updated"] = datetime.now(timezone.utc).isoformat()
        updates["body_snapshot"] = new_snapshot

        # If user mentions recovery, mark events resolved in memory and persist
        active_issues = assessment.get("active_issues") or []
        if active_issues:
            existing_events = list(memory.health_events or []) if memory else []
            resolved_any = False
            for issue in active_issues:
                desc = issue.get("issue", "")
                if any(kw in desc.lower() for kw in ["khỏi", "hết", "đỡ", "bình thường"]):
                    resolved_event_id = issue.get("event_id")
                    if resolved_event_id:
                        updated_events = []
                        for event in existing_events:
                            if event.get("event_id") == resolved_event_id:
                                updated_events.append({**event, "resolved": True})
                                resolved_any = True
                            else:
                                updated_events.append(event)
                        existing_events = updated_events

            if resolved_any:
                updates["health_events"] = existing_events

        return updates

    def _status_to_priority(self, overall: str) -> int:
        """Map overall status string to numeric priority."""
        mapping = {
            "urgent": 1,
            "concerning": 3,
            "monitor": 5,
            "good": 7,
        }
        return mapping.get(overall, 5)

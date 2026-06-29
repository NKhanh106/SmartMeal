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
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.output_guardrails import append_medical_disclaimer
from app.agents.prompt_builder import build_health_monitor_context
from app.schemas.chat_card import ChatCard

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

# Regex pattern covering both correct spelling and common typo:
# "méo miệng" (correct) and "mêo miệng" (common typo).
# Compiled once at module level for efficiency.
STROKE_FACE_PATTERN = re.compile(r"m[eé]o\s*miệng", re.IGNORECASE)

URGENT_KEYWORDS = [
    # ── Cardiac ─────────────────────────────────────────────────
    "đau ngực",
    "đau thắt ngực",
    "đau lan lên vai",
    "tim đập loạn",
    "tim ngừng",
    "ngất xỉu",

    # ── Respiratory ─────────────────────────────────────────────
    "khó thở",
    "không thở được",
    "ngạt thở",
    "thở gấp dữ dội",

    # ── Stroke — WHO F.A.S.T. ────────────────────────────────────
    "tê bì một bên",
    "tê liệt một bên",
    "yếu một bên",
    # "méo miệng" handled by STROKE_FACE_PATTERN below
    "nói ngọng",
    "nói khó",
    "nói không ra",
    "đột ngột mất thăng bằng",
    "mờ mắt",
    "mất thị lực đột ngột",

    # ── Anaphylaxis ──────────────────────────────────────────────
    "sưng môi",
    "sưng lưỡi",
    "sưng cổ họng",
    "phát ban toàn thân",
    "nổi mề đay khắp người",

    # ── Neurological / Other ─────────────────────────────────────
    "co giật",
    "ngất",
    "đau đầu dữ dội",
    "đau đầu như búa bổ",
    "nôn ra máu",
    "đi ngoài ra máu",
    "xuất huyết",

    # ── Gastrointestinal emergency ───────────────────────────────
    "đau bụng dữ dội",
    "bụng cứng đau",
]


def _stroke_face_detected(message: str) -> bool:
    """Return True if message contains 'méo/mêo miệng' (stroke face sign).

    The regex tolerates the common 'mêo' typo. Negation and third-person
    checks are the caller's responsibility.
    """
    clean_msg = message.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    clean_msg = re.sub(r'\s+', ' ', clean_msg)
    return bool(STROKE_FACE_PATTERN.search(clean_msg))


# Crisis keywords — any match triggers immediate escalation with no nutrition advice
MENTAL_HEALTH_CRISIS_KEYWORDS = [
    # Vietnamese self-harm intent
    "tự tử",
    "muốn chết",
    "không muốn sống",
    "muốn tự làm hại",
    "làm hại bản thân",
    "kết thúc tất cả",
    "không còn lý do sống",
    # English fallback
    "want to die",
    "kill myself",
    "end my life",
    "self harm",
]

# Distress keywords — acknowledge and flag for empathetic synthesis, not escalation alone
MENTAL_HEALTH_CONCERN_KEYWORDS = [
    "chán nản",
    "tuyệt vọng",
    "không muốn ăn gì",
    "mất hứng sống",
    "cuộc sống vô nghĩa",
    "không còn cảm giác",
    "lo âu nặng",
    "trầm cảm",
    "depression",
    "anxiety",
]

# Negation patterns supporting no-space variants and zero-width unicode tricks.
# Each pattern uses \s* (zero-or-more whitespace) so "khôngbị" and "không bị" both match.
NEGATION_PATTERNS = [
    r"không\s*bị",
    r"không\s+có",
    r"chưa\s+bị",
    r"hết\s+rồi",
    r"không\s+còn",
    r"đã\s+khỏi",
    r"bình\s+thường",
    r"không\s+đau",
    r"đâu\s+bị",
]


def _is_negated(keyword: str, message: str) -> bool:
    """Check if keyword appears in a negated context."""
    clean_msg = message.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    clean_msg = re.sub(r'\s+', ' ', clean_msg)
    pos = clean_msg.lower().find(keyword.lower())
    if pos == -1:
        return False
    context_window = clean_msg[max(0, pos - 30):pos]
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, context_window, re.IGNORECASE):
            return True
    return False


def _is_third_person_report(msg: str, keyword: str) -> bool:
    """Return True if keyword appears in a third-person report context.

    Prevents false-urgent alerts when the user describes another person's symptoms.
    """
    idx = msg.lower().find(keyword.lower())
    if idx == -1:
        return False
    window = msg[max(0, idx - 30):idx].lower()
    third_person_indicators = [
        "người khác", "bạn của", "người nhà", "ai đó",
        "họ", "vợ tôi", "chồng tôi", "con tôi",
        "mẹ tôi", "bố tôi", "anh tôi", "chị tôi",
    ]
    return any(indicator in window for indicator in third_person_indicators)


def _check_mental_health_crisis(message: str) -> tuple[bool, bool]:
    """
    Returns (is_crisis, is_concern).

    is_crisis  = True  if any CRISIS keyword is found  → escalate immediately
    is_concern = True  if any CONCERN keyword is found  → acknowledge, not block
    Crisis takes priority: if crisis=True, concern is always False.
    """
    msg_lower = message.lower()

    is_crisis = any(kw in msg_lower for kw in MENTAL_HEALTH_CRISIS_KEYWORDS)
    if is_crisis:
        return True, False

    is_concern = any(kw in msg_lower for kw in MENTAL_HEALTH_CONCERN_KEYWORDS)
    return False, is_concern


class HealthMonitorAgent(BaseAgent):
    name = "health_monitor"
    _ctx: AgentContext | None = None
    _mh_concern_flag: bool = False

    async def execute(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        self._ctx = context
        self._mh_concern_flag = False
        run = self._log_start(
            context=context,
            trigger="health_keyword_detected",
            input_summary=context.current_message[:200],
            db=db,
        )

        try:
            # Mental health crisis check — HIGHEST PRIORITY, runs before any other logic
            is_mh_crisis, is_mh_concern = _check_mental_health_crisis(context.current_message)

            if is_mh_crisis:
                logger.warning(
                    "[HealthMonitor] Mental health crisis keyword detected. "
                    f"Message preview: {context.current_message[:60]}"
                )
                crisis_card = ChatCard(
                    card_id=f"mh_crisis_{run.id}",
                    card_type="CONFIRM",
                    title="Bạn không cô đơn trong điều này",
                    subtitle=(
                        "Tôi thấy bạn đang trải qua điều rất khó khăn. "
                        "Bạn có muốn nói chuyện với chuyên gia tâm lý không? "
                        "Đường dây hỗ trợ sức khỏe tâm thần 24/7: "
                        "0963 061 414 (Ngày Mai, miễn phí), "
                        "0909 658 035 / 0784 604 598 (Chăm sóc Sức khỏe Việt), "
                        "024 3576 5344 (Viện Tâm thần Quốc gia)."
                    ),
                    trigger_reason="mental_health_crisis",
                    skippable=False,
                )
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="health_status",
                    content={
                        "current_status": {"overall": "urgent"},
                        "active_issues": [{
                            "issue": "mental_health_crisis",
                            "severity": "severe",
                            "see_doctor_if": "Cảm giác này kéo dài hoặc trở nên tồi tệ hơn"
                        }],
                        "fitness_clearance": {
                            "cleared_for": [],
                            "avoid": ["all_exercise"],
                            "reason": "Cần hỗ trợ tâm lý trước"
                        },
                        "nutritional_needs": {"increase": [], "decrease": [], "avoid": []},
                        "alerts": [{
                            "level": "urgent",
                            "message": (
                                "Phát hiện dấu hiệu khủng hoảng tâm lý. "
                                "Đường dây hỗ trợ: 0963 061 414 (Ngày Mai, 24/7, miễn phí), "
                                "0909 658 035 / 0784 604 598 (Chăm sóc Sức khỏe Việt), "
                                "024 3576 5344 (Viện Tâm thần Quốc gia)."
                            )
                        }],
                    },
                    priority=1,
                    confidence=1.0,
                    suggested_card=crisis_card,
                    text_for_orchestrator=(
                        "MH CRISIS DETECTED. "
                        "Do NOT provide nutrition or fitness advice. "
                        "User needs emotional support and professional help. "
                        "Crisis hotline: 0963 061 414 (Ngay Mai, 24/7), "
                        "0909 658 035 (Cham soc Suc khoe Viet)."
                    ),
                    memory_updates={},
                )
                await self._log_complete(run, result, db)
                return result

            if is_mh_concern:
                # Set flag so orchestrator injects empathetic preamble into synthesis.
                # Does NOT return early — execution continues through normal health flow.
                self._mh_concern_flag = True
                logger.info(
                    "[HealthMonitor] Mental health concern keyword detected. "
                    "Flagging for empathetic synthesis."
                )

            # ── 1. Urgent keyword check (rule-based, before AI call) ─────────────
            # Stroke face-paralysis keyword is piped through the same negation and
            # third-person gates as the rest of URGENT_KEYWORDS.
            _face_kw = "méo miệng"
            urgent_keywords_found = [
                kw for kw in URGENT_KEYWORDS
                if kw in context.current_message.lower()
                and not _is_negated(kw, context.current_message)
                and not _is_third_person_report(context.current_message, kw)
            ]
            # Regex check for both correct + typo spelling of the stroke face sign
            # (WHO F.A.S.T. — F = Face).
            if _stroke_face_detected(context.current_message) \
                    and not _is_negated(_face_kw, context.current_message) \
                    and not _is_third_person_report(context.current_message, _face_kw):
                urgent_keywords_found.append(_face_kw)
            if urgent_keywords_found:
                logger.warning(
                    "[HealthMonitor] URGENT keywords detected",
                    extra={
                        "keywords": urgent_keywords_found,
                        "message_length": len(context.current_message),
                        "user_id": str(context.user.id),
                        "depth_mode": str(context.depth_config.mode
                                          if context.depth_config else "unknown"),
                    }
                )
                alert_text = f"⚠️ URGENT: User reports serious symptoms: {urgent_keywords_found}. Recommend immediate medical attention."
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="health_status",
                    content={
                        "current_status": {"overall": "urgent"},
                        "alerts": [
                            f"⚠️ Triệu chứng nghiêm trọng phát hiện: {', '.join(urgent_keywords_found)}. "
                            f"Vui lòng gặp bác sĩ ngay lập tức."
                        ],
                        "active_issues": [],
                        "nutritional_needs": {"increase": [], "decrease": [], "avoid": []},
                        "fitness_clearance": {
                            "cleared_for": [],
                            "avoid": ["all_exercise"],
                            "reason": "Triệu chứng khẩn cấp — cần nghỉ ngơi hoàn toàn"
                        },
                        "user_facing_note": (
                            "Mình nhận thấy bạn đang có triệu chứng đáng lo ngại. "
                            "Hãy gặp bác sĩ hoặc đến cơ sở y tế ngay nhé."
                        )
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
            memory_updates = self._build_memory_updates(assessment, body_snapshot, memory)
            # Memory writes are centralized in the orchestrator. Do NOT call
            # self._update_memory() here — return memory_updates in AgentResult
            # and let the orchestrator write via MemoryWriteEngine for
            # deterministic, ownership-validated writes.

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

            # Always append medical disclaimer
            if text_for_orch:
                text_for_orch = append_medical_disclaimer(text_for_orch, context="health")

            priority = self._status_to_priority(overall)

            # If concern flag was set, prepend empathetic preamble to synthesis text
            if getattr(self, "_mh_concern_flag", False):
                mh_preamble = (
                    "[MH CONCERN DETECTED] "
                    "Acknowledge the user's emotional distress FIRST (2-3 warm, empathetic sentences). "
                    "Then suggest talking to a trusted person or mental health professional. "
                    "Remind them that mood affecting appetite is normal and temporary. "
                )
                text_for_orch = mh_preamble + " " + text_for_orch if text_for_orch else mh_preamble

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
        if self._ctx and self._ctx.full_context:
            return build_health_monitor_context(self._ctx.full_context)

        # Legacy path — preserves exact existing behavior
        parts = []

        # Demographics
        if profile:
            gender_val = profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender)
            parts.append(f"DEMOGRAPHICS:\nDOB: {profile.date_of_birth} | Gender: {gender_val} | Height: {profile.height_cm}cm | Weight: {profile.current_weight_kg}kg")

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

        # Record ACTUAL injury/soreness data from active_issues
        active_issues = assessment.get("active_issues") or []
        if current_status.get("musculoskeletal") in ("injured", "sore"):
            existing_muscle = existing_snapshot.get("muscle_status", {})
            existing_injuries = existing_muscle.get("injury_areas", [])
            existing_sore = existing_muscle.get("sore_areas", [])

            new_injuries = []
            new_sore = []

            AREA_KEYWORDS = {
                "tay phải": "right_arm",
                "tay trái": "left_arm",
                "vai": "shoulder",
                "lưng": "lower_back",
                "cổ": "neck",
                "đầu gối": "knee",
                "chân": "leg",
                "hông": "hip",
                "bụng": "abdomen",
                "ngực": "chest",
            }

            for issue in active_issues:
                combined = (issue.get("issue", "") + " " + issue.get("description", "")).lower()
                area = next(
                    (v for k, v in AREA_KEYWORDS.items() if k in combined),
                    "general"
                )
                severity = issue.get("severity", "mild")
                if severity == "severe" or "chấn thương" in combined:
                    if area not in existing_injuries:
                        new_injuries.append(area)
                else:
                    if area not in existing_sore:
                        new_sore.append(area)

            new_snapshot["muscle_status"] = {
                **existing_muscle,
                "injury_areas": list(set(existing_injuries + new_injuries)),
                "sore_areas": list(set(existing_sore + new_sore)),
            }

        new_snapshot["last_updated"] = datetime.now(timezone.utc).isoformat()
        updates["body_snapshot"] = new_snapshot

        # Recovery event resolution — mark health events resolved when AI reports recovery
        if active_issues:
            existing_events = list(memory.health_events or []) if memory else []
            resolved_events = self._resolve_matching_health_events(active_issues, existing_events)
            if resolved_events != existing_events:
                updates["health_events"] = resolved_events

        return updates

    def _resolve_matching_health_events(
        self,
        active_issues: list,
        existing_events: list,
    ) -> list:
        """
        Mark health events as resolved when AI reports recovery.
        Uses keyword and description matching instead of event_id.
        """
        RECOVERY_KEYWORDS = ["khỏi", "hết", "đỡ", "bình thường", "phục hồi", "ổn rồi"]

        updated_events = []

        for event in existing_events:
            event_copy = dict(event)

            if event_copy.get("resolved"):
                updated_events.append(event_copy)
                continue

            event_category = event_copy.get("category", "")
            event_desc = event_copy.get("description", "").lower()

            should_resolve = False
            for issue in active_issues:
                issue_text = (issue.get("issue", "") + " " +
                             issue.get("recommendation", "")).lower()
                has_recovery = any(kw in issue_text for kw in RECOVERY_KEYWORDS)
                matches_context = (
                    event_category in issue_text or
                    any(word in issue_text for word in event_desc.split()[:3])
                )
                if has_recovery and matches_context:
                    should_resolve = True
                    break

            if should_resolve:
                event_copy["resolved"] = True
                event_copy["resolved_at"] = datetime.utcnow().isoformat()

            updated_events.append(event_copy)

        return updated_events

    def _status_to_priority(self, overall: str) -> int:
        """Map overall status string to numeric priority."""
        mapping = {
            "urgent": 1,
            "concerning": 3,
            "monitor": 5,
            "good": 7,
        }
        return mapping.get(overall, 5)

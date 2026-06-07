"""
Agent 3 — Nutrition Advisor.

Personalized nutrition advice and meal suggestions based on:
- User's profile (allergies, dietary restrictions, preferences)
- Health Monitor output (nutritional needs, restrictions)
- Nutrition memory (recent meals, foods to avoid)
- Key facts from conversation history

Two-path response logic:
1. If request is clear → give direct nutrition advice
2. If request is ambiguous → return needs_clarification=True + options
   → Orchestrator emits a clarification card popup
   → User selects option → AI continues with clarified intent

Trigger:
- When user message contains food/nutrition keywords
- When health monitor outputs nutritional_needs
"""

import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.memory_service import get_memory_context_for_agent
from app.agents.output_guardrails import append_medical_disclaimer, filter_prohibited_phrases
from app.agents.prompt_builder import build_nutrition_advisor_context
from app.core.constants import DRUG_INTERACTIONS
from app.schemas.chat_card import ClarificationOption, ClarificationPayload, build_clarification_card
from app.services.nutrition_math import calculate_macro_targets

logger = logging.getLogger(__name__)

# ── Allergen Synonyms ────────────────────────────────────────────────────────
# Canonical allergen name → all forms, hidden sources, and related foods to block.

ALLERGEN_SYNONYM_MAP: dict[str, list[str]] = {
    "đậu phộng": [
        "lạc", "peanut", "groundnut",
        "bơ đậu phộng", "peanut butter",
        "dầu lạc", "dầu đậu phộng",
        "satay", "sốt satay", "satay sauce",
        "kẹo lạc", "bánh lạc",
        "mì lạc", "tương lạc",
    ],
    "gluten": [
        "lúa mì", "wheat", "bột mì",
        "bánh mì", "mì", "phở",
        "ramen", "udon", "soba",
        "bia", "soy sauce",
        "malt", "barley", "rye",
    ],
    "sữa": [
        "milk", "dairy", "lactose",
        "phô mai", "cheese", "bơ", "butter",
        "kem", "cream", "yogurt", "sữa chua",
        "whey", "casein", "ghee",
        "chocolate sữa",
    ],
    "tôm": [
        "shrimp", "prawn", "shellfish",
        "hải sản", "seafood",
        "cua", "ghẹ", "sò", "hàu",
        "mực",
        "mắm tôm",
    ],
    "trứng": [
        "egg", "lòng đỏ", "lòng trắng",
        "mayonnaise", "mayo",
        "meringue", "custard",
    ],
    "đậu nành": [
        "soy", "soya", "tofu", "đậu hũ",
        "tương", "nước tương", "miso",
        "edamame", "tempeh",
        "soy sauce", "tamari",
    ],
    "hạt cây": [
        "tree nut", "almond", "hạnh nhân",
        "óc chó", "walnut",
        "hạt điều", "cashew",
        "macadamia", "pistachio",
        "hạt dẻ", "hazelnut",
        "hạt thông", "pine nut",
    ],
    "cá": [
        "fish", "cá ngừ", "tuna",
        "cá hồi", "salmon",
        "cá thu", "mackerel",
        "cá mú", "cá basa",
        "nước mắm",
        "worcestershire sauce",
    ],
}


def _expand_allergens(allergen_name: str) -> list[str]:
    """
    Expand a single allergen name → all synonym forms that must be blocked.

    Returns a list that includes the canonical name plus all known synonyms.
    If the allergen_name is itself a synonym (not a canonical key), it resolves
    to the canonical group so that all variants are blocked.
    Falls back to returning [allergen_name] if not found in the map.
    """
    allergen_lower = allergen_name.lower().strip()
    for canonical, synonyms in ALLERGEN_SYNONYM_MAP.items():
        all_forms = [canonical] + synonyms
        if allergen_lower in [f.lower() for f in all_forms]:
            return [canonical] + synonyms
    return [allergen_lower]


# ─── Ambiguity Detection Rules ───────────────────────────────────────────────────

VAGUE_NUTRITION_PATTERNS = [
    # Very short or generic questions
    (r"^[\s\S]{0,15}$", "too_short"),
    # Generic wish-fulfillment without specifics
    (r"(?:nên|muốn|cho mình)\s+(?:ăn|uống)\s*\??$", "no_object"),
    # "what should I eat?" without context
    (r"^(?:ăn|uống)\s*(?:gì|nào)?\s*\??$", "no_context"),
    # Goal without meal type
    (r"(?:giảm cân|tăng cơ|tăng cân)\s*(?:thì|sao|nào|đi|ở|nên)?\s*\??$", "goal_only_no_meal"),
    # Multi-topic combined (fitness + nutrition in same vague sentence)
    (r"tập.*(?:ăn|uống)|(?:ăn|uống).*tập", "multi_topic_vague"),
    # No specifics: "meal plan" or "food" without specifying what
    (r"^(?:thực đơn|kế hoạch ăn|meal plan)\s*\??$", "plan_without_goal"),
    # "how to eat?" without goal
    (r"(?:ăn|nấu|uống)\s+(?:như thế nào|sao|thế nào)\s*\??$", "how_without_what"),
    # Ambiguous follow-ups (respond to recent question but lacks specifics)
    (r"^(?:ừm|ok|okay|được|đồng ý|vậy|thì|có|mà|hay|là)\s*$", "vague_affirmation"),
]


def detect_ambiguous_intent(message: str, history: list[dict]) -> tuple[bool, str]:
    """
    Rule-based pre-check before sending to AI.

    Returns (is_ambiguous, reason_code).
    This is a fast filter to avoid unnecessary AI calls for obviously vague messages.
    """
    msg_lower = message.strip().lower()

    # Only treat as ambiguous-nutrition if the message actually contains nutrition keywords.
    # Prevents ClarificationCard from firing on fitness-only short messages.
    nutrition_core_kw = ["ăn", "uống", "calo", "thực đơn", "món"]
    has_nutrition_kw = any(kw in msg_lower for kw in nutrition_core_kw)

    # Short messages — only flag as ambiguous if they contain nutrition keywords
    if len(msg_lower) <= 20:
        import re
        for pattern, code in VAGUE_NUTRITION_PATTERNS:
            if re.search(pattern, msg_lower):
                if has_nutrition_kw:
                    return True, code
                return False, ""

    # Check for multiple unrelated intents in single message
    nutrition_kw = any(kw in msg_lower for kw in ["ăn", "uống", "dinh dưỡng", "thực đơn", "calo"])
    fitness_kw = any(kw in msg_lower for kw in ["tập", "gym", "cardio", "workout", "bài tập"])
    health_kw = any(kw in msg_lower for kw in ["mệt", "đau", "bệnh", "triệu chứng"])

    if sum([nutrition_kw, fitness_kw, health_kw]) >= 2:
        # Multiple domains but message is short/vague
        if len(msg_lower) <= 50:
            return True, "multi_domain_short"

    # Check last assistant message for pending clarification context
    if history:
        last_assistant = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant = msg.get("content", "").lower()
                break

        # If AI asked a clarification question and user gives a short response
        if last_assistant and ("chọn" in last_assistant or "nào" in last_assistant or "hướng nào" in last_assistant):
            if len(msg_lower) <= 15:
                return True, "vague_clarification_response"

    return False, ""


# ─── Behavioral Eating Pattern Classifier ───────────────────────────────────────
# Detects disordered eating patterns that warrant a clinical psychology response.

BEHAVIORAL_EATING_PATTERNS: list[tuple[str, str, str]] = [
    # (regex_pattern, category, label)
    # Skipping meals
    (r"(?:bỏ|bỏ qua|không.*ă.n)\s*(?:bữa|bữa sáng|bữa trưa|bữa tối)", "skipping_meals", "Bỏ bữa"),
    (r"(?:nhị[nh]?\s*ă[n]?|nhịn)\s*(?:đói|ă[n]?)", "skipping_meals", "Nhịn ăn"),
    (r"(?:sáng|nay)\s*(?:không\s*ă[n]?|chưa\s*ă[n]?)(?:\s|$)", "skipping_meals", "Bỏ bữa sáng"),

    # Late-night eating
    (r"(?:ă[n]\s*)?đêm|đêm\s*(?:khuya|muộn|12h|1h|2h|3h)|khuya\s*ă[n]", "late_night_eating", "Ăn đêm"),
    (r"(?:đói|thèm)\s*(?:đêm|khuya)", "late_night_eating", "Thèm đêm"),
    (r"(?:gọi|order|mang)\s*(?:đồ|đồ ă[n])\s*(?:đêm|khuya)", "late_night_eating", "Ăn đêm muộn"),

    # Emotional eating — sweet cravings
    (r"thèm\s*(?:ngọt|đường|bánh|keo|socola|chocolate|kẹo)", "emotional_eating_sweet", "Thèm ngọt"),
    (r"(?:ă[n]|không\s*ă[n]?)\s*(?:bánh|kẹo|socola)\s*(?:lúc|khi)", "emotional_eating_sweet", "Ăn bánh theo cảm xúc"),
    (r"stress.*(ă[n]|ngọt)|(ă[n]|ngọt).*stress", "emotional_eating_sweet", "Stress eating"),

    # Emotional eating — savory cravings
    (r"thèm\s*(?:mặn|đồ\s*chiên|đồ\s*ngập|thức ă[n]\s*ngậ[py])", "emotional_eating_savory", "Thèm đồ chiên"),
    (r"(?:buồn|mệt|chán|nả[n]?|bực)\s*(?:nên\s*)?(?:ă[n]|thèm)", "emotional_eating_savory", "Ăn theo cảm xúc"),
    (r"(?:ă[n]\s*)?(?:để\s*)?(?:giải\s*)?(?:stress|buồn|mệt|chán)", "emotional_eating_savory", "Ăn giải tỏa"),

    # Binge / uncontrolled eating
    (r"(?:ă[n]\s*)?(?:vô\s*)?(?:độ|tổ\s*chức)|(ă[n])\s*(?:quá\s*)?(?:nhiều|lắm|no)", "binge_eating", "Ăn vô độ"),
    (r"(?:không\s*)?(?:kiểm\s*soát|控制)", "binge_eating", "Mất kiểm soát ăn uống"),
    (r"(?:ă[n]\s*)?(?:như\s*)?(?:con\s*)?(?:điên|khùng|mất\s*kiểm)", "binge_eating", "Ăn mất kiểm soát"),
    (r"(?:sau\s*)?(?:khi\s*)?(?:ăn\s*)?(?:xong\s*)?(?:thấy|hay|luôn)\s*(?:đói|muốn\s*ă[n])\s*(?:nữa|liền)", "binge_eating", "Ăn không no"),

    # Disordered eating patterns
    (r"(?:chỉ\s*ă[n]\s*)?(?:rau|trái\s*cây|ổi)\s*(?:thôi|thui|hết)", "disordered_eating", "Hạn chế cực đoan"),
    (r"(?:ăn\s*)?(?:chay|kiêng)\s*(?:kỉ|quá)", "disordered_eating", "Ăn chay cực đoan"),
    (r"(?:sợ|lên\s*câ[n]?)\s*(?:ă[n]|béo|mập)", "disordered_eating", "Sợ ăn"),
    (r"(?:nạp|đổ)\s*(?:bữa|bữa\s*ăn)\s*(?:để\s*)?(?:rồi|thôi)", "disordered_eating", "Nạp rồi thôi"),
]

# Objective reason keywords — suppress false positives in behavioral pattern detection.
# If any of these keywords appear near a behavioral pattern match, the pattern is
# considered benign (not a disordered eating signal).
# Prevents: "bỏ bữa sáng vì bận học" → not disordered
#           "chưa kịp ăn sáng vì trễ giờ" → not disordered
OBJECTIVE_REASON_KEYWORDS = [
    # Work / school / schedule
    "bận", "bận học", "bận làm", "trễ giờ", "chưa kịp",
    "không có thời gian", "gấp", "họp", "thi", "exam",
    "đi làm", "đi học", "sáng sớm", "dậy muộn",
    # Health-related (not psychological)
    "đau bụng", "nôn", "ốm", "bệnh", "viêm", "cảm",
    "dị ứng", "không dung nạp",
    # Neutral descriptions
    "thỉnh thoảng", "lúc nào", "thường",
]


def classify_behavioral_pattern(message: str, conversation_history: list[dict]) -> tuple[bool, str, str]:
    """
    Classify eating behaviour from user message + recent chat history.

    Returns (is_behavioral, category, label):
      - is_behavioral: True only when a behavioral pattern is detected
                       AND no objective/lifestyle reason is present nearby.
      - category:      skipping_meals | late_night_eating | emotional_eating_sweet |
                      emotional_eating_savory | binge_eating | disordered_eating
      - label:         human-readable label

    Anti-false-positive strategy:
      1. Check pattern match in current message and last 3 turns
      2. If a match is found, scan ±50 chars for OBJECTIVE_REASON_KEYWORDS
         (work, school, health, neutral descriptors)
      3. If objective reasons are found in context, suppress the trigger
    """
    msg_lower = message.strip().lower()

    import re as _re

    # Build history context for keyword scanning
    history_text = ""
    if conversation_history:
        history_text = " ".join(
            msg.get("content", "").lower()
            for msg in conversation_history[-3:]
        )
    combined = msg_lower + " " + history_text

    for pattern, category, label in BEHAVIORAL_EATING_PATTERNS:
        match = _re.search(pattern, msg_lower)
        if not match and history_text:
            match = _re.search(pattern, history_text)

        if match:
            # Anti-false-positive gate: expand ±50 chars around the match
            # and suppress if any objective/lifestyle reason keyword appears nearby
            matched_text = match.group(0)
            match_pos = combined.find(matched_text)
            if match_pos == -1:
                match_pos = 0
            ctx_start = max(0, match_pos - 50)
            ctx_end = min(len(combined), match_pos + len(matched_text) + 50)
            local_context = combined[ctx_start:ctx_end]

            for reason in OBJECTIVE_REASON_KEYWORDS:
                if reason.lower() in local_context:
                    return False, "", ""

            # Pattern fires — no benign objective reason found
            return True, category, label

    return False, "", ""


# ─── Drug–Nutrient Interaction Detector ────────────────────────────────────────

def _check_drug_interactions(
    medications: list | None,
) -> tuple[list[str], list[str]]:
    """
    Check medications against DRUG_INTERACTIONS and return
    (avoid_items, warnings) for injection into the AI prompt.

    Returns:
      avoid_items  — flat list of food/ingredient identifiers to hard-block
      warnings     — list of reason strings for the disclaimer block

    Gracefully handles None/missing/empty medications.
    """
    if not medications:
        return [], []

    avoid_items: list[str] = []
    warnings: list[str] = []

    for med in medications:
        med_dict = med if isinstance(med, dict) else {}
        name = med_dict.get("name", "")
        if not name:
            continue

        name_lower = name.lower().strip()
        for drug_key, interaction in DRUG_INTERACTIONS.items():
            if drug_key in name_lower or name_lower in drug_key:
                avoid_list = interaction.get("avoid", [])
                if avoid_list:
                    avoid_items.extend(avoid_list)
                reason = interaction.get("reason", "")
                if reason:
                    warnings.append(reason)
                note = interaction.get("note", "")
                if note:
                    warnings.append(note)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_avoid: list[str] = []
    for item in avoid_items:
        if item not in seen:
            seen.add(item)
            unique_avoid.append(item)

    return unique_avoid, warnings


class NutritionAdvisorAgent(BaseAgent):
    name = "nutrition_advisor"
    _ctx: AgentContext | None = None

    MEAL_PLAN_KEYWORDS = [
        "thực đơn", "kế hoạch ăn", "ăn gì", "gợi ý bữa",
        "nên ăn", "bữa sáng", "bữa trưa", "bữa tối"
    ]
    SPECIFIC_FOOD_KEYWORDS = [
        "có nên ăn", "ăn được không", "độc không",
        "an toàn không", "có hại không", "tốt không"
    ]

    # ── Mode A: Algorithmic Tool Layer ────────────────────────────────────────

    def _calculate_macros_tool(
        self,
        full_context,
        active_goal,
    ) -> dict | None:
        """
        Mode A Tool: run the Mifflin-St Jeor algorithm BEFORE LLM generates suggestions.

        Extracts biometric data from full_context and active_goal, calls
        calculate_macro_targets(), and returns a dict ready to inject into the prompt.

        Returns None if required fields are missing — Mode A falls back gracefully.
        """
        try:
            # Priority 1: NutritionGoal (user-verified canonical data)
            if active_goal:
                weight  = getattr(active_goal, "weight_kg", None)
                height  = getattr(active_goal, "height_cm", None)
                age     = getattr(active_goal, "age", None)
                gender  = getattr(active_goal, "gender", None)
                activity = getattr(active_goal, "activity_level", None)
                goal_type = (
                    active_goal.goal_type.value
                    if hasattr(active_goal.goal_type, "value")
                    else str(active_goal.goal_type)
                )
            else:
                weight, height, age, gender, activity, goal_type = None, None, None, None, None, None

            # Priority 2: FullUserContext fields (AI-extracted + profile)
            fc = full_context
            if fc:
                weight   = weight   or getattr(fc, "weight_kg",      None)
                height   = height   or getattr(fc, "height_cm",      None)
                age      = age      or getattr(fc, "age",            None)
                gender   = gender   or getattr(fc, "gender",         None)
                activity = activity or getattr(fc, "activity_level", None)
                goal_type = goal_type or getattr(fc, "usage_goal",   None)

            # All five fields required
            if not all([weight, height, age, gender, activity, goal_type]):
                logger.debug(
                    "[NutritionAdvisor] Mode A skipped — missing biometric fields "
                    "(weight=%s, height=%s, age=%s, gender=%s, activity=%s, goal=%s)",
                    weight, height, age, gender, activity, goal_type,
                )
                return None

            result = calculate_macro_targets(
                weight_kg=float(weight),
                height_cm=float(height),
                age=int(age),
                gender=str(gender),
                activity_level=str(activity),
                nutrition_goal_type=str(goal_type),
            )

            return {
                "bmr":                result.macros.bmr,
                "tdee":               result.macros.tdee,
                "target_calories":    result.macros.target_calories,
                "protein_g":          result.macros.protein_g,
                "carb_g":             result.macros.carb_g,
                "fat_g":              result.macros.fat_g,
                "goal_type":          result.goal_type,
                "calorie_floor":      result.calorie_floor,
                "is_using_floor":     result.is_using_floor,
            }

        except ValueError as ve:
            logger.warning("[NutritionAdvisor] Mode A tool validation error: %s", ve)
            return None
        except Exception as e:
            logger.error("[NutritionAdvisor] Mode A tool unexpected error: %s", e)
            return None

    def _format_macro_tool_result(self, macro_data: dict) -> str:
        """Pretty-format macro tool output for injection into the user prompt."""
        lines = [
            "",
            "━━━ MACRO CALCULATOR (Algorithmic — DO NOT override) ━━━",
            f"  BMR:               {macro_data['bmr']:.0f} kcal",
            f"  TDEE:              {macro_data['tdee']:.0f} kcal",
            f"  Target Calories:   {macro_data['target_calories']:.0f} kcal",
            f"  Protein:           {macro_data['protein_g']:.0f}g",
            f"  Carbohydrate:      {macro_data['carb_g']:.0f}g",
            f"  Fat:               {macro_data['fat_g']:.0f}g",
            f"  Goal:              {macro_data['goal_type']}",
        ]
        if macro_data.get("is_using_floor"):
            lines.append("  ⚠ Note: Deficit clamped to BMR floor (safe minimum).")
        lines.append("━━━ END MACRO CALCULATOR ━━━\n")
        return "\n".join(lines)

    # ── Mode B: Behavioral Nutrition Analysis ─────────────────────────────────

    async def _run_mode_b(
        self,
        context: AgentContext,
        behavior_category: str,
        behavior_label: str,
        memory_ctx: dict,
        hard_avoid: list,
        db: AsyncSession,
        start_time: float,
    ) -> AgentResult | None:
        """
        Handle behavioral eating patterns with clinical nutrition psychology.

        Routes to clinical psychology + nutrition prompt. Returns an AgentResult
        with empathetic analysis, root-cause explanation, and up to 2 clarifying
        questions — NOT a card (card-based clarification is for intent ambiguity).

        Returns None on failure so the caller falls through to normal flow.
        """
        try:
            # Build Mode B prompt with behavioral context
            prompt = self._build_mode_b_prompt(
                user_message=context.current_message,
                behavior_category=behavior_category,
                behavior_label=behavior_label,
                memory_ctx=memory_ctx,
                conversation_history=context.conversation_history or [],
                full_context=context.full_context,
            )

            raw = await self._call_ai(
                system_prompt=self._system_prompt_mode_b(),
                user_prompt=prompt,
                response_format="json",
                max_tokens=800,
            )

            raw_data = raw if isinstance(raw, dict) else self._parse_json_safe(raw)
            result_data = raw_data.get("behavioral_response", raw_data)

            # Filter prohibited phrases from Mode B output
            mode_b_text = result_data.get("user_facing_text", "")
            if mode_b_text:
                mode_b_text = filter_prohibited_phrases(mode_b_text)
                mode_b_text = append_medical_disclaimer(mode_b_text, context="nutrition")
                result_data["user_facing_text"] = mode_b_text

            latency_ms = int((time.time() - start_time) * 1000)
            return AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="behavioral_nutrition",
                content={
                    "response_mode": "mode_b",
                    "behavior_category": behavior_category,
                    "behavior_label": behavior_label,
                    **result_data,
                },
                confidence=0.80,
                priority=4,
                text_for_orchestrator=result_data.get("user_facing_text", ""),
                memory_updates={},
                suggested_card=None,
                error=None,
            )

        except Exception as e:
            logger.error("[NutritionAdvisor] Mode B failed for category '%s': %s", behavior_category, e)
            return None

    def _build_mode_b_prompt(
        self,
        user_message: str,
        behavior_category: str,
        behavior_label: str,
        memory_ctx: dict,
        conversation_history: list[dict],
        full_context,
    ) -> str:
        """Build user prompt for Mode B behavioral analysis."""
        parts = [
            f"━━━ BEHAVIORAL ANALYSIS REQUEST ━━━",
            f"Detected pattern: [{behavior_label}] ({behavior_category})",
            f"User message: {user_message}",
            "",
        ]

        # Inject recent chat history (last 3 turns) for context
        if conversation_history:
            recent = conversation_history[-3:]
            history_lines = [
                f"[{msg.get('role', 'unknown')}] {msg.get('content', '')[:200]}"
                for msg in recent
            ]
            parts.append("Recent conversation:\n" + "\n".join(history_lines))

        # Inject biometric data if available (helps AI give science-based explanations)
        if full_context:
            age    = getattr(full_context, "age",       None)
            gender = getattr(full_context, "gender",    None)
            weight = getattr(full_context, "weight_kg", None)
            if any([age, gender, weight]):
                parts.append(
                    f"User biometrics: age={age}, gender={gender}, weight={weight}kg"
                )

        # Inject eating history from memory
        nutrition_mem = memory_ctx.get("nutrition_memory") or {}
        recent_meals = nutrition_mem.get("recent_meals", [])[:5]
        if recent_meals:
            meal_summary = ", ".join(
                f"{m.get('meal_type','meal')} {m.get('kcal',0)}kcal"
                for m in recent_meals if isinstance(m, dict)
            )
            parts.append(f"Recent meals: {meal_summary}")

        parts.append("")
        return "\n".join(parts)

    def _system_prompt_mode_b(self) -> str:
        """
        Clinical Nutrition Psychology prompt for behavioral eating patterns.

        Guiding principles:
        - Empathetic, never judgmental
        - Root-cause analysis before advice
        - Max 2 open-ended clarifying questions focused on TRIGGER identification
        - Short-term behavioral alternatives, not macro-perfect meal plans
        """
        return """
You are a clinical nutrition psychologist specializing in eating behavior.
You analyze eating patterns and provide empathetic, science-based responses.

━━━ CONTEXT ━━━
You will receive:
- A detected BEHAVIORAL PATTERN category (e.g. "late_night_eating", "emotional_eating_sweet")
- The user's message
- Recent conversation history (last 3 turns)
- Optional biometric data (age, gender, weight)

━━━ YOUR TASK ━━━
When you receive a behavioral eating pattern:

1. ROOT-CAUSE ANALYSIS (explain WHY this happens, not just WHAT to eat)
2. EMPATHETIC RESPONSE (never judge, never shame)
3. SHORT-TERM ALTERNATIVE (harm reduction — a better choice right now)
4. CLARIFYING QUESTIONS (max 2, open-ended, focus on TRIGGER identification)

━━━ PSYCHOLOGICAL ROOT-CAUSE EXAMPLES ━━━
- Late-night eating: "Cortisol và ghrelin tăng cao vào buổi tối khi stress kéo dài. Não bộ tìm carbohydrate như cơ chế tự vệ giải phóng serotonin."
- Skipping meals: "Bỏ bữa sáng gây sụt giảm đường huyết → insulin bù đắp quá mức → thèm ngọt và ăn nhiều hơn vào bữa sau. Đây là vòng lặp sinh lý, không phải lỗi ý chí."
- Emotional sweet cravings: "Thèm đường khi buồn là phản ứng của hệ dopamine. Não nhớ rằng đường kích hoạt reward pathway — đây là conditioning, không phải thiếu ý chí."
- Binge eating: "Ăn mất kiểm soát thường xảy ra sau giai đoạn hạn chế nghiêm ngặt. Đây là response của cơ chế bảo vệ cơ thể trước 'threat' của việc thiếu năng lượng."

━━━ RESPONSE RULES ━━━
- NEVER say: "bạn nên kiểm soát", "đừng ăn", "không tốt"
- ALWAYS say: "có thể bạn đang...", "một số người nhận thấy rằng...", "một lựa chọn nhẹ nhàng hơn có thể là..."
- MAX 2 clarifying questions per response. Questions must be about TRIGGERS:
  Good: "Bạn thường cảm thấy thèm ngọt vào khung giờ nào trong ngày?"
  Good: "Tình trạng bỏ bữa sáng này đã diễn ra liên tục bao nhiêu ngày rồi?"
  Bad:  "Bạn có tập thể dục không?" (unrelated)
  Bad:  Multiple questions about diet details

━━━ SHORT-TERM ALTERNATIVES ━━━
- Thèm ngọt: hạt điều/hạnh nhân 10g, táo + bơ, sữa chua không đường, trà gừng
- Ăn đêm: nước ấm + chanh, súp rau nhẹ, sữa ấm
- Bỏ bữa: sữa hạt + chuối, bánh mì nguyên cám phết bơ đậu, smoothie protein
- Ăn vô độ: uống nước trước 15 phút, đi bộ 10 phút, hít thở 4-7-8

━━━ OUTPUT SCHEMA ━━━
Return ONLY valid JSON:
{
  "needs_clarification": false,
  "behavioral_response": {
    "root_cause": "2-3 sentences explaining the physiological/psychological mechanism (Vietnamese)",
    "empathy_statement": "1-2 empathetic sentences acknowledging the user's experience (Vietnamese)",
    "short_term_alternative": "One specific, actionable substitution (Vietnamese, include approximate portions)",
    "clarifying_questions": [
      {
        "question": "Open question about the trigger (Vietnamese, max 50 chars)",
        "purpose": "trigger_identification"
      }
    ],
    "user_facing_text": "Full empathetic response in Vietnamese, 3-5 sentences, conversational tone"
  }
}

━━━ HARD RULES ━━━
- Output ONLY valid JSON. No markdown fences. No explanations outside JSON.
- MAX 2 clarifying questions. Never more.
- Never judge or shame eating behavior.
- Use Vietnamese language in all user-facing fields.
- All clarifying questions must focus on trigger identification.
"""

    # ── Mode A: Algorithmic Tool Layer ────────────────────────────────────────

    async def execute(self, context: AgentContext, db: AsyncSession) -> AgentResult:
        self._ctx = context
        run = self._log_start(
            context=context,
            trigger="nutrition_keyword_detected",
            input_summary=context.current_message[:200],
            db=db,
        )
        start_time = time.time()

        try:
            # ── 0. Fast rule-based ambiguity pre-check ──────────────────────────
            is_ambiguous, reason = detect_ambiguous_intent(
                context.current_message,
                context.conversation_history
            )

            # ── 1. Get nutrition memory + profile ───────────────────────────────
            memory_ctx = await get_memory_context_for_agent(
                context.user.id, "nutrition_advisor", db
            )
            profile = context.profile

            # ── 2. Get health_monitor result from context ───────────────────────
            health_result = getattr(context, "agent_results", {}).get("health")
            health_restrictions = []
            nutritional_needs = {}
            if health_result and health_result.success:
                health_restrictions = (
                    health_result.content.get("nutritional_needs", {})
                    .get("avoid", [])
                )
                nutritional_needs = health_result.content.get("nutritional_needs", {})

            # ── 3. Build hard constraints (NEVER suggest these) ─────────────────
            hard_avoid: list[str] = []
            if profile:
                if hasattr(profile, "allergies") and profile.allergies:
                    for a in profile.allergies:
                        if isinstance(a, dict):
                            allergen_name = a.get("allergen", "")
                        else:
                            allergen_name = str(a)
                        if allergen_name:
                            # Expand allergens to all synonyms / hidden sources
                            hard_avoid.extend(_expand_allergens(allergen_name))
                if hasattr(profile, "dietary_restrictions") and profile.dietary_restrictions:
                    hard_avoid.extend(profile.dietary_restrictions)

            # Deduplicate after expansion
            hard_avoid = list(set(hard_avoid))

            # ── Demographic Safety Constraints ─────────────────────────────────
            # These block dangerous advice for pregnant, breastfeeding, minor, elderly users.
            # Applied BEFORE the AI call so the system prompt encodes them.
            demographic_disclaimer = ""
            demographic_restrictions: list[str] = []

            demo_flags = getattr(context, "demographic_flags", {})
            if demo_flags.get("is_pregnant"):
                demographic_restrictions.extend([
                    "calorie_restriction",
                    "weight_loss_diet",
                    "fasting",
                    "intermittent_fasting",
                    "detox_diet",
                    "raw_fish",
                    "unpasteurized_dairy",
                    "high_mercury_fish",
                ])
                demographic_disclaimer = (
                    "⚠️ QUAN TRỌNG: Người dùng đang MANG THAI. "
                    "KHÔNG được gợi ý giảm cân, hạn chế calo, nhịn ăn, "
                    "hoặc bất kỳ thực phẩm nguy hiểm cho thai kỳ (cá ngừ lớn, "
                    "phô mai tươi, đồ sống). Thay vào đó, tập trung dinh dưỡng "
                    "đủ chất cho mẹ và bé. Luôn kèm disclaimer: tham khảo bác sĩ sản khoa."
                )
            elif demo_flags.get("is_breastfeeding"):
                demographic_restrictions.extend([
                    "calorie_restriction",
                    "fasting",
                    "high_caffeine",
                ])
                demographic_disclaimer = (
                    "Người dùng đang cho con bú — đảm bảo đủ calo và dinh dưỡng."
                )

            if demo_flags.get("is_minor"):
                demographic_restrictions.extend([
                    "calorie_restriction",
                    "weight_loss_diet",
                    "fasting",
                    "adult_supplements",
                ])
                demographic_disclaimer += (
                    " Người dùng dưới 18 tuổi — KHÔNG gợi ý giảm cân hay "
                    "hạn chế calo. Tư vấn chế độ dinh dưỡng phát triển lành mạnh."
                )

            if demo_flags.get("is_elderly"):
                demographic_restrictions.extend([
                    "extreme_calorie_restriction",
                    "very_high_protein_without_medical_supervision",
                ])
                demographic_disclaimer += (
                    " Người dùng trên 65 tuổi — thận trọng với thay đổi chế độ ăn lớn."
                )

            # Drug–nutrient interaction filter. Matches medication names against
            # DRUG_INTERACTIONS keys and hard-blocks any interacting foods.
            drug_avoid: list[str] = []
            drug_warnings: list[str] = []
            meds = getattr(context, "medications", None)
            if meds:
                drug_avoid, drug_warnings = _check_drug_interactions(meds)

            if drug_avoid:
                hard_avoid.extend(drug_avoid)

            if drug_warnings:
                warning_block = " | ".join(drug_warnings)
                if demographic_disclaimer:
                    demographic_disclaimer += f"\n⚠️ TƯƠNG TÁC THUỐC-THỰC PHẨM: {warning_block}"
                else:
                    demographic_disclaimer = (
                        f"⚠️ TƯƠNG TÁC THUỐC-THỰC PHẨM: {warning_block}"
                    )

            # ── 4. Build soft constraints (avoid today) ───────────────────────────
            soft_avoid = list(health_restrictions)
            nutrition_mem = memory_ctx.get("nutrition_memory") or {}
            foods_to_avoid = nutrition_mem.get("foods_to_avoid", [])
            soft_avoid.extend([f["food"] for f in foods_to_avoid if isinstance(f, dict)])

            # ── 5. Build preference context ─────────────────────────────────────
            taste_prefs = {}
            cuisine_prefs = []
            favorite_foods = []
            disliked_foods = []
            if profile:
                taste_prefs = getattr(profile, "taste_preferences", {}) or {}
                cuisine_prefs = getattr(profile, "cuisine_preferences", []) or []
                favorite_foods = getattr(profile, "favorite_foods", []) or []
                disliked_foods = getattr(profile, "disliked_foods", []) or []
                if isinstance(disliked_foods, list):
                    disliked_foods = [
                        d if isinstance(d, str) else d.get("name", "")
                        for d in disliked_foods
                    ]

            # ── 6. Recent meals ────────────────────────────────────────────────
            recent_meals = nutrition_mem.get("recent_meals", [])[:7]
            recent_foods = []
            for meal in recent_meals:
                if isinstance(meal, dict):
                    recent_foods.extend(meal.get("items", []))

            # ── 7. Key facts (health-related) ──────────────────────────────────
            key_facts = memory_ctx.get("key_facts") or []
            health_facts = [
                f["fact"] for f in key_facts
                if f.get("confidence") in ("high", "medium")
            ]

            # ── 8. Detect query type + Behavioral Pattern ─────────────────────
            msg_lower = context.current_message.lower()
            is_meal_plan = any(kw in msg_lower for kw in self.MEAL_PLAN_KEYWORDS)
            is_specific_food = any(kw in msg_lower for kw in self.SPECIFIC_FOOD_KEYWORDS)

            # Classify behavioral eating patterns
            is_behavioral, behavior_category, behavior_label = classify_behavioral_pattern(
                message=context.current_message,
                conversation_history=context.conversation_history or [],
            )

            # ── Mode B: Behavioral / Psychological Nutrition Analysis ────────────
            if is_behavioral:
                mode_b_result = await self._run_mode_b(
                    context=context,
                    behavior_category=behavior_category,
                    behavior_label=behavior_label,
                    memory_ctx=memory_ctx,
                    hard_avoid=hard_avoid,
                    db=db,
                    start_time=start_time,
                )
                if mode_b_result is not None:
                    await self._log_complete(run, mode_b_result, db)
                    return mode_b_result
                # Fall through to normal flow if Mode B returns None

            # ── Mode A: Algorithmic macro tool (Mifflin-St Jeor) ─────────────────
            macro_data = None
            if is_meal_plan or (
                context.full_context and getattr(context.full_context, "weight_kg", None)
            ):
                macro_data = self._calculate_macros_tool(
                    full_context=context.full_context,
                    active_goal=context.active_goal,
                )

            # ── 9. Build prompt (macro_data injected here) ─────────────────────
            prompt = self._build_prompt(
                user_message=context.current_message,
                hard_avoid=hard_avoid,
                soft_avoid=soft_avoid,
                taste_prefs=taste_prefs,
                cuisine_prefs=cuisine_prefs,
                favorite_foods=favorite_foods,
                disliked_foods=disliked_foods,
                recent_foods=recent_foods,
                nutritional_needs=nutritional_needs,
                health_facts=health_facts,
                is_meal_plan=is_meal_plan,
                is_specific_food=is_specific_food,
                profile=profile,
                active_goal=context.active_goal,
                full_context=context.full_context,
                macro_data=macro_data,
                demographic_disclaimer=demographic_disclaimer,
                demographic_restrictions=demographic_restrictions,
            )

            # Extend hard_avoid so the post-AI allergen-safety filter also strips
            # dietary advice that includes demographic restrictions.
            if demographic_restrictions:
                hard_avoid.extend(demographic_restrictions)

            # ── 10. Call AI with TWO-PATH response schema ─────────────────────
            raw = await self._call_ai(
                system_prompt=self._system_prompt(
                    macro_data=macro_data,
                    demographic_disclaimer=demographic_disclaimer,
                    demographic_restrictions=demographic_restrictions,
                ),
                user_prompt=prompt,
                response_format="json",
                max_tokens=1200,
            )

            # ── 11. Parse JSON ────────────────────────────────────────────────
            raw_data = raw if isinstance(raw, dict) else self._parse_json_safe(raw)

            # ── 12. Check if AI wants clarification ─────────────────────────────
            clarification_payload = self._extract_clarification(raw_data)
            if clarification_payload and clarification_payload.needs_clarification:
                # Validate: must have 2-4 options
                opts = clarification_payload.clarification_options
                if opts and 2 <= len(opts) <= 4:
                    card = build_clarification_card(
                        clarification=clarification_payload,
                        trigger_reason="intent_ambiguity",
                    )
                    latency = int((time.time() - start_time) * 1000)
                    agent_result = AgentResult(
                        agent_name=self.name,
                        success=True,
                        insight_type="clarification_request",
                        content=raw_data,
                        confidence=clarification_payload.confidence,
                        priority=5,
                        text_for_orchestrator=(
                            f"[Clarification] {clarification_payload.clarification_question}"
                        ),
                        memory_updates={},
                        suggested_card=card,
                        error=None,
                    )
                    await self._log_complete(run, agent_result, db, latency_ms=latency)
                    return agent_result

            # ── 13. Normal path: parse as nutrition advice ────────────────────
            result_data = raw_data.get("nutrition_advice", raw_data)

            # Safety check — verify no allergens in suggestions
            result_data = self._verify_no_allergens(result_data, hard_avoid)

            # Build memory updates
            memory_updates = {}
            if result_data.get("nutrition_gaps"):
                memory_updates = {
                    "nutrition_memory": {
                        "common_deficiencies": result_data["nutrition_gaps"]
                    }
                }

            # Append medical disclaimer to normal nutrition advice
            user_facing_summary = result_data.get("user_facing_summary", "")
            if user_facing_summary:
                user_facing_summary = append_medical_disclaimer(
                    user_facing_summary, context="nutrition"
                )

            latency = int((time.time() - start_time) * 1000)
            agent_result = AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="nutrition_recommendation",
                content=result_data,
                confidence=0.85,
                priority=5,
                text_for_orchestrator=user_facing_summary,
                memory_updates=memory_updates,
                suggested_card=None,
                error=None,
            )
            await self._log_complete(run, agent_result, db, latency_ms=latency)
            return agent_result

        except Exception as e:
            logger.error(f"NutritionAdvisorAgent failed: {e}")
            err_result = AgentResult(
                agent_name=self.name, success=False,
                insight_type="nutrition_recommendation", content={},
                confidence=0.0, priority=5, text_for_orchestrator="",
                memory_updates={}, suggested_card=None, error=str(e)
            )
            await self._log_complete(run, err_result, db)
            return err_result

    # ── Clarification Detection ────────────────────────────────────────────────

    def _extract_clarification(self, data: dict[str, Any]) -> ClarificationPayload | None:
        """
        Extract clarification from AI JSON response.

        The AI returns either:
          - { needs_clarification: true, clarification_question, clarification_options, ... }
          - { needs_clarification: false, nutrition_advice: { ... } }

        Falls back gracefully if schema doesn't match.
        """
        if not data:
            return None

        # Direct needs_clarification flag
        if data.get("needs_clarification") is True:
            try:
                return ClarificationPayload.model_validate(data)
            except Exception:
                logger.warning("NutritionAdvisor: failed to validate ClarificationPayload: %s", data)
                return None

        # Fallback: check if nutrition_advice is absent AND no meal_suggestions
        # (suggests the AI didn't give advice — might mean it wanted clarification)
        has_advice = bool(data.get("meal_suggestions") or data.get("foods_to_avoid_today"))
        if not has_advice and data.get("needs_clarification") is not False:
            question = data.get("clarification_question") or data.get("title")
            options = data.get("clarification_options")
            if question and options:
                try:
                    parsed_opts = []
                    for opt in options:
                        if isinstance(opt, dict):
                            parsed_opts.append(ClarificationOption(
                                id=opt.get("id", ""),
                                label=opt.get("label", ""),
                                description=opt.get("description"),
                            ))
                    if len(parsed_opts) >= 2:
                        return ClarificationPayload(
                            needs_clarification=True,
                            clarification_question=question,
                            clarification_hint=data.get("clarification_hint"),
                            clarification_options=parsed_opts,
                        )
                except Exception:
                    pass

        return None

    # ── System Prompt (Two-Path) ───────────────────────────────────────────────

    def _system_prompt(
        self,
        macro_data: dict | None = None,
        demographic_disclaimer: str = "",
        demographic_restrictions: list[str] | None = None,
    ) -> str:
        restrictions_list = demographic_restrictions or []
        restrictions_str = ""
        if restrictions_list:
            restrictions_str = (
                f"\n\n🚨 DEMOGRAPHIC SAFETY — TUYỆT ĐỐI KHÔNG gợi ý: "
                f"{', '.join(restrictions_list)}."
            )
        disclaimer_block = (
            f"\n\n{demographic_disclaimer}"
            if demographic_disclaimer
            else ""
        )
        return f"""{disclaimer_block}{restrictions_str}

You are a certified nutritionist and culinary expert specializing in
Vietnamese and Asian cuisine with deep knowledge of food science.

Your job has TWO modes. Look at the user's question and decide which mode to use.

━━━ MODE A: Direct Advice (use when request is clear) ━━━
Return when the user's question is specific enough to answer directly.
Examples of clear requests:
|- "gợi ý bữa sáng cho người giảm cân"
|- "100g ức gà có bao nhiêu calories"
|- "tôi bị tiểu đường, ăn gì tốt"
|- "thực đơn 1 ngày cho người tập gym"

━━━ MODE B: Clarification (use when request is vague/ambiguous) ━━━
Return ONLY when the request is too vague to give accurate advice.
Examples of vague requests:
|- "nên ăn gì?" (no goal, no meal type)
|- "giảm cân sao?" (no specifics about current state)
|- "meal plan" (no timeframe, no goal)
|- "hôm nay ăn gì" (no meal type, no goal)
|- "cho mình xin" (incomplete)

IN THIS MODE, set needs_clarification: true and generate 2-4 options.

━━━ Decision Rules ━━━
- Does the question have a clear goal? (giảm cân/tăng cơ/giữ dáng)
- Does the question specify a meal type? (sáng/trưa/tối/snack)
- Does the question specify a food or dish? (cụ thể: ức gà, cơm, phở)
- Is the question specific enough for actionable advice?

YES to 2+ of the above → MODE A (direct advice)
NO to 2+ of the above → MODE B (clarification)

━━━ MODE A — Calorie and Macro Rules ━━━
CRITICAL: When the MACRO CALCULATOR block appears in the user prompt,
you MUST use those exact algorithmic values. Do NOT invent, round, or
override BMR, TDEE, target_calories, protein_g, carb_g, or fat_g.
These are computed with the Mifflin-St Jeor equation and are more accurate
than estimates.

Meal suggestions MUST use familiar Vietnamese dishes and estimate realistic
weights (g, bowls, plates) that fit within the given macro targets.
Examples: Phở gà (1 tô ≈ 350g, 450 kcal), Cơm tấm (1 đĩa ≈ 400g, 550 kcal),
Ức gà áp chảo (150g ≈ 200 kcal, 40g protein), Canh cải thịt bằm (1 tô ≈ 200g).

━━━ Output Schema ━━━
MODE A (direct advice) — return this JSON:
{{
  "needs_clarification": false,
  "nutrition_advice": {{
    "meal_suggestions": [
      {{
        "meal_type": "bữa sáng",
        "suggestion": "Phở gà 1 tô (350g)",
        "why": "Giàu protein, quen thuộc với người Việt",
        "estimated_kcal": 450,
        "protein_g": 35,
        "carb_g": 45,
        "fat_g": 12,
        "estimated_weight_g": 350,
        "alternatives": ["Bún bò Huế", "Mì Quảng"]
      }}
    ],
    "foods_to_avoid_today": [...],
    "nutrition_gaps": [],
    "daily_kcal_target": <from MACRO CALCULATOR>,
    "hydration_note": "...",
    "user_facing_summary": "2-3 câu tiếng Việt"
  }}
}}

MODE B (clarification) — return this JSON:
{{
  "needs_clarification": true,
  "clarification_question": "Bạn muốn hướng nào? (max 60 chars Vietnamese)",
  "clarification_hint": "Mình cần rõ hơn để tư vấn đúng (max 100 chars Vietnamese, optional)",
  "clarification_options": [
    {{"id": "meal_plan", "label": "Lên thực đơn", "description": "..."}},
    {{"id": "calorie_check", "label": "Tính calories", "description": "..."}}
  ],
  "confidence": 0.3,
  "reason": "internal reason not shown to user (optional)"
}}

━━━ Option Generation Rules ━━━
- ALWAYS 2–4 options. NEVER 1. NEVER more than 4.
- Labels must be SHORT (3-6 words Vietnamese).
- Each option must be DISTINCT and non-overlapping.
- Consider what information is MISSING:
  - Missing goal? → Options about goals (giảm cân / tăng cơ / giữ dáng / ăn healthy)
  - Missing meal type? → Options about meal types (sáng / trưa / tối / snack)
  - Missing food? → Options about food categories or specific dishes
  - Multiple topics? → Options for each topic (dinh dưỡng / tập luyện / sức khỏe)
- Avoid generic wording: use specific, actionable labels.
- The AI's final response will depend on the selected option.

━━━ Hard Rules ━━━
- NEVER suggest foods on the allergen or hard_avoid list
- ALWAYS respect health restrictions from Health Monitor
- NEVER invent calorie or macro numbers — use MACRO CALCULATOR values
- Output ONLY valid JSON. No explanation. No markdown fences.
- If you choose MODE B (clarification), you MUST include 2-4 clarification_options.
- confidence must be between 0.0 and 1.0.
"""

    def _build_prompt(self, **kwargs) -> str:
        parts = [f"User question: {kwargs['user_message']}\n"]

        # ── Mode A: Inject algorithmic macro results before LLM ────────────────
        macro_data = kwargs.get("macro_data")
        if macro_data:
            parts.append(self._format_macro_tool_result(macro_data))

        # Use rich context when available
        full_ctx = kwargs.get("full_context")
        if full_ctx:
            from app.agents.prompt_builder import build_nutrition_advisor_context
            parts.append(build_nutrition_advisor_context(full_ctx))
        else:
            profile = kwargs.get("profile")
            if profile:
                gender_val = profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender)
                parts.append(f"DEMOGRAPHICS: Age: {profile.date_of_birth} | Gender: {gender_val} | Height: {profile.height_cm}cm | Weight: {profile.current_weight_kg}kg")

            active_goal = kwargs.get("active_goal")
            if active_goal:
                goal_type = active_goal.goal_type.value if hasattr(active_goal.goal_type, "value") else str(active_goal.goal_type)
                parts.append(f"GOAL: {goal_type} | Daily Target: {active_goal.daily_calorie_target} kcal (P: {active_goal.protein_target_g}g, C: {active_goal.carb_target_g}g, F: {active_goal.fat_target_g}g)")

            if kwargs["hard_avoid"]:
                parts.append(f"HARD AVOID (allergies/restrictions): {', '.join(kwargs['hard_avoid'])}")

            demo_disclaimer = kwargs.get("demographic_disclaimer", "")
            demo_restrictions = kwargs.get("demographic_restrictions") or []
            if demo_disclaimer:
                parts.append(f"\nDEMOGRAPHIC SAFETY NOTE: {demo_disclaimer}")
            if demo_restrictions:
                parts.append(f"DEMOGRAPHIC RESTRICTIONS (never suggest): {', '.join(demo_restrictions)}")

            if kwargs["taste_prefs"]:
                dominant = [k for k, v in kwargs["taste_prefs"].items() if isinstance(v, (int, float)) and v >= 4]
                if dominant:
                    parts.append(f"Likes: {', '.join(dominant)} flavors")
            if kwargs["favorite_foods"]:
                parts.append(f"Favorite foods: {', '.join(kwargs['favorite_foods'][:5])}")
            if kwargs["disliked_foods"]:
                parts.append(f"Dislikes: {', '.join(kwargs['disliked_foods'][:5])}")
            if kwargs["recent_foods"]:
                parts.append(f"Already ate recently (avoid repeating): {', '.join(set(kwargs['recent_foods'][:8]))}")

        query_hint = ""
        if kwargs["is_meal_plan"]:
            query_hint = "User wants a full meal plan."
        elif kwargs["is_specific_food"]:
            query_hint = "User asking about a specific food safety/suitability."
        if query_hint:
            parts.append(query_hint)

        return "\n".join(parts)

    def _verify_no_allergens(self, data: dict, hard_avoid: list) -> dict:
        """Remove any suggestion that contains an allergen or its synonym. Safety net."""
        if not hard_avoid or not data.get("meal_suggestions"):
            return data

        # hard_avoid is already expanded at source. Expand again here for defensive
        # safety — catches any terms passed in from other code paths that
        # weren't expanded.
        expanded_terms: set[str] = set()
        for allergen in hard_avoid:
            for term in _expand_allergens(allergen):
                expanded_terms.add(term.lower())

        clean_suggestions = []
        flagged_suggestions = []

        for s in data["meal_suggestions"]:
            suggestion_text = (
                s.get("suggestion", "") + " " +
                s.get("preparation", "") + " " +
                " ".join(s.get("alternatives", []))
            ).lower()

            has_allergen = any(
                term in suggestion_text
                for term in expanded_terms
            )

            if has_allergen:
                flagged_suggestions.append(s)
                logger.info(
                    "[NutritionAdvisor] Filtered allergen in: %s",
                    s.get("suggestion", "")[:50],
                )
            else:
                clean_suggestions.append(s)

        data["meal_suggestions"] = clean_suggestions

        # Fallback if ALL suggestions were removed by allergen filtering
        if not clean_suggestions and flagged_suggestions:
            logger.warning(
                "[NutritionAdvisor] ALL suggestions filtered by allergens. "
                "Allergens: %s. Returning safe fallback.",
                hard_avoid,
            )
            clean_suggestions = [
                {
                    "meal_type": "any",
                    "suggestion": "Cháo trắng với rau củ luộc",
                    "why": (
                        "Món ăn an toàn, không chứa các thành phần gây dị ứng phổ biến, "
                        "dễ tiêu và bổ dưỡng"
                    ),
                    "estimated_kcal": 200,
                    "key_nutrients": ["carbohydrates", "fiber", "vitamins"],
                    "preparation": (
                        "Nấu cháo gạo trắng với nước, thêm cà rốt và khoai tây luộc"
                    ),
                    "alternatives": ["Bánh mì trắng", "Khoai lang hấp", "Bún tươi"]
                }
            ]
            data["user_facing_summary"] = (
                "Do các hạn chế dị ứng của bạn, mình gợi ý các món ăn đơn giản và an toàn. "
                + (data.get("user_facing_summary") or "")
            )
            data["meal_suggestions"] = clean_suggestions

        return data

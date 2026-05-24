"""
Agent 3 — Nutrition Advisor.

Personalized nutrition advice and meal suggestions based on:
- User's profile (allergies, dietary restrictions, preferences)
- Health Monitor output (nutritional needs, restrictions)
- Nutrition memory (recent meals, foods to avoid)
- Key facts from conversation history

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

logger = logging.getLogger(__name__)


class NutritionAdvisorAgent(BaseAgent):
    name = "nutrition_advisor"

    MEAL_PLAN_KEYWORDS = [
        "thực đơn", "kế hoạch ăn", "ăn gì", "gợi ý bữa",
        "nên ăn", "bữa sáng", "bữa trưa", "bữa tối"
    ]
    SPECIFIC_FOOD_KEYWORDS = [
        "có nên ăn", "ăn được không", "độc không",
        "an toàn không", "có hại không", "tốt không"
    ]

    async def run(self, context: AgentContext, db: AsyncSession) -> AgentResult:
        run = self._log_start(
            context=context,
            trigger="nutrition_keyword_detected",
            input_summary=context.current_message[:200],
            db=db,
        )
        start_time = time.time()

        try:
            # 1. Get nutrition memory + profile
            memory_ctx = await get_memory_context_for_agent(
                context.user.id, "nutrition_advisor", db
            )
            profile = context.profile

            # 2. Get health_monitor result from context if available
            health_result = getattr(context, "agent_results", {}).get("health")
            health_restrictions = []
            nutritional_needs = {}
            if health_result and health_result.success:
                health_restrictions = (
                    health_result.content.get("nutritional_needs", {})
                    .get("avoid", [])
                )
                nutritional_needs = health_result.content.get("nutritional_needs", {})

            # 3. Build hard constraints (NEVER suggest these)
            hard_avoid = []
            if profile:
                if hasattr(profile, "allergies") and profile.allergies:
                    hard_avoid.extend([a["allergen"] for a in profile.allergies if isinstance(a, dict)])
                if hasattr(profile, "dietary_restrictions") and profile.dietary_restrictions:
                    hard_avoid.extend(profile.dietary_restrictions)

            # 4. Build soft constraints (avoid today)
            soft_avoid = list(health_restrictions)
            nutrition_mem = memory_ctx.get("nutrition_memory") or {}
            foods_to_avoid = nutrition_mem.get("foods_to_avoid", [])
            soft_avoid.extend([f["food"] for f in foods_to_avoid if isinstance(f, dict)])

            # 5. Build preference context
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

            # 6. Recent meals (avoid suggesting same food within 24h)
            recent_meals = nutrition_mem.get("recent_meals", [])[:7]
            recent_foods = []
            for meal in recent_meals:
                if isinstance(meal, dict):
                    recent_foods.extend(meal.get("items", []))

            # 7. Key facts (health-related)
            key_facts = memory_ctx.get("key_facts") or []
            health_facts = [
                f["fact"] for f in key_facts
                if f.get("confidence") in ("high", "medium")
            ]

            # 8. Detect query type
            msg_lower = context.current_message.lower()
            is_meal_plan = any(kw in msg_lower for kw in self.MEAL_PLAN_KEYWORDS)
            is_specific_food = any(kw in msg_lower for kw in self.SPECIFIC_FOOD_KEYWORDS)

            # 9. Build prompt
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
            )

            # 10. Call AI
            raw = await self._call_ai(
                system_prompt=self._system_prompt(),
                user_prompt=prompt,
                response_format="text",
                max_tokens=800
            )

            # 11. Parse safely
            result_data = self._parse_json_safe(raw)

            # 12. Safety check — verify no allergens in suggestions
            result_data = self._verify_no_allergens(result_data, hard_avoid)

            # 13. Build memory updates
            memory_updates = {}
            if result_data.get("nutrition_gaps"):
                memory_updates = {
                    "nutrition_memory": {
                        "common_deficiencies": result_data["nutrition_gaps"]
                    }
                }

            latency = int((time.time() - start_time) * 1000)
            agent_result = AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="nutrition_recommendation",
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
            logger.error(f"NutritionAdvisorAgent failed: {e}")
            err_result = AgentResult(
                agent_name=self.name, success=False,
                insight_type="nutrition_recommendation", content={},
                confidence=0.0, priority=5, text_for_orchestrator="",
                memory_updates={}, suggested_card=None, error=str(e)
            )
            await self._log_complete(run, err_result, db)
            return err_result

    def _system_prompt(self) -> str:
        return """
You are a certified nutritionist and culinary expert specializing in
Vietnamese and Asian cuisine with deep knowledge of food science.

You know:
- Which foods are harmful in certain health states
  (grapefruit + medications, high-purine + gout, high-potassium + kidney disease)
- Vietnamese traditional medicine food wisdom (tính nhiệt/hàn)
- Practical meals a Vietnamese person can actually find and cook
- Portion science, caloric density, micronutrient optimization
- Food-drug interactions when medications are known

Rules (MUST follow):
- NEVER suggest foods on the allergen or hard_avoid list
- ALWAYS respect health restrictions from Health Monitor
- Prefer foods the user likes when nutritionally equivalent
- Be specific: "100g ức gà luộc" not just "ăn protein"
- Flag food-drug interactions if medications known
- Output ONLY valid JSON. No explanation. No markdown fences.

Schema:
{
  "meal_suggestions": [
    {
      "meal_type": "breakfast|lunch|dinner|snack",
      "suggestion": "...",
      "why": "...",
      "estimated_kcal": 0,
      "key_nutrients": [],
      "preparation": "...",
      "alternatives": []
    }
  ],
  "foods_to_avoid_today": [{"food": "...", "reason": "..."}],
  "nutrition_gaps": [],
  "daily_kcal_target": 0,
  "hydration_note": "...",
  "user_facing_summary": "2-3 câu tiếng Việt"
}
"""

    def _build_prompt(self, **kwargs) -> str:
        parts = [f"User question: {kwargs['user_message']}\n"]
        
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
        if kwargs["soft_avoid"]:
            parts.append(f"Avoid today (health reasons): {', '.join(kwargs['soft_avoid'])}")
        if kwargs["nutritional_needs"].get("increase"):
            parts.append(f"Needs more: {', '.join(kwargs['nutritional_needs']['increase'])}")
        if kwargs["taste_prefs"]:
            dominant = [k for k, v in kwargs["taste_prefs"].items() if isinstance(v, (int, float)) and v >= 4]
            if dominant:
                parts.append(f"Likes: {', '.join(dominant)} flavors")
        if kwargs["cuisine_prefs"]:
            parts.append(f"Preferred cuisines: {', '.join(kwargs['cuisine_prefs'][:3])}")
        if kwargs["favorite_foods"]:
            parts.append(f"Favorite foods: {', '.join(kwargs['favorite_foods'][:5])}")
        if kwargs["disliked_foods"]:
            parts.append(f"Dislikes: {', '.join(kwargs['disliked_foods'][:5])}")
        if kwargs["recent_foods"]:
            parts.append(f"Already ate recently (avoid repeating): {', '.join(set(kwargs['recent_foods'][:8]))}")
        if kwargs["health_facts"]:
            parts.append(f"Known facts: {'; '.join(kwargs['health_facts'][:3])}")

        query_hint = ""
        if kwargs["is_meal_plan"]:
            query_hint = "User wants a full meal plan."
        elif kwargs["is_specific_food"]:
            query_hint = "User asking about a specific food safety/suitability."
        if query_hint:
            parts.append(query_hint)

        return "\n".join(parts)

    def _verify_no_allergens(self, data: dict, hard_avoid: list) -> dict:
        """Remove any suggestion that contains an allergen. Safety net."""
        if not hard_avoid or not data.get("meal_suggestions"):
            return data
        clean_suggestions = []
        for s in data["meal_suggestions"]:
            suggestion_text = (
                s.get("suggestion", "") + " " +
                s.get("preparation", "") + " " +
                " ".join(s.get("alternatives", []))
            ).lower()
            if not any(a.lower() in suggestion_text for a in hard_avoid):
                clean_suggestions.append(s)

        # Fallback if ALL suggestions were removed by allergen filtering
        if not clean_suggestions and data.get("meal_suggestions"):
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

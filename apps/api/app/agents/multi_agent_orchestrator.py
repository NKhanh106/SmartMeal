"""
Multi-Agent Orchestrator.

Routes every user message to the right specialist agents, runs them in
parallel, and synthesizes a coherent response.

Flow:
1. Load shared context (memory, profile, history)
2. Fire ExtractorAgent as fire-and-forget background task
3. Decide which specialist agents to run (keyword + memory-based routing)
4. Run specialists IN PARALLEL (health, nutrition, fitness, research)
5. Check if any agent suggests a clarification card → yield it and stop
6. Build synthesis context from all agent results
7. Call the final AI with synthesis context → stream response

Safety: Health Monitor always runs first for health-related queries.
        No response is sent until at least health is assessed.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, _get_groq_client
from app.ai.circuit_breaker import groq_circuit
from app.agents.extractor_agent import ExtractorAgent
from app.agents.fitness_coach_agent import FitnessCoachAgent
from app.agents.health_monitor_agent import HealthMonitorAgent
from app.agents.memory_service import apply_memory_updates, get_memory_context_for_agent, get_or_create_memory
from app.agents.nutrition_advisor_agent import NutritionAdvisorAgent
from app.agents.web_researcher_agent import WebResearcherAgent
from app.chatbot.context_builder import build_health_context, get_dietary_rules
from app.core.config import settings
from app.core.sanitize import sanitize_for_prompt
from app.core.token_budget import build_context_within_budget, truncate_to_token_budget
from app.models import User
from app.models.chat import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:

    HEALTH_KEYWORDS = [
        "mệt", "đau", "tiêu chảy", "táo bón", "sốt", "buồn nôn",
        "chóng mặt", "căng cơ", "chấn thương", "bệnh", "triệu chứng",
        "khó chịu", "nhức", "viêm", "sưng", "ho", "cảm"
    ]
    NUTRITION_KEYWORDS = [
        "ăn", "uống", "bữa", "thực đơn", "dinh dưỡng", "calories",
        "protein", "gợi ý", "nên ăn", "không nên ăn", "món",
        "thực phẩm", "chế độ ăn", "vitamin", "khoáng chất", "calo"
    ]
    FITNESS_KEYWORDS = [
        "tập", "gym", "cardio", "chạy", "lịch tập", "bài tập",
        "workout", "vận động", "thể dục", "cơ", "sức mạnh",
        "yoga", "bơi", "đạp xe", "thể thao"
    ]
    RESEARCH_TRIGGERS = [
        "mới nhất", "nghiên cứu", "có thật không", "khoa học",
        "so sánh", "review", "tốt nhất hiện nay", "bằng chứng"
    ]

    async def process(
        self,
        user_message: str,
        session_id,
        user: User,
        db: AsyncSession
    ) -> AsyncGenerator[str, None]:

        run_id = str(uuid4())
        start_time = time.time()

        # Sanitize user input at entry point — applies to ALL agents downstream
        sanitized_message = sanitize_for_prompt(user_message, max_length=500)

        # Step 1: Load shared context
        memory = await get_or_create_memory(user.id, db)
        profile = await self._get_user_profile(user.id, db)
        history = await self._get_recent_messages(session_id, limit=10, db=db)

        active_goal = await self._get_active_goal(user.id, db)

        context = AgentContext(
            user=user,
            session_id=str(session_id),
            current_message=sanitized_message,  # sanitized — safe for all agents
            conversation_history=history,
            profile=profile,
            run_id=run_id,
            memory=memory,
            active_goal=active_goal,
        )

        # Step 2: Mark session needs_extraction = True
        await self._mark_needs_extraction(session_id, db)

        # Step 3: Fire extractor as background task (non-blocking)
        asyncio.create_task(
            self._run_extractor_background(context)
        )

        # Step 4: Decide which specialists to run
        msg_lower = sanitized_message.lower()
        run_health    = self._needs_health_check(msg_lower, memory)
        run_nutrition = self._needs_nutrition_advice(msg_lower)
        run_fitness   = self._needs_fitness_advice(msg_lower)
        run_research  = self._needs_research(msg_lower)

        # Step 5: Run needed specialists IN PARALLEL
        agent_results: dict[str, AgentResult] = {}

        if run_health or run_nutrition or run_fitness or run_research:

            # ── PHASE 1: Run HealthMonitor FIRST (others depend on it) ──────────
            if run_health:
                try:
                    health_result = await asyncio.wait_for(
                        HealthMonitorAgent().run(context, db),
                        timeout=4.0  # half the total budget
                    )
                    if health_result.success:
                        agent_results["health"] = health_result
                        if not hasattr(context, "agent_results"):
                            context.agent_results = {}
                        context.agent_results["health"] = health_result
                        if health_result.memory_updates:
                            await apply_memory_updates(
                                context.user.id, health_result.memory_updates, db
                            )
                except asyncio.TimeoutError:
                    logger.warning("[Orchestrator] HealthMonitor timed out after 4s")
                except Exception as e:
                    logger.error(f"[Orchestrator] HealthMonitor failed: {e}")

            # ── PHASE 2: Run remaining agents IN PARALLEL ────────────────────────
            phase2_tasks: dict[str, asyncio.coroutine] = {}
            if run_nutrition:
                phase2_tasks["nutrition"] = NutritionAdvisorAgent().run(context, db)
            if run_fitness:
                phase2_tasks["fitness"] = FitnessCoachAgent().run(context, db)
            if run_research:
                phase2_tasks["research"] = WebResearcherAgent().run(context, db)

            if phase2_tasks:
                # Create actual Task objects so we can inspect them on timeout
                task_map: dict[str, asyncio.Task] = {
                    key: asyncio.create_task(coro)
                    for key, coro in phase2_tasks.items()
                }

                # Wait with timeout — returns (done, pending) sets
                done, pending = await asyncio.wait(
                    task_map.values(),
                    timeout=6.0  # remaining budget
                )

                # Cancel pending tasks cleanly
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass

                # Process completed tasks (even partial results are useful)
                for key, task in task_map.items():
                    if task not in done:
                        continue
                    try:
                        result = task.result()
                        if result and result.success:
                            agent_results[key] = result
                            if not hasattr(context, "agent_results"):
                                context.agent_results = {}
                            context.agent_results[key] = result
                            if result.memory_updates:
                                try:
                                    await apply_memory_updates(
                                        context.user.id, result.memory_updates, db
                                    )
                                except Exception as e:
                                    logger.error(f"[Orchestrator] Memory update failed for {key}: {e}")
                    except Exception as e:
                        logger.error(f"[Orchestrator] Agent '{key}' raised: {e}")

                if pending:
                    pending_keys = [k for k, t in task_map.items() if t in pending]
                    logger.warning(f"[Orchestrator] {len(pending)} agent(s) timed out: {pending_keys}")

        # Step 6: Check if any agent suggests a clarification card
        suggested_card = self._get_highest_priority_card(agent_results)
        if suggested_card:
            yield f"event: card\ndata: {suggested_card.model_dump_json()}\n\n"
            return

        # Step 7: Build synthesis context for final AI call
        synthesis = self._build_synthesis_context(agent_results, memory, profile)

        # Step 8: Final AI call — always happens even if all agents failed/skipped
        system_prompt = self._build_final_system_prompt(synthesis, profile, active_goal, context)

        try:
            async for chunk in self._stream_final_response(
                system_prompt=system_prompt,
                messages=history + [{"role": "user", "content": sanitized_message}],
                db=db,
                session_id=session_id,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"[Orchestrator] Final AI call failed: {e}")
            yield f"data: {json.dumps({'error': 'Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại.'})}\n\n"

        total_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[Orchestrator] Complete in {total_ms}ms — agents ran: {list(agent_results.keys())}")

    # ─── Routing Decisions ───────────────────────────────────────────────

    def _needs_health_check(self, msg: str, memory) -> bool:
        has_keywords = any(kw in msg for kw in self.HEALTH_KEYWORDS)
        has_active_issues = bool(
            memory.health_events and
            any(not e.get("resolved", False) for e in (memory.health_events or []))
        )
        return has_keywords or has_active_issues

    def _needs_nutrition_advice(self, msg: str) -> bool:
        return any(kw in msg for kw in self.NUTRITION_KEYWORDS)

    def _needs_fitness_advice(self, msg: str) -> bool:
        return any(kw in msg for kw in self.FITNESS_KEYWORDS)

    def _needs_research(self, msg: str) -> bool:
        return any(kw in msg for kw in self.RESEARCH_TRIGGERS)

    # ─── Context Building ────────────────────────────────────────────────

    def _build_synthesis_context(self, agent_results: dict, memory, profile) -> str:
        sections: list[tuple[str, str, int]] = []

        if "health" in agent_results:
            h = agent_results["health"].content
            status = h.get("current_status", {}).get("overall", "unknown")
            issues = [i["issue"] for i in h.get("active_issues", [])]
            note = agent_results["health"].text_for_orchestrator
            sections.append((
                "HEALTH STATE",
                f"Overall: {status}\nActive issues: {', '.join(issues) if issues else 'none'}\n{note}",
                1,
            ))

        if "nutrition" in agent_results:
            n = agent_results["nutrition"].content
            summary = n.get("user_facing_summary", "")
            avoid = [f["food"] for f in n.get("foods_to_avoid_today", []) if isinstance(f, dict)]
            gaps = n.get("nutrition_gaps", [])
            sections.append((
                "NUTRITION GUIDANCE",
                f"{summary}\nAvoid today: {', '.join(avoid) if avoid else 'none'}\nGaps: {', '.join(gaps) if gaps else 'none'}",
                2,
            ))

        if "fitness" in agent_results:
            f_res = agent_results["fitness"].content
            rec = f_res.get("workout_recommendation", {})
            sections.append((
                "FITNESS GUIDANCE",
                f"{rec.get('type', 'unknown')} — {rec.get('title', '')}\n{f_res.get('user_facing_summary', '')}",
                3,
            ))

        if "research" in agent_results:
            findings = agent_results["research"].content.get("findings", [])
            if findings:
                finding_texts = [f["finding"] for f in findings[:2] if isinstance(f, dict)]
                sections.append(("RESEARCH FINDINGS", "\n".join(finding_texts), 4))

        # Always include user memory summary (lowest priority)
        mem_parts = []
        if memory.key_facts:
            high_conf = [
                f["fact"] for f in (memory.key_facts or [])
                if f.get("confidence") == "high"
            ][:4]
            if high_conf:
                mem_parts.append(f"Known facts: {'; '.join(high_conf)}")
        if memory.body_snapshot:
            snap = memory.body_snapshot
            if snap.get("digestion_status") and snap["digestion_status"] != "normal":
                mem_parts.append(f"Digestion: {snap['digestion_status']}")
            sore = snap.get("muscle_status", {}).get("sore_areas", [])
            if sore:
                mem_parts.append(f"Sore areas: {', '.join(sore)}")
        if mem_parts:
            sections.append(("USER MEMORY", "\n".join(mem_parts), 5))

        if not sections:
            return "(No specialist context available — respond as general assistant)"

        return build_context_within_budget(sections, total_budget=1500)

    def _build_final_system_prompt(self, synthesis: str, profile, active_goal, context: AgentContext) -> str:
        health_ctx = ""
        dietary_rules = ""
        demo_ctx = ""
        goal_ctx = ""
        if profile:
            try:
                health_ctx = build_health_context(profile)
                rules = get_dietary_rules(
                    getattr(profile, "health_conditions", None) or []
                )
                if rules:
                    dietary_rules = "DIETARY CONSTRAINTS:\n" + "\n".join(f"- {r}" for r in rules)
            except Exception as e:
                logger.warning(f"[Orchestrator] build_health_context error: {e}")
            
            # Demographics
            user_name = context.user.full_name or "Người dùng"
            gender_val = profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender)
            demo_ctx = f"Name: {user_name} | Gender: {gender_val} | Height: {profile.height_cm}cm | Weight: {profile.current_weight_kg}kg"
            
        if active_goal:
            goal_type = active_goal.goal_type.value if hasattr(active_goal.goal_type, "value") else str(active_goal.goal_type)
            goal_ctx = f"ACTIVE GOAL: {goal_type}\nTargets: {active_goal.daily_calorie_target}kcal/day (P:{active_goal.protein_target_g}g, C:{active_goal.carb_target_g}g, F:{active_goal.fat_target_g}g)\n"

        disclaimer = ""
        if profile and getattr(profile, "health_conditions", None):
            disclaimer = (
                "\nAlways include at end: "
                "'Đây là gợi ý dinh dưỡng chung. "
                "Hãy tham khảo bác sĩ trước khi thay đổi chế độ ăn.'"
            )

        return f"""Bạn là SmartMeal AI — người bạn đồng hành thông minh về dinh dưỡng và sức khỏe.
Giao tiếp bằng tiếng Việt tự nhiên, thân thiện như một người bạn am hiểu — không cứng nhắc.

THÔNG TIN NGƯỜI DÙNG:
{demo_ctx}
{health_ctx}
{dietary_rules}
{goal_ctx}
PHÂN TÍCH TỪ HỆ THỐNG CHUYÊN GIA:
{synthesis}

QUY TẮC TRẢ LỜI:
- Trả lời tự nhiên như cuộc trò chuyện, KHÔNG phải báo cáo hay danh sách gạch đầu dòng
- Tích hợp thông tin chuyên gia một cách tự nhiên, không trích dẫn trực tiếp
- Nếu có vấn đề sức khỏe → đề cập nhẹ nhàng nhưng rõ ràng
- Tối đa 3-4 đoạn trừ khi người dùng yêu cầu kế hoạch chi tiết
- KHÔNG bao giờ đề cập "agent", "hệ thống chuyên gia", hay "phân tích tổng hợp"
- KHÔNG bao giờ nói "Theo hệ thống của tôi..." hay "Dữ liệu cho thấy..."
{disclaimer}"""

    def _get_highest_priority_card(self, agent_results: dict):
        cards = [
            r.suggested_card for r in agent_results.values()
            if r.suggested_card is not None
        ]
        if not cards:
            return None
        return min(cards, key=lambda c: getattr(c, "priority", 5))

    # ─── Background Tasks ────────────────────────────────────────────────

    async def _run_extractor_background(self, context: AgentContext):
        """
        Background extractor MUST create its own DB session.
        The request session will be closed before this task completes.
        """
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            try:
                result = await ExtractorAgent().run(context, bg_db)
                if result.memory_updates:
                    await apply_memory_updates(context.user.id, result.memory_updates, bg_db)
                await bg_db.commit()
            except Exception:
                await bg_db.rollback()
                logger.exception(f"[Extractor background] failed for user {context.user.id}")

    # ─── Helpers ─────────────────────────────────────────────────────────

    async def _get_user_profile(self, user_id, db: AsyncSession):
        """Load UserProfile for the user."""
        try:
            from sqlalchemy.future import select
            from app.models.user_profile import UserProfile

            result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def _get_active_goal(self, user_id, db: AsyncSession):
        from app.models.nutrition_goal import NutritionGoal
        try:
            result = await db.execute(
                select(NutritionGoal).where(
                    NutritionGoal.user_id == user_id,
                    NutritionGoal.is_active.is_(True),
                )
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def _get_recent_messages(self, session_id, limit: int, db: AsyncSession) -> list:
        """Query last N messages from chat_messages table for this session."""
        try:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .where(ChatMessage.message_type == "text")
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            messages = result.scalars().all()
            return [
                {"role": m.role, "content": m.content}
                for m in reversed(messages)
            ]
        except Exception:
            return []

    async def _mark_needs_extraction(self, session_id, db: AsyncSession):
        try:
            await db.execute(
                update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(needs_extraction=True)
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[Orchestrator] _mark_needs_extraction failed: {e}")

    async def _stream_final_response(
        self,
        system_prompt: str,
        messages: list,
        db: AsyncSession,
        session_id,
    ) -> AsyncGenerator[str, None]:
        """Stream the final synthesized response using Groq streaming."""
        client = _get_groq_client()
        full_response = ""

        try:
            async def _do_stream():
                return await client.chat.completions.create(
                    model=settings.GROQ_TEXT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *messages,
                    ],
                    max_tokens=1024,
                    temperature=0.4,
                    stream=True,
                )

            async with asyncio.timeout(60):
                stream = await groq_circuit.call(_do_stream)

            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_response += delta
                    yield f"data: {json.dumps({'delta': delta})}\n\n"

        except asyncio.TimeoutError:
            logger.error("[Orchestrator] Streaming timed out after 60s")
            yield f"data: {json.dumps({'error': 'Xin lỗi, phản hồi bị gián đoạn. Vui lòng thử lại.'})}\n\n"
        except Exception as e:
            logger.error(f"[Orchestrator] Streaming error: {e}")
            raise

        # Save assistant message to DB
        if full_response:
            try:
                msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    message_type="text",
                )
                db.add(msg)
                await db.commit()
            except Exception as e:
                logger.warning(f"[Orchestrator] Failed to save assistant message: {e}")

        yield f"data: {json.dumps({'done': True})}\n\n"

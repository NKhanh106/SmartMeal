"""
Multi-Agent Orchestrator.

Routes every user message to the right specialist agents, runs them in
parallel, and synthesizes a coherent response.

Execution model (3-phase pipeline):

  Phase 1 — HealthMonitor (sequential, blocking)
    • Runs BEFORE any other agent for every request.
    • Safety gate: if MH crisis detected → hard stop, no nutrition advice sent.
    • Its AgentResult is immediately placed into context.agent_results so
      Phase 2 agents read the health context as soon as it is available.

  Phase 2 — Specialist agents (parallel, fire-and-forget SSE tokens)
    • NutritionAdvisor, FitnessCoach, WebResearcher run concurrently.
    • Each agent runs in its own isolated AsyncSession to avoid SQLAlchemy
      concurrency violations. Memory writes are routed through MemoryWriteEngine
      (single commit point after all Phase 2 agents complete).
    • Results are emitted as SSE "event: agent_result\ndata: {...}\n\n" events
      so the SMA-Eval benchmark runner can extract individual agent outputs.

  Phase 3 — ExtractorAgent (fire-and-forget, Redis queue)
    • Queued via Redis BRPOP after the HTTP response begins streaming.
    • Runs OUTSIDE the request transaction — extracts meals from the chat
      history and writes PENDING MealLog records for Frontend confirmation.
    • Proposals are drained from Redis after the final AI response and
      emitted as SSE "event: update_proposal" events.

Full pipeline (deep/expert mode):
  1. Load shared context (memory, profile, history)
  2. Emit "event: depth\ndata: {...}\n\n"
  3. Mark session needs_extraction = True
  4. Enqueue ExtractorAgent task to Redis queue (deferred — runs AFTER request)
  5. Route & run Phase 1 (HealthMonitor) — sequential, with timeout circuit
  6. Run Phase 2 specialists IN PARALLEL — emit SSE agent_result events
  7. Check for clarification card (anti-loop protection)
  8. Build synthesis context from all agent results
  9. Stream final AI response via SSE "data: {delta: ...}\n\n"
 10. Drain proposals from Redis → emit SSE "event: update_proposal\ndata: {...}\n\n"

Safety: Health Monitor always runs first for health-related queries.
        No response is sent until at least health is assessed.

Concurrency: Extraction runs via Redis queue (extractor_queue_worker_loop in background.py)
             to prevent races with Phase 1/Phase 2 agents writing UserMemory.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.base import AgentContext, AgentResult, _get_groq_client
from app.agents.depth_config import DepthConfig, ResponseDepth, get_depth_config
from app.ai.circuit_breaker import groq_circuit
from app.agents.fitness_coach_agent import FitnessCoachAgent
from app.agents.health_monitor_agent import (
    HealthMonitorAgent,
    URGENT_KEYWORDS,
    MENTAL_HEALTH_CRISIS_KEYWORDS,
    _is_negated,
)
from app.agents.memory_service import (
    MemoryWriteEngine,
    apply_memory_updates,
    get_memory_context_for_agent,
    get_or_create_memory,
)
from app.agents.nutrition_advisor_agent import NutritionAdvisorAgent
from app.agents.web_researcher_agent import WebResearcherAgent
from app.chatbot.context_builder import build_health_context, get_dietary_rules
from app.core.background import _active_tasks
from app.core.config import settings
from app.core.sanitize import sanitize_for_prompt
from app.core.token_budget import build_context_within_budget, truncate_to_token_budget
from app.models import User
from app.models.chat import ChatMessage, ChatSession
from app.agents.context_loader import load_full_user_context, detect_sensitive_demographics
from app.core.cache import get_redis
from app.agents.prompt_builder import (
    build_health_monitor_context,
    build_nutrition_advisor_context,
    build_fitness_coach_context,
)
from app.schemas.chat_card import ChatCard

logger = logging.getLogger(__name__)


def _make_health_fallback(reason: str) -> AgentResult:
    """
    Safe fallback when HealthMonitor does not complete.
    Conservative defaults: no specific restrictions, but injects a warning
    into the synthesis context so the final AI knows health context is missing.
    """
    return AgentResult(
        success=False,
        agent_name="health_monitor",
        insight_type="health_status",
        content={
            "current_status": {
                "overall": "unknown",
                "note": f"Health assessment unavailable ({reason}). "
                        "Apply conservative defaults."
            },
            "active_issues": [],
            "nutritional_needs": {
                "avoid": [],
                "prioritize": [],
                "note": "No health-based restrictions available — "
                        "use profile allergies only."
            },
            "fitness_clearance": {
                "status": "unknown",
                "cleared_for": [],
                "avoid": [],
                "note": "Health clearance unavailable — "
                        "suggest low-intensity activities only."
            },
            "alerts": [],
        },
        priority=4,
        confidence=0.0,
        text_for_orchestrator=(
            f"⚠️ Health assessment could not complete ({reason}). "
            "Response generated without real-time health context. "
            "Apply conservative defaults for all recommendations."
        ),
    )


# Maps orchestrator phase-key → canonical agent_name used in FIELD_OWNERSHIP
_AGENT_NAME_MAP: dict[str, str] = {
    "health": "health_monitor",
    "nutrition": "nutrition_advisor",
    "fitness": "fitness_coach",
    "research": "web_researcher",
}


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
        db: AsyncSession,
        session_factory: async_sessionmaker,
        depth: str = "deep",
    ) -> AsyncGenerator[str, None]:

        depth_config = get_depth_config(depth)
        run_id = str(uuid4())
        start_time = time.time()

        # Sanitize user input at entry point — applies to ALL agents downstream
        sanitized_message = sanitize_for_prompt(user_message, max_length=500)

        # Step 1: Load shared context
        memory = await get_or_create_memory(user.id, db)
        profile = await self._get_user_profile(user.id, db)
        history = await self._get_recent_messages(session_id, limit=10, db=db)

        active_goal = await self._get_active_goal(user.id, db)
        full_context = await load_full_user_context(user.id, db)

        # Detect sensitive demographic flags that require special safety handling
        demographic_flags = detect_sensitive_demographics(
            profile=profile,
            memory=memory,
            current_message=sanitized_message,
            full_context=full_context,
        )

        context = AgentContext(
            user=user,
            session_id=str(session_id),
            current_message=sanitized_message,
            conversation_history=history,
            profile=profile,
            run_id=run_id,
            memory=memory,
            active_goal=active_goal,
            depth_config=depth_config,
            full_context=full_context,
            demographic_flags=demographic_flags,
        )

        # Step 2: Emit depth mode indicator to frontend
        yield f"event: depth\ndata: {depth}\n\n"

        # Step 3: Mark session needs_extraction = True
        await self._mark_needs_extraction(session_id, session_factory)

        # Enqueue extractor to Redis queue. The queue worker processes extraction
        # AFTER the HTTP response begins, eliminating the race where the background
        # task wrote PENDING MealLog records while Phase 2 agents were still writing
        # UserMemory (both would conflict if writing to the same transaction).
        from app.core.extractor_queue import extractor_enqueue
        await extractor_enqueue(
            user_id=str(user.id),
            session_id=str(session_id),
            user_message=sanitized_message,
            ai_response="",  # filled by the queue worker using session history
        )

        # ── QUICK MODE: Skip all specialist agents ────────────────────────────
        if depth_config.mode == ResponseDepth.QUICK:
            # Minimal rule-based safety gate — must run even in QUICK mode
            safety_result = await self._quick_safety_precheck(sanitized_message)

            if safety_result:
                card = safety_result.suggested_card
                if card:
                    yield f"event: card\ndata: {card.model_dump_json()}\n\n"
                if safety_result.text_for_orchestrator.startswith("MENTAL HEALTH CRISIS"):
                    # Hard stop for mental health crisis — no nutrition advice
                    # Emit the safety agent result for SMA-Eval before exiting
                    yield f"event: agent_result\ndata: {json.dumps({'agent': 'health', 'success': safety_result.success, 'insight_type': safety_result.insight_type, 'confidence': safety_result.confidence, 'priority': safety_result.priority, 'text_for_orchestrator': safety_result.text_for_orchestrator, 'content': safety_result.content, 'error': safety_result.error}, ensure_ascii=False)}\n\n"
                    return

            safety_note = ""
            if safety_result:
                safety_note = safety_result.text_for_orchestrator

            synthesis = self._build_quick_context(memory, profile)
            system_prompt = self._build_final_system_prompt(
                synthesis, profile, active_goal, context, depth_config,
                safety_note=safety_note,
            )
            async for chunk in self._stream_final_response(
                system_prompt=system_prompt,
                messages=history + [{"role": "user", "content": sanitized_message}],
                session_factory=session_factory,
                session_id=session_id,
                max_tokens=depth_config.final_response_tokens,
                temperature=depth_config.temperature,
            ):
                yield chunk

            # Step 8: Drain proposals from Redis queue (extractor ran in queue worker)
            from app.core.extractor_queue import extractor_drain_proposals
            try:
                proposals = await extractor_drain_proposals(str(user.id), timeout=1.0)
                for proposal_json in proposals:
                    yield f"event: update_proposal\ndata: {proposal_json}\n\n"
            except Exception as e:
                logger.warning(f"[Orchestrator] Failed to drain proposals: {e}")
            return

        # ── DEEP / EXPERT MODE: Run specialist agents ───────────────────────
        msg_lower = sanitized_message.lower()

        # Determine which agents to run based on depth_config + keywords
        should_run_health = (
            depth_config.run_health_monitor and
            self._needs_health_check(msg_lower, memory)
        )
        should_run_nutrition = (
            depth_config.run_nutrition_advisor and
            self._needs_nutrition_advice(msg_lower)
        )
        should_run_fitness = (
            depth_config.run_fitness_coach and
            self._needs_fitness_advice(msg_lower)
        )
        should_run_research = (
            depth_config.run_web_researcher and
            self._needs_research(msg_lower)
        )

        # DEEP MODE: only run the MOST RELEVANT specialist (not all)
        if depth_config.mode == ResponseDepth.DEEP:
            if should_run_nutrition and should_run_fitness:
                should_run_fitness = False

        agent_results: dict[str, AgentResult] = {}

        # ── PHASE 1: Run HealthMonitor FIRST ─────────────────────────────────
        if should_run_health:
            try:
                health_result = await asyncio.wait_for(
                    HealthMonitorAgent().run(context, db),
                    timeout=depth_config.phase1_timeout,
                )
                if health_result.success:
                    agent_results["health"] = health_result
                    context.agent_results = {"health": health_result}
                    if health_result.memory_updates:
                        await apply_memory_updates(
                            context.user.id,
                            health_result.memory_updates,
                            db,
                            agent_name="health_monitor",
                        )
            except asyncio.TimeoutError:
                logger.warning("[Orchestrator] HealthMonitor timed out after "
                              f"{depth_config.phase1_timeout}s — injecting safe fallback")
                health_result = _make_health_fallback(reason="timeout")

            except Exception as e:
                logger.error(f"[Orchestrator] HealthMonitor failed: {e}")
                health_result = _make_health_fallback(reason="error")

            # Set context for Phase 2 — use the real result when available,
            # fall back to safe defaults when health did not complete.
            if "health" not in context.agent_results:
                context.agent_results["health"] = health_result

        # Release the initial session — all subsequent DB writes use session_factory
        await db.close()

        # ── PHASE 2: Run remaining agents IN PARALLEL ──────────────────────
        # Each agent must run in its own AsyncSession to avoid SQLAlchemy 2.0
        # concurrency violations (AsyncSession is not safe to share across tasks).
        #
        # Phase 2 agents are READ-ONLY. They generate responses and memory_proposals,
        # but do NOT write to DB directly. All memory writes go through
        # MemoryWriteEngine.commit() after agents complete.
        # This eliminates parallel race conditions and enforces single write point.

        # Centralized write engine for Phase 2
        write_engine = MemoryWriteEngine(context.user.id, session_factory)
        async def _run_agent_isolated(
            agent,
            agent_key: str,
            ctx: AgentContext,
        ) -> tuple[str, AgentResult | None]:
            """Run an agent with its own isolated session + transaction."""
            async with session_factory() as agent_db:
                try:
                    async with agent_db.begin():
                        result = await agent.run(ctx, agent_db)
                    return agent_key, result
                except asyncio.CancelledError:
                    await agent_db.rollback()
                    raise
                except Exception as e:
                    await agent_db.rollback()
                    logger.error("[Orchestrator] Agent '%s' raised in isolated session: %s", agent_key, e)
                    return agent_key, None

        phase2_coroutines: list[tuple[str, asyncio.coroutine]] = []
        if should_run_nutrition:
            phase2_coroutines.append(
                ("nutrition", _run_agent_isolated(NutritionAdvisorAgent(), "nutrition", context))
            )
        if should_run_fitness:
            phase2_coroutines.append(
                ("fitness", _run_agent_isolated(FitnessCoachAgent(), "fitness", context))
            )
        if should_run_research:
            phase2_coroutines.append(
                ("research", _run_agent_isolated(WebResearcherAgent(), "research", context))
            )

        if phase2_coroutines:
            task_map: dict[str, asyncio.Task] = {}
            for key, coro in phase2_coroutines:
                task = asyncio.create_task(coro, name=key)
                _active_tasks.add(task)
                task.add_done_callback(_active_tasks.discard)
                task_map[key] = task
            done, pending = await asyncio.wait(
                task_map.values(),
                timeout=depth_config.phase2_timeout,
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            for key, task in task_map.items():
                if task not in done:
                    continue
                try:
                    result = task.result()
                    if result and result[1] and result[1].success:
                        _, agent_result = result
                        agent_results[key] = agent_result
                        if not hasattr(context, "agent_results"):
                            context.agent_results = {}
                        context.agent_results[key] = agent_result
                        # Route all memory updates through MemoryWriteEngine
                        if agent_result.memory_updates:
                            canonical_name = _AGENT_NAME_MAP.get(key, key)
                            authorized = await write_engine.apply(canonical_name, agent_result.memory_updates)
                            if not authorized:
                                logger.warning(
                                    "[Orchestrator] Phase 2 write blocked for '%s' (unauthorized field)", key
                                )
                except Exception as e:
                    logger.error(f"[Orchestrator] Agent '{key}' raised: {e}")
            if pending:
                pending_keys = [k for k, t in task_map.items() if t in pending]
                logger.warning(f"[Orchestrator] {len(pending)} agent(s) timed out: {pending_keys}")

        # Commit all Phase 2 writes through the single MemoryWriteEngine
        if write_engine.has_pending():
            await write_engine.commit()

        # ── Emit per-agent results as SSE events for SMA-Eval runner ──────────
        # Each agent's structured output is serialised so the benchmark runner can
        # extract individual NutritionAdvisor, FitnessCoach, and HealthMonitor results
        # and pass them to InterAgentConsistencyMetric / TaskDecompositionQualityMetric.
        for agent_key, result in agent_results.items():
            if result is None:
                continue
            payload = {
                "agent": agent_key,
                "success": result.success,
                "insight_type": result.insight_type,
                "confidence": result.confidence,
                "priority": result.priority,
                "text_for_orchestrator": result.text_for_orchestrator,
                "content": result.content,           # dict — parsed JSON from AI
                "error": result.error,
            }
            yield f"event: agent_result\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # Step 5: Anti-loop check — block clarification cards if user just saw one
        clarification_blocked = await self._is_clarification_blocked(
            str(session_id), sanitized_message
        )

        # Step 6: Check if any agent suggests a clarification card
        suggested_card = self._get_highest_priority_card(agent_results)
        if suggested_card:
            # Priority check: clarification cards (trigger_reason=intent_ambiguity)
            # are LOWER priority than safety cards (urgency=urgent/concerning)
            # and LOWER priority than mandatory profile cards.
            is_clarification = (
                suggested_card.trigger_reason in ("intent_ambiguity", "ai_request")
                and getattr(suggested_card, "priority", 5) >= 5
            )
            if is_clarification and clarification_blocked:
                logger.info(
                    "[Orchestrator] Clarification card blocked by anti-loop protection "
                    "for session %s", session_id
                )
                # Fall through to normal response
            else:
                if is_clarification:
                    await self._record_clarification_shown(str(session_id))
                card_type = getattr(suggested_card, "card_type", "unknown")
                card_summary = getattr(suggested_card, "title", str(suggested_card)[:200])
                await self._save_assistant_message(
                    db=db,
                    session_id=session_id,
                    content=f"[card:{card_type}] {card_summary}",
                    message_type="card",
                )
                yield f"event: card\ndata: {suggested_card.model_dump_json()}\n\n"
                return

        # Step 6: Build synthesis context for final AI call
        synthesis = self._build_synthesis_context(agent_results, memory, profile)

        # Step 7: Final AI call
        system_prompt = self._build_final_system_prompt(
            synthesis, profile, active_goal, context, depth_config
        )

        try:
            async for chunk in self._stream_final_response(
                system_prompt=system_prompt,
                messages=history + [{"role": "user", "content": sanitized_message}],
                session_factory=session_factory,
                session_id=session_id,
                max_tokens=depth_config.final_response_tokens,
                temperature=depth_config.temperature,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"[Orchestrator] Final AI call failed: {e}")
            yield f"data: {json.dumps({'error': 'Xin loi, da co loi xay ra. Vui long thu lai.'})}\n\n"

        # Step 8: Drain proposals from Redis queue (extractor ran in queue worker)
        from app.core.extractor_queue import extractor_drain_proposals
        try:
            proposals = await extractor_drain_proposals(str(user.id), timeout=1.0)
            for proposal_json in proposals:
                yield f"event: update_proposal\ndata: {proposal_json}\n\n"
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to drain proposals: {e}")

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
        """
        Fallback rule — if message is ambiguous/short, default to NutritionAdvisor.
        Ensures users always get some response.
        """
        has_keywords = any(kw in msg for kw in self.NUTRITION_KEYWORDS)
        if has_keywords:
            return True
        if len(msg.strip()) < 30:
            return True
        return False

    def _needs_fitness_advice(self, msg: str) -> bool:
        return any(kw in msg for kw in self.FITNESS_KEYWORDS)

    def _needs_research(self, msg: str) -> bool:
        return any(kw in msg for kw in self.RESEARCH_TRIGGERS)

    # ─── Safety Pre-check (QUICK mode) ─────────────────────────────────────

    async def _quick_safety_precheck(
        self,
        message: str,
    ) -> AgentResult | None:
        """
        Lightweight rule-based safety gate for QUICK mode.
        Runs before the final AI call to catch life-threatening keywords.
        Does NOT call AI — pure pattern matching for low latency.
        Returns AgentResult if safety concern found, None if safe to proceed.
        """
        msg_lower = message.lower()

        # Crisis: highest priority — hard stop regardless of mode
        if any(kw in msg_lower for kw in MENTAL_HEALTH_CRISIS_KEYWORDS):
            logger.warning("[QuickSafety] Mental health crisis keyword detected in QUICK mode")
            return AgentResult(
                success=True,
                agent_name="quick_safety",
                insight_type="safety_check",
                content={"current_status": {"overall": "urgent"}},
                priority=1,
                confidence=1.0,
                text_for_orchestrator="MENTAL HEALTH CRISIS DETECTED — do not provide advice",
                suggested_card=ChatCard(
                    card_id="quick_mh_crisis",
                    card_type="confirm",
                    title="Ban khong co don trong dieu nay",
                    subtitle=(
                        "Duong day ho tro tam ly 24/7: "
                        "0963 061 414 (Ngay Mai, mien phi, bao mat), "
                        "0909 658 035 / 0784 604 598 (Cham soc Suc khoe Viet), "
                        "024 3576 5344 (Vien Tam than Quoc gia)."
                    ),
                    trigger_reason="mental_health_crisis",
                    skippable=False,
                ),
            )

        # Physical urgent: emit warning card, do not hard-stop
        urgent_found = [
            kw for kw in URGENT_KEYWORDS
            if kw in msg_lower and not _is_negated(kw, message)
        ]
        if urgent_found:
            logger.warning(
                "[QuickSafety] Urgent physical keywords in QUICK mode: %s",
                urgent_found,
            )
            return AgentResult(
                success=True,
                agent_name="quick_safety",
                insight_type="safety_check",
                content={"current_status": {"overall": "urgent"}},
                priority=1,
                confidence=1.0,
                text_for_orchestrator=(
                    f"WARNING: urgent symptoms: {', '.join(urgent_found)}. "
                    "Include safety reminder in response."
                ),
                suggested_card=ChatCard(
                    card_id="quick_urgent",
                    card_type="confirm",
                    title="Trieu chung can chu y",
                    subtitle=(
                        f"Phat hien: {', '.join(urgent_found)}. "
                        "Lien he bac si hoac goi 115 neu trieu chung "
                        "nghiem trong."
                    ),
                    trigger_reason="urgent_physical_symptom",
                    skippable=True,
                ),
            )

        return None

    # ─── Context Building ───────────────────────────────────────────────

    def _build_quick_context(self, memory, profile) -> str:
        """Minimal context for quick mode — just key facts and active issues."""
        parts = []
        if memory and memory.key_facts:
            high_conf = [
                f["fact"] for f in (memory.key_facts or [])
                if f.get("confidence") == "high"
            ][:3]
            if high_conf:
                parts.append(f"Known: {'; '.join(high_conf)}")
        if memory and memory.body_snapshot:
            snap = memory.body_snapshot
            if snap.get("digestion_status") not in (None, "normal"):
                parts.append(f"Digestion: {snap['digestion_status']}")
        return "\n".join(parts) if parts else ""

    def _build_synthesis_context(self, agent_results: dict, memory, profile) -> str:
        sections: list[tuple[str, str, int]] = []

        if "health" in agent_results:
            h = agent_results["health"].content
            status = h.get("current_status", {}).get("overall", "unknown")
            issues = [i["issue"] for i in h.get("active_issues", [])]
            note = agent_results["health"].text_for_orchestrator

            # If health result contains MH concern flag, prepend empathetic preamble
            # so the final AI acknowledges emotional distress before any advice.
            synthesis_note = note
            if note and note.startswith("[MH CONCERN DETECTED]"):
                synthesis_note = (
                    "USER MAY BE IN EMOTIONAL DISTRESS. "
                    "Begin with 2-3 warm, empathetic sentences that acknowledge their feelings. "
                    "Then suggest professional support if appropriate. "
                    "THEN provide nutrition/fitness advice only after emotional acknowledgment. "
                    + note
                )

            sections.append((
                "HEALTH STATE",
                f"Overall: {status}\nActive issues: {', '.join(issues) if issues else 'none'}\n{synthesis_note}",
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

    def _build_final_system_prompt(
        self,
        synthesis: str,
        profile,
        active_goal,
        context: AgentContext,
        depth_config: DepthConfig | None = None,
        safety_note: str = "",
    ) -> str:
        health_ctx = ""
        dietary_rules = ""
        demo_ctx = ""

        # Use rich context when available
        if context.full_context:
            try:
                health_ctx = build_health_monitor_context(context.full_context)
                if context.full_context.health_risk_flags:
                    dietary_rules = "DIETARY CONSTRAINTS:\n" + "\n".join(
                        f"- {r}" for r in context.full_context.health_risk_flags[:6]
                    )
                # Inject allergy list as a hard constraint. HealthMonitor
                # already short-circuits to "use profile allergies only",
                # but the final LLM call can still recommend allergen
                # recipes if allergies aren't surfaced here.
                if getattr(context.full_context, "allergies", None):
                    allergy_lines = [
                        f"- {a.get('allergen', '?')}" for a in context.full_context.allergies
                    ]
                    if allergy_lines:
                        allergy_rule = (
                            "DANH SÁCH DỊ ỨNG NGHIÊM TRỌNG (TUYỆT ĐỐI KHÔNG gợi ý công thức/món ăn "
                            "có chứa các thành phần dưới đây, dù dưới bất kỳ hình thức nào):\n"
                            + "\n".join(allergy_lines)
                        )
                        dietary_rules = (
                            (dietary_rules + "\n\n" if dietary_rules else "")
                            + allergy_rule
                        )
                user_name = (
                    context.full_context.name
                    if context.full_context and context.full_context.name
                    else "Người dùng"
                )
                demo_ctx = f"Name: {user_name}"
                if context.full_context.gender:
                    demo_ctx += f" | Gender: {context.full_context.gender}"
                if context.full_context.height_cm:
                    demo_ctx += f" | Height: {context.full_context.height_cm}cm"
                if context.full_context.weight_kg:
                    demo_ctx += f" | Weight: {context.full_context.weight_kg}kg"
            except Exception as e:
                logger.warning(f"[Orchestrator] rich context error: {e}")

        elif profile:
            try:
                health_ctx = build_health_context(profile)
                rules = get_dietary_rules(
                    getattr(profile, "health_conditions", None) or []
                )
                if rules:
                    dietary_rules = "DIETARY CONSTRAINTS:\n" + "\n".join(f"- {r}" for r in rules)
            except Exception as e:
                logger.warning(f"[Orchestrator] build_health_context error: {e}")

            user_name = context.user.full_name or "Người dùng"
            gender_val = profile.gender.value if hasattr(profile.gender, "value") else str(profile.gender)
            demo_ctx = f"Name: {user_name} | Gender: {gender_val} | Height: {profile.height_cm}cm | Weight: {profile.current_weight_kg}kg"

        goal_ctx = ""

        if active_goal:
            goal_type = active_goal.goal_type.value if hasattr(active_goal.goal_type, "value") else str(active_goal.goal_type)
            goal_ctx = f"ACTIVE GOAL: {goal_type}\nTargets: {active_goal.daily_calorie_target}kcal/day (P:{active_goal.protein_target_g}g, C:{active_goal.carb_target_g}g, F:{active_goal.fat_target_g}g)\n"

        # Mode-specific persona
        if depth_config is not None:
            persona = {
                "quick": "Bạn là SmartMeal AI — trợ lý dinh dưỡng nhanh và chính xác.",
                "deep": "Bạn là SmartMeal AI — chuyên gia dinh dưỡng và sức khỏe tận tâm.",
                "expert": (
                    "Bạn là SmartMeal AI — chuyên gia dinh dưỡng lâm sàng với kiến thức "
                    "y học, thể thao và dinh dưỡng học chuyên sâu."
                ),
            }
            persona_text = persona.get(depth_config.system_prompt_variant, persona["deep"])
            response_style = depth_config.response_style
        else:
            persona_text = "Bạn là SmartMeal AI — người bạn đồng hành thông minh về dinh dưỡng và sức khỏe."
            response_style = (
                "- Trả lời tự nhiên như cuộc trò chuyện, KHÔNG phải báo cáo hay danh sách gạch đầu dòng\n"
                "- Tích hợp thông tin chuyên gia một cách tự nhiên, không trích dẫn trực tiếp\n"
                "- Tối đa 3-4 đoạn trừ khi người dùng yêu cầu kế hoạch chi tiết"
            )

        disclaimer = ""
        has_conditions = (
            context.full_context.health_conditions if context.full_context
            else (getattr(profile, "health_conditions", None) if profile else None)
        )
        if has_conditions:
            disclaimer = (
                "\nLuôn thêm vào cuối câu trả lời: "
                "'Đây là gợi ý tham khảo. Hãy tham khảo bác sĩ trước khi thay đổi chế độ ăn.'"
            )

        return f"""{persona_text}
Giao tiếp bằng tiếng Việt tự nhiên, thân thiện.

{f"{demo_ctx}" if demo_ctx else ""}
{f"THÔNG TIN SỨC KHỎE NGƯỜI DÙNG:\n{health_ctx}" if health_ctx else ""}
{f"{dietary_rules}" if dietary_rules else ""}
{f"PHÂN TÍCH CHUYÊN GIA:\n{synthesis}" if synthesis else ""}
{f"SAFETY NOTE: {safety_note}" if safety_note else ""}

CÁCH TRẢ LỜI:
{response_style}

TUYỆT ĐỐI KHÔNG đề cập "agent", "hệ thống", "phân tích tổng hợp" với người dùng.

QUY TẮC AN TOÀN DINH DƯỠNG (BẮT BUỘC):
- Khuyến nghị calo hàng ngày KHÔNG ĐƯỢC thấp hơn 85% BMR của người dùng (nếu đã tính). Nếu thiếu thông tin BMR, đề cập "≥1200 kcal/ngày" như mức sàn an toàn cho người lớn.
- Với người có tiền sử/bằng chứng rối loạn ăn uống (nhịn ăn kéo dài, chỉ ăn rau, sợ tăng cân cực đoan), TUYỆT ĐỐI không xác nhận hành vi ăn hạn chế là "tốt/ổn/phù hợp". Thay vào đó, nhẹ nhàng khuyên gặp chuyên gia dinh dưỡng lâm sàng.
{disclaimer}"""

    def _get_highest_priority_card(self, agent_results: dict):
        """
        Return the highest-priority (lowest number) card from agent results.

        Priority values:
          1 = urgent health warning (HIGHEST priority)
          2 = mandatory profile completion
          3 = concerning health
          5 = clarification / intent ambiguity (LOWEST priority)

        Lower number = higher priority = emitted first.
        """
        candidates = []
        for name, result in agent_results.items():
            if result.suggested_card is not None:
                candidates.append((result.priority, result.suggested_card))

        if not candidates:
            return None

        # min by priority number (1 is highest)
        return min(candidates, key=lambda x: x[0])[1]

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

    async def _mark_needs_extraction(
        self,
        session_id,
        session_factory: async_sessionmaker,
    ):
        try:
            async with session_factory() as s:
                await s.execute(
                    update(ChatSession)
                    .where(ChatSession.id == session_id)
                    .values(needs_extraction=True)
                )
                await s.commit()
        except Exception as e:
            logger.warning("[Orchestrator] _mark_needs_extraction failed: %s", e)

    # ─── Anti-Loop Protection ───────────────────────────────────────────────────

    ANTI_LOOP_PREFIX = "clarification_anti_loop"
    MAX_LOOPS_PER_SESSION = 2

    async def _is_clarification_blocked(
        self,
        session_id: str,
        message: str,
    ) -> bool:
        """
        Check if a clarification card should be blocked to prevent loops.

        Block rules:
        1. If user just skipped the last clarification card → block immediately
        2. If user answered a clarification card in last 2 turns → block
        3. Track how many times clarification was shown per session
           (max MAX_LOOPS_PER_SESSION)
        """
        try:
            redis = await get_redis()

            # Rule 1: Check if user recently skipped
            skip_key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:skipped"
            if await redis.exists(skip_key):
                return True

            # Rule 2: Check if user recently answered a clarification
            answer_key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:answered"
            if await redis.exists(answer_key):
                ttl = await redis.ttl(answer_key)
                # Only block if answered very recently (within 3 messages)
                if ttl > -1:  # key exists and has TTL
                    return True

            # Rule 3: Count clarification cards shown this session
            count_key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:count"
            count_raw = await redis.get(count_key)
            if count_raw:
                count = int(count_raw)
                if count >= self.MAX_LOOPS_PER_SESSION:
                    logger.info(
                        "[Orchestrator] Clarification loop limit reached (%d) for session %s",
                        count, session_id
                    )
                    return True

            # Rule 4: Very short responses to clarification questions → block
            if len(message.strip()) <= 10 and message.strip() not in ("a", "b", "c", "d", "1", "2", "3", "4"):
                recent_key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:answered"
                if await redis.exists(recent_key):
                    return True

        except Exception as e:
            logger.warning("[Orchestrator] Anti-loop check failed: %s", e)

        return False

    async def _record_clarification_shown(self, session_id: str) -> None:
        """Record that a clarification card was shown for anti-loop tracking."""
        try:
            redis = await get_redis()
            count_key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:count"
            count_raw = await redis.get(count_key)
            count = int(count_raw) if count_raw else 0
            await redis.setex(count_key, 3600, str(count + 1))
        except Exception as e:
            logger.warning("[Orchestrator] Failed to record clarification shown: %s", e)

    async def record_clarification_skipped(self, session_id: str) -> None:
        """Called when user skips a clarification card — blocks next immediate clarification."""
        try:
            redis = await get_redis()
            key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:skipped"
            await redis.setex(key, 300, "1")  # Block for 5 minutes
        except Exception as e:
            logger.warning("[Orchestrator] Failed to record skipped: %s", e)

    async def record_clarification_answered(self, session_id: str) -> None:
        """Called when user answers a clarification card — blocks rapid follow-up clarifications."""
        try:
            redis = await get_redis()
            key = f"{self.ANTI_LOOP_PREFIX}:{session_id}:answered"
            await redis.setex(key, 600, "1")  # Block for 10 minutes
        except Exception as e:
            logger.warning("[Orchestrator] Failed to record answered: %s", e)

    async def _stream_final_response(
        self,
        system_prompt: str,
        messages: list,
        session_factory: async_sessionmaker,
        session_id,
        max_tokens: int = 1024,
        temperature: float = 0.4,
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
                    max_tokens=max_tokens,
                    temperature=temperature,
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

        # Always save the assistant message using a fresh session —
        # avoids holding a connection open throughout the stream.
        content = full_response if full_response else "[AI response was empty]"
        try:
            async with session_factory() as save_db:
                await self._save_assistant_message(
                    db=save_db,
                    session_id=session_id,
                    content=content,
                )
                await save_db.commit()
        except Exception as e:
            logger.warning("[Orchestrator] Failed to save assistant message: %s", e)

        yield f"data: {json.dumps({'done': True})}\n\n"

    # ─── Persistence ─────────────────────────────────────────────────────────

    async def _save_assistant_message(
        self,
        db: AsyncSession,
        session_id,
        content: str,
        message_type: str = "text",
    ) -> None:
        """Persist an assistant ChatMessage. Called on every exit path to prevent data loss."""
        try:
            msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=content,
                message_type=message_type,
            )
            db.add(msg)
            await db.commit()
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to save assistant message: {e}")

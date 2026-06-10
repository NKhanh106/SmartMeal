"""
Background task concurrency bounding.

All fire-and-forget asyncio tasks and FastAPI BackgroundTasks must go through
this module to avoid exhausting the DB connection pool under burst load.

Architecture:
- BACKGROUND_TASK_SEMAPHORE: module-level Semaphore limits how many background
  tasks can run concurrently across the entire worker process.
- _active_tasks: set of in-flight Task objects, kept alive by a done-callback
  so they are not garbage-collected prematurely.
- create_tracked_task(): replaces asyncio.create_task() for fire-and-forget tasks.
- run_with_semaphore(): wraps a coroutine with semaphore acquisition. Used by
  FastAPI BackgroundTasks via background_tasks.add_task(run_with_semaphore, coro).

The limit is set via BACKGROUND_TASK_CONCURRENCY_LIMIT in config (default 20).
"""

import asyncio
import logging
from typing import Awaitable

from app.core.config import settings

logger = logging.getLogger(__name__)

BACKGROUND_TASK_SEMAPHORE = asyncio.Semaphore(settings.BACKGROUND_TASK_CONCURRENCY_LIMIT)

_active_tasks: set[asyncio.Task] = set()


async def run_with_semaphore(coro: Awaitable, task_name: str) -> None:
    """
    Run a coroutine after acquiring the shared semaphore.

    Used by FastAPI BackgroundTasks via:
        background_tasks.add_task(run_with_semaphore, coro, "task_name")
    """
    waited = BACKGROUND_TASK_SEMAPHORE.locked()
    if waited:
        logger.warning(
            "Background task queued (semaphore at capacity)",
            extra={"task": task_name, "active": len(_active_tasks)},
        )
    async with BACKGROUND_TASK_SEMAPHORE:
        try:
            return await coro
        except asyncio.CancelledError:
            logger.warning("Background task cancelled: %s", task_name)
            raise
        except Exception as e:
            logger.error(
                "Background task failed: %s",
                task_name,
                exc_info=True,
                extra={"task": task_name, "error": str(e)},
            )
            raise


def create_tracked_task(coro: Awaitable, task_name: str) -> asyncio.Task:
    """
    Create and track a fire-and-forget background task.

    Replaces asyncio.create_task() for all background coroutines.
    The task reference is kept in _active_tasks until it completes,
    preventing premature garbage collection and ensuring done-callback
    runs even if nobody awaits the task.

    Use when you want fire-and-forget semantics AND bounded concurrency.
    For tasks that need to block on completion, just await the coroutine
    directly (e.g. in the orchestrator Phase 2 loop).
    """
    task = asyncio.create_task(
        run_with_semaphore(coro, task_name),
        name=task_name,
    )
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)
    return task


# ── Extractor Queue Worker ─────────────────────────────────────────────────────

async def extractor_queue_worker_loop() -> None:
    """
    FIX-6 A4: Background worker that polls the Redis extraction queue.

    Replaces the fire-and-forget create_tracked_task() pattern which raced with
    the main request's transaction. This worker runs in a dedicated background task
    (or can be run as a separate process). It blocks on BRPOP, processes one
    extraction at a time, and stores proposals in Redis for SSE emission.

    The orchestrator drains proposals from Redis after the main response completes,
    ensuring extraction always happens AFTER the request commit — no more race.
    """
    from app.core.extractor_queue import extractor_dequeue, extractor_enqueue_proposal
    from app.db.session import AsyncSessionLocal
    from app.agents.extractor_agent import ExtractorAgent
    from app.agents.memory_service import get_or_create_memory, memory_write_engine
    from app.models.user import User
    from app.models.meal import MealLog
    from app.models.enums import MealLogStatus, MealLogSourceType, MealTypeEnum
    from app.proposal_builder import build_proposals_from_extraction
    from sqlalchemy import select
    from uuid import UUID
    from datetime import datetime

    logger.info("[QueueWorker] Starting extractor queue worker loop")

    while True:
        task = await extractor_dequeue(timeout=5)
        if task is None:
            continue

        logger.info(
            "[QueueWorker] Processing extraction for user %s session %s",
            task.user_id, task.session_id
        )

        # FIX-6: Retry loop for transient failures (DB timeout, AI error, connection pool)
        success = False
        for attempt in range(3):
            try:
                async with AsyncSessionLocal() as db:
                    # Fetch user
                    user_result = await db.execute(
                        select(User).where(User.id == UUID(task.user_id))
                    )
                    researcher_user = user_result.scalar_one_or_none()
                    if not researcher_user:
                        logger.warning(
                            "[QueueWorker] User %s not found, skipping", task.user_id
                        )
                        break  # Permanent failure — don't retry

                    # Load memory
                    memory = await get_or_create_memory(task.user_id, db)

                    # Build conversation history context
                    from app.models.chat import ChatMessage
                    history_result = await db.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == UUID(task.session_id))
                        .order_by(ChatMessage.created_at.desc())
                        .limit(6)
                    )
                    msgs = list(reversed(history_result.scalars().all()))
                    conversation_history = [
                        {"role": m.role, "content": m.content}
                        for m in msgs
                    ]

                    # Build agent context
                    from app.agents.base import AgentContext
                    from app.agents.context_loader import load_full_user_context

                    full_context = await load_full_user_context(task.user_id, db)

                    context = AgentContext(
                        user=researcher_user,
                        session_id=task.session_id,
                        current_message=task.user_message,
                        conversation_history=conversation_history,
                        memory=memory,
                        full_context=full_context,
                    )

                    # Run extraction
                    extractor = ExtractorAgent()
                    result = await extractor.run(context, db)

                    if result.memory_updates:
                        engine = memory_write_engine(task.user_id, AsyncSessionLocal)
                        authorized = engine.apply("extractor", result.memory_updates)
                        if authorized and engine.has_pending():
                            await engine.commit_with_session(db)

                    # FIX-6 PENDING STATE: Create MealLog records for extracted meals.
                    # Status = PENDING so Frontend can show confirmation UI before
                    # calories are actually committed. recalculate_daily_metrics
                    # is intentionally NOT called here — it runs only on APPROVE.
                    extracted = result.content or {}
                    meals = extracted.get("meals") or []
                    for meal in meals:
                        raw_items = meal.get("items") or []
                        if not raw_items:
                            continue

                        # Map chat-extraction meal type to DB enum
                        raw_meal_type = meal.get("meal_type") or "snack"
                        meal_type_map = {
                            "breakfast": "bua_sang",
                            "lunch": "bua_trua",
                            "dinner": "bua_toi",
                            "snack": "an_vat",
                        }
                        meal_type_value = meal_type_map.get(raw_meal_type, "khac")

                        # Aggregate nutritional totals
                        total_cal = sum(i.get("calories", 0) for i in raw_items)
                        total_prot = sum(i.get("protein_g", 0) for i in raw_items)
                        total_carb = sum(i.get("carb_g", 0) for i in raw_items)
                        total_fat = sum(i.get("fat_g", 0) for i in raw_items)

                        new_log = MealLog(
                            user_id=researcher_user.id,
                            meal_type=MealTypeEnum(meal_type_value),
                            meal_time=datetime.fromisoformat(
                                meal.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
                            ).replace(tzinfo=None),
                            source=MealLogSourceType.chat_extraction,
                            status=MealLogStatus.PENDING,
                            extracted_data={
                                "items": raw_items,
                                "total_calories": total_cal,
                                "total_protein_g": total_prot,
                                "total_carb_g": total_carb,
                                "total_fat_g": total_fat,
                                "confidence": meal.get("confidence", "medium"),
                                "session_id": task.session_id,
                            },
                            total_calories=total_cal,
                            total_protein_g=total_prot,
                            total_carb_g=total_carb,
                            total_fat_g=total_fat,
                            ai_model=settings.LLM_MODEL_NAME,
                            ai_confidence=result.confidence,
                        )
                        db.add(new_log)

                    # Store proposals in Redis for SSE emission
                    if result.proposals:
                        for proposal in result.proposals:
                            try:
                                await extractor_enqueue_proposal(
                                    user_id=task.user_id,
                                    proposal_id=proposal.proposal_id,
                                    proposal_json=proposal.model_dump_json(),
                                )
                            except Exception as e:
                                logger.warning(
                                    "[QueueWorker] Failed to store proposal: %s", e
                                )

                    await db.commit()

                    logger.info(
                        "[QueueWorker] Extraction done for user %s session %s "
                        "(confidence=%.2f, proposals=%d)",
                        task.user_id, task.session_id,
                        result.confidence, len(result.proposals) if result.proposals else 0
                    )
                    success = True
                    break

            except asyncio.CancelledError:
                logger.info("[QueueWorker] Cancelled, exiting")
                raise
            except Exception as e:
                if attempt < 2:
                    delay = 0.5 * (2 ** attempt)
                    logger.warning(
                        "[QueueWorker] Transient failure for user %s session %s "
                        "(attempt %d/3): %s — retrying in %.1fs",
                        task.user_id, task.session_id, attempt + 1, e, delay
                    )
                    import asyncio as _asyncio
                    await _asyncio.sleep(delay)
                else:
                    logger.exception(
                        "[QueueWorker] Extraction failed after 3 attempts "
                        "for user %s session %s: %s",
                        task.user_id, task.session_id, e
                    )
                    # Don't retry further — message will be lost, but at least
                    # the worker doesn't crash and keeps processing other tasks

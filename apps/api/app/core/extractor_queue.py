"""
Redis-based async task queue for deferred background execution.

Replaces fire-and-forget create_tracked_task() for write operations that must not
race with the main request's transaction.

Architecture:
- Orchestrator enqueues work via extractor_enqueue() — returns immediately
- Background worker (extractor_queue_worker in background.py) polls BRPOP
- Worker processes one task at a time per worker process
- Proposals emitted via SSE to frontend after extraction completes

Why Redis queue instead of FastAPI BackgroundTasks:
- BackgroundTasks run immediately when enqueued — they race with the main request
- Redis queue ensures tasks are only processed AFTER the main request commits
- BRPOP blocks until a task is available (no busy-polling CPU waste)
- Tasks survive worker restart (enqueued in Redis, not memory)

Queue keys:
- smartmeal:extractor_queue       — pending extraction tasks (LPUSH/BRPOP)
- smartmeal:proposal:{user_id}    — completed proposals per user (SETEX, TTL=600)
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from app.core.cache import get_redis

logger = logging.getLogger(__name__)

# Queue name
EXTRACTOR_QUEUE = "smartmeal:extractor_queue"

# Proposal TTL in Redis (1 hour — long enough for user to confirm/reject)
PROPOSAL_TTL_SECONDS = 3600


@dataclass
class ExtractorTask:
    """One extraction task, serialized as JSON to Redis queue."""
    user_id: str
    session_id: str
    user_message: str
    ai_response: str
    enqueued_at: str  # ISO timestamp for ordering/debugging

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "ExtractorTask":
        data = json.loads(raw)
        return cls(**data)


async def extractor_enqueue(
    user_id: str,
    session_id: str,
    user_message: str,
    ai_response: str,
) -> None:
    """
    Enqueue an extraction task to the Redis queue.

    Call this AFTER the main request commits so the extractor never races
    with in-flight transactions. The background worker will process this task
    after the request has fully completed.

    Failures are logged and best-effort — the task may be retried on next message.
    """
    task = ExtractorTask(
        user_id=str(user_id),
        session_id=str(session_id),
        user_message=user_message,
        ai_response=ai_response,
        enqueued_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    )
    try:
        redis = await get_redis()
        await redis.lpush(EXTRACTOR_QUEUE, task.to_json())
        logger.debug(
            "[Queue] Enqueued extractor task for user %s session %s",
            user_id, session_id
        )
    except Exception as e:
        logger.warning(
            "[Queue] Failed to enqueue extractor task (best-effort): %s", e
        )


async def extractor_dequeue(timeout: int = 5) -> ExtractorTask | None:
    """
    Dequeue one extraction task from the Redis queue (blocking).

    Uses BRPOP — blocks up to `timeout` seconds waiting for a task.
    Returns None if queue is empty after timeout.

    This is called by the background worker loop.
    """
    try:
        redis = await get_redis()
        result = await redis.brpop(EXTRACTOR_QUEUE, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        return ExtractorTask.from_json(raw)
    except Exception as e:
        logger.error("[Queue] Dequeue failed: %s", e)
        return None


async def extractor_enqueue_proposal(
    user_id: str,
    proposal_id: str,
    proposal_json: str,
) -> None:
    """
    Store a completed proposal in Redis for SSE emission.

    The orchestrator polls this key after the main response completes.
    """
    key = f"smartmeal:proposal:{user_id}:{proposal_id}"
    try:
        redis = await get_redis()
        await redis.setex(key, PROPOSAL_TTL_SECONDS, proposal_json)
    except Exception as e:
        logger.warning(
            "[Queue] Failed to store proposal %s for user %s: %s",
            proposal_id, user_id, e
        )


async def extractor_drain_proposals(
    user_id: str,
    timeout: float = 2.0,
) -> list[str]:
    """
    Drain all pending proposals for a user from Redis.

    Called by the orchestrator after the main SSE response is complete.
    Returns list of proposal JSON strings. Idempotent — calling twice
    in the same request returns empty list on second call.
    """
    proposals: list[str] = []

    try:
        redis = await get_redis()
        pattern = f"smartmeal:proposal:{user_id}:*"

        # SCAN to collect keys, then atomically drain all with a Redis pipeline.
        # This prevents concurrent requests from racing — the pipeline executes all
        # GETs in a single round-trip, so keys are collected atomically.
        keys: list[str] = []
        async for key in redis.scan_iter(match=pattern, count=100):
            keys.append(key)

        if not keys:
            return []

        # Drain proposal values without deleting them. The proposal stays in
        # Redis (TTL=600s) so the user can still confirm/reject after receiving
        # the SSE event. The confirm/reject endpoints own the deletion.
        async with redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.get(key)
            results = await pipe.execute()

        for raw in results:
            if raw:
                proposals.append(raw)

        if proposals:
            logger.debug(
                "[Queue] Drained %d proposals for user %s", len(proposals), user_id
            )
    except Exception as e:
        logger.warning("[Queue] Failed to drain proposals for user %s: %s", user_id, e)

    return proposals

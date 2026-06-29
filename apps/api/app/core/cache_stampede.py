"""
Cache stampede prevention helpers.

Provides two mechanisms to prevent thundering herd / cache stampede:

1. Distributed Lock (cache_lock.py):
   - SET NX with TTL ensures only one process regenerates a cache entry.
   - Others wait or fall back to stale/regenerate.

2. Probabilistic Early Expiry:
   - When a cache entry is read and TTL < threshold (10% of original),
     a background refresh is triggered via create_tracked_task.
   - This spreads regeneration over time rather than concentrating it
     at expiry boundaries (cliff-edge).

Usage:
    # With distributed lock (blocks waiters, one regenerates)
    await get_or_regenerate_with_lock(
        cache_key, regenerate_fn,
        lock_key_prefix="regen", lock_ttl=60
    )

    # With probabilistic early expiry (non-blocking background refresh)
    await check_early_expiry_trigger(cache_key, ttl, threshold=0.1, refresh_fn)
"""

import asyncio
import logging
import random
from typing import Callable, Awaitable, Any, TypeVar

from app.core.background import create_tracked_task
from app.core.cache import cache_get, get_redis

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def get_or_regenerate_with_lock(
    cache_key: str,
    regenerate_fn: Callable[[], Awaitable[T]],
    lock_key_prefix: str = "regen",
    lock_ttl: int = 60,
    lock_timeout: float = 5.0,
) -> T:
    """
    Cache-aside pattern with distributed lock for stampede prevention.

    Flow:
    1. Check cache — return immediately if hit.
    2. Acquire distributed lock (only one process enters regeneration).
    3. Double-check cache (another process may have populated it while waiting).
    4. Regenerate if still missing.
    5. On lock timeout: regenerate without caching (degraded but functional).

    Args:
        cache_key: Redis key for the cached value.
        regenerate_fn: Async function that produces the value to cache.
        lock_key_prefix: Prefix for the lock key (e.g. "regen:daily_plan").
        lock_ttl: Lock TTL in seconds (must exceed expected regeneration time).
        lock_timeout: Max seconds to wait for lock acquisition.

    Returns:
        The cached or freshly regenerated value.
    """
    from app.core.cache_lock import CacheLock, CacheLockError

    redis = await get_redis()

    # Fast path: cache hit
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    # Slow path: acquire lock, then double-check and regenerate
    lock_key = f"{lock_key_prefix}:{cache_key}"
    try:
        async with CacheLock(redis, lock_key, ttl=lock_ttl, timeout=lock_timeout):
            # Double-check: another process may have populated the cache
            # while we were waiting for the lock.
            cached = await cache_get(cache_key)
            if cached is not None:
                return cached

            # We won the lock — regenerate
            result = await regenerate_fn()
            return result

    except CacheLockError:
        # Jittered exponential backoff instead of immediate fallback.
        # Each failed waiter retries the cache check with increasing delay + jitter.
        # This prevents the "N-1 stampede" where all waiters regenerate simultaneously.
        # Delays: ~100ms → ~500ms → ~2000ms (+ random jitter).
        import random
        for attempt in range(3):
            delay = 0.1 * (4 ** attempt)  # 0.1, 0.4, 1.6 seconds
            jitter = random.uniform(-0.1, 0.1) * delay  # ±10% jitter
            total_delay = max(0.01, delay + jitter)
            logger.debug(
                "CacheLock timeout — retry %d/3 for '%s' in %.0fms",
                attempt + 1, cache_key, total_delay * 1000,
            )
            await asyncio.sleep(total_delay)
            cached = await cache_get(cache_key)
            if cached is not None:
                logger.info(
                    "Stampede backoff recovered key '%s' on retry %d",
                    cache_key, attempt + 1,
                )
                return cached

        # All retries exhausted — regenerate without caching.
        # Do NOT write to cache to avoid clobbering the lock holder's value.
        logger.warning(
            "CacheLock backoff exhausted for '%s' — regenerating without cache.",
            cache_key,
        )
        return await regenerate_fn()


async def check_and_trigger_early_expiry_refresh(
    cache_key: str,
    original_ttl: int,
    refresh_fn: Callable[[], Awaitable[Any]],
    threshold: float = 0.1,
) -> None:
    """
    Probabilistic early expiry trigger.

    When a cache entry's remaining TTL falls below `threshold` fraction of the
    original TTL, this triggers a background refresh using create_tracked_task.
    This distributes regeneration over time instead of concentrating it at expiry.

    Call this after every cache hit. The refresh is best-effort and does not
    block the caller.

    Args:
        cache_key: The Redis cache key.
        original_ttl: The TTL the entry was stored with (in seconds).
        refresh_fn: Async function to call for background refresh.
        threshold: Fraction of original_ttl below which refresh is triggered. Default 10%.
    """
    redis = await get_redis()
    try:
        ttl_remaining = await redis.ttl(cache_key)
        if ttl_remaining < 0:
            return  # Key doesn't exist or has no TTL

        if ttl_remaining < (original_ttl * threshold):
            logger.debug(
                "Early expiry triggered for '%s' (TTL remaining: %ds < %ds threshold)",
                cache_key, ttl_remaining, int(original_ttl * threshold),
            )
            create_tracked_task(
                refresh_fn(),
                task_name=f"early_refresh:{cache_key}",
            )
    except Exception as e:
        # Non-critical: just log and continue
        logger.warning("Early expiry check failed for '%s': %s", cache_key, e)


async def trigger_background_refresh(
    cache_key: str,
    original_ttl: int,
    regenerate_fn: Callable[[], Awaitable[Any]],
    cache_set_fn: Callable[[Any, int], Awaitable[None]],
    threshold: float = 0.1,
) -> None:
    """
    Convenience: refresh a cache entry in the background.

    Combines early expiry detection with the regeneration function and cache set.

    Args:
        cache_key: Redis key.
        original_ttl: Original TTL used when the entry was stored.
        regenerate_fn: Async function that produces the new value.
        cache_set_fn: Async function(value, ttl) to store the result.
        threshold: Fraction of original_ttl below which refresh is triggered.
    """
    try:
        result = await regenerate_fn()
        await cache_set_fn(result, original_ttl)
        logger.info("Background refresh completed for '%s'", cache_key)
    except Exception as e:
        logger.warning("Background refresh failed for '%s': %s", cache_key, e)

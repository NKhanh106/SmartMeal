"""
Distributed lock for cache stampede prevention.

Uses Redis SET NX (set-if-not-exists) with TTL for lock acquisition.
Implements the "cache-aside with distributed lock" pattern to ensure only
one process regenerates a cache entry while others wait or serve stale.

Usage:
    async with CacheLock(redis, "my-key", ttl=60, timeout=5.0) as lock:
        # only one process enters here
        await do_expensive_work()
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Lua script for safe lock release (only delete if we own the lock)
_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class CacheLockError(Exception):
    """Raised when a lock cannot be acquired within the timeout."""
    pass


class CacheLock:
    """
    A Redis-based distributed lock using SET NX with TTL.

    Attributes:
        redis: Async Redis client.
        key: Base lock key (prefixed with "lock:" internally).
        ttl: Lock TTL in seconds. Must exceed expected regeneration time.
        timeout: Max seconds to wait for lock acquisition.
        token: Unique identifier for this lock holder (used for safe release).
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        key: str,
        ttl: int = 60,
        timeout: float = 5.0,
    ):
        self.redis = redis
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.timeout = timeout
        self.token = str(uuid.uuid4())
        self._acquired = False

    async def acquire(self) -> bool:
        """
        Attempt to acquire the lock within self.timeout.
        Retries every 100ms (50 attempts max = 5s timeout).
        Returns True if acquired, False otherwise.
        """
        max_attempts = max(1, int(self.timeout / 0.1))
        for _ in range(max_attempts):
            result = await self.redis.set(
                self.key,
                self.token,
                nx=True,
                ex=self.ttl,
            )
            if result:
                self._acquired = True
                return True
            await asyncio.sleep(0.1)
        return False

    async def release(self) -> None:
        """Release the lock only if we still own it (safe release)."""
        if not self._acquired:
            return
        try:
            await self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
        except Exception as e:
            logger.warning("Failed to release lock %s (best-effort): %s", self.key, e)
        finally:
            self._acquired = False

    async def __aenter__(self) -> "CacheLock":
        if not await self.acquire():
            raise CacheLockError(
                f"Could not acquire lock '{self.key}' within {self.timeout}s"
            )
        return self

    async def __aexit__(self, *args) -> None:
        await self.release()


@asynccontextmanager
async def cache_lock(
    redis: aioredis.Redis,
    key: str,
    ttl: int = 60,
    timeout: float = 5.0,
) -> AsyncIterator[CacheLock]:
    """
    Async context manager for cache lock acquisition.

    Example:
        async with cache_lock(redis, f"regen:daily_plan:{user_id}", ttl=60) as lock:
            result = await expensive_regeneration()
            await cache_set(cache_key, result, ttl)
    """
    lock = CacheLock(redis, key, ttl=ttl, timeout=timeout)
    try:
        await lock.acquire()
        yield lock
    finally:
        await lock.release()

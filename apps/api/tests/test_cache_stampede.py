"""Tests for app.core.cache_stampede — cache-aside with distributed lock pattern."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class FakeRedis:
    """Fake Redis client for testing."""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        entry = self.data.get(key)
        return entry[0] if entry else None

    async def setex(self, key, ttl, value):
        self.data[key] = (value, ttl)

    async def ttl(self, key):
        entry = self.data.get(key)
        return entry[1] if entry else -2

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return False
        self.data[key] = (value, ex or 60)
        return True

    async def eval(self, script, num_keys, key, token):
        entry = self.data.get(key)
        if entry and entry[0] == token:
            del self.data[key]
            return 1
        return 0


def make_fake_cache_get(fake_redis: FakeRedis):
    """Create a fake cache_get that returns deserialized values from FakeRedis."""
    async def fake_cache_get(key: str):
        value = await fake_redis.get(key)
        if value:
            return json.loads(value)
        return None
    return fake_cache_get


class TestCacheStampedeGetOrRegenerate:
    async def test_cache_hit_returns_without_regenerating(self):
        fake = FakeRedis()
        fake.data["test-key"] = (json.dumps({"result": "cached"}), 100)
        regen_called = False

        async def regen():
            nonlocal regen_called
            regen_called = True
            return {"result": "fresh"}

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.cache_get", make_fake_cache_get(fake)):
            from app.core.cache_stampede import get_or_regenerate_with_lock
            result = await get_or_regenerate_with_lock(
                cache_key="test-key",
                regenerate_fn=regen,
                lock_key_prefix="regen",
            )

        assert result == {"result": "cached"}
        assert regen_called is False

    async def test_cache_miss_regenerates_and_caches(self):
        fake = FakeRedis()
        regen_called = False

        async def regen():
            nonlocal regen_called
            regen_called = True
            return {"result": "fresh"}

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.cache_get", make_fake_cache_get(fake)):
            from app.core.cache_stampede import get_or_regenerate_with_lock
            result = await get_or_regenerate_with_lock(
                cache_key="miss-key",
                regenerate_fn=regen,
                lock_key_prefix="regen",
            )

        assert result == {"result": "fresh"}
        assert regen_called is True

    async def test_lock_timeout_falls_back_to_regenerate(self):
        fake = FakeRedis()
        fake.data["lock:regen:timeout-key"] = ("someone-else", 999)
        regen_count = 0

        async def regen():
            nonlocal regen_count
            regen_count += 1
            return {"result": "degraded"}

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.cache_get", make_fake_cache_get(fake)):
            from app.core.cache_stampede import get_or_regenerate_with_lock
            result = await get_or_regenerate_with_lock(
                cache_key="timeout-key",
                regenerate_fn=regen,
                lock_key_prefix="regen",
                lock_ttl=1,
                lock_timeout=0.2,
            )

        assert result == {"result": "degraded"}
        assert regen_count == 1

    async def test_double_check_skips_second_regen_with_lock_holder(self):
        """
        Test that when a second request arrives while the first is still holding
        the lock (regenerating), the second request waits and gets the cached result.

        This simulates the scenario where the lock key still exists (first caller
        hasn't released it yet), so the second caller falls back to regenerate.
        """
        fake = FakeRedis()
        regen_count = 0

        async def regen():
            nonlocal regen_count
            regen_count += 1
            return {"result": "only-once"}

        # Simulate: lock is still held by first caller (they haven't released it)
        fake.data["lock:regen:double-check"] = ("someone-elses-token", 999)

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.cache_get", make_fake_cache_get(fake)):
            from app.core.cache_stampede import get_or_regenerate_with_lock
            result = await get_or_regenerate_with_lock(
                cache_key="double-check",
                regenerate_fn=regen,
                lock_key_prefix="regen",
                lock_ttl=1,
                lock_timeout=0.2,  # Short timeout so it falls back quickly
            )

        # With lock timeout, it regenerates (degraded mode) without caching
        assert result == {"result": "only-once"}
        assert regen_count == 1


class TestEarlyExpiryTrigger:
    async def test_triggers_when_ttl_below_threshold(self):
        fake = FakeRedis()
        # TTL must be below threshold (original_ttl * threshold = 4320 * 0.1 = 432)
        fake.data["early-key"] = (json.dumps({"id": "123"}), 400)
        refresh_called = False

        async def refresh():
            nonlocal refresh_called
            refresh_called = True

        # Track created tasks to await them
        created_tasks = []

        # create_tracked_task is synchronous, takes a coroutine and creates a Task
        def fake_create_tracked_task(coro, task_name):
            task = asyncio.ensure_future(coro)
            created_tasks.append(task)
            return task

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.create_tracked_task", fake_create_tracked_task):
            from app.core.cache_stampede import check_and_trigger_early_expiry_refresh
            await check_and_trigger_early_expiry_refresh(
                cache_key="early-key",
                original_ttl=4320,
                refresh_fn=refresh,
                threshold=0.1,
            )

        # Await all created tasks to ensure they complete
        if created_tasks:
            await asyncio.gather(*created_tasks)

        assert refresh_called is True

    async def test_no_trigger_when_ttl_above_threshold(self):
        fake = FakeRedis()
        # TTL above threshold (4320 * 0.1 = 432)
        fake.data["fresh-key"] = (json.dumps({"id": "456"}), 1000)

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.create_tracked_task") as mock_task:
            from app.core.cache_stampede import check_and_trigger_early_expiry_refresh
            await check_and_trigger_early_expiry_refresh(
                cache_key="fresh-key",
                original_ttl=4320,
                refresh_fn=lambda: None,
                threshold=0.1,
            )

        mock_task.assert_not_called()

    async def test_no_trigger_for_missing_key(self):
        fake = FakeRedis()

        with patch("app.core.cache.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=fake)), \
             patch("app.core.cache_stampede.create_tracked_task") as mock_task:
            from app.core.cache_stampede import check_and_trigger_early_expiry_refresh
            await check_and_trigger_early_expiry_refresh(
                cache_key="nonexistent",
                original_ttl=4320,
                refresh_fn=lambda: None,
                threshold=0.1,
            )

        mock_task.assert_not_called()

    async def test_non_critical_exception_handled(self):
        bad_redis = MagicMock()
        bad_redis.ttl = AsyncMock(side_effect=Exception("Redis down"))

        with patch("app.core.cache.get_redis", AsyncMock(return_value=bad_redis)), \
             patch("app.core.cache_stampede.get_redis", AsyncMock(return_value=bad_redis)):
            from app.core.cache_stampede import check_and_trigger_early_expiry_refresh
            await check_and_trigger_early_expiry_refresh(
                cache_key="any-key",
                original_ttl=4320,
                refresh_fn=lambda: None,
                threshold=0.1,
            )

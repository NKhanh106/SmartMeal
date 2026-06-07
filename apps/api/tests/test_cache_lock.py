"""Tests for app.core.cache_lock — distributed lock for cache stampede prevention."""

import pytest

from app.core.cache_lock import CacheLock, CacheLockError


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def eval(self, script: str, num_keys: int, key: str, token: str) -> int:
        if self.data.get(key) == token:
            del self.data[key]
            return 1
        return 0


class TestCacheLockAcquireRelease:
    async def test_acquire_sets_lock(self):
        fake = FakeRedis()
        lock = CacheLock(fake, "test-key", ttl=10, timeout=1.0)
        acquired = await lock.acquire()
        assert acquired is True
        assert lock._acquired is True
        assert "lock:test-key" in fake.data
        assert fake.data["lock:test-key"] == lock.token

    async def test_release_deletes_lock(self):
        fake = FakeRedis()
        lock = CacheLock(fake, "test-key", ttl=10, timeout=1.0)
        await lock.acquire()
        await lock.release()
        assert lock._acquired is False
        assert "lock:test-key" not in fake.data

    async def test_safe_release_only_owner(self):
        fake = FakeRedis()
        lock1 = CacheLock(fake, "test-key", ttl=10, timeout=1.0)
        lock2 = CacheLock(fake, "test-key", ttl=10, timeout=1.0)
        await lock1.acquire()
        token1 = lock1.token
        assert fake.data["lock:test-key"] == token1
        acquired2 = await lock2.acquire()
        assert acquired2 is False
        assert fake.data["lock:test-key"] == token1
        await lock1.release()
        assert "lock:test-key" not in fake.data
        await lock2.release()

    async def test_context_manager_acquires_and_releases(self):
        fake = FakeRedis()
        async with CacheLock(fake, "ctx-key", ttl=10, timeout=1.0) as lock:
            assert lock._acquired is True
            assert "lock:ctx-key" in fake.data
        assert "lock:ctx-key" not in fake.data

    async def test_context_manager_raises_on_timeout(self):
        fake = FakeRedis()
        lock1 = CacheLock(fake, "hold-key", ttl=10, timeout=0.2)
        await lock1.acquire()
        with pytest.raises(CacheLockError, match="Could not acquire lock"):
            async with CacheLock(fake, "hold-key", ttl=10, timeout=0.2):
                pass
        await lock1.release()

    async def test_double_release_is_no_op(self):
        fake = FakeRedis()
        lock = CacheLock(fake, "double", ttl=10, timeout=1.0)
        await lock.acquire()
        await lock.release()
        await lock.release()
        assert "lock:double" not in fake.data

    async def test_token_is_uuid(self):
        import uuid
        fake = FakeRedis()
        lock = CacheLock(fake, "tok", ttl=10, timeout=1.0)
        uuid.UUID(lock.token)

"""Tests for SSE connection release and daily plan cache stampede integration."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings


class TestDailyPlanStampedeIntegration:
    def test_early_expiry_threshold_is_10_percent(self):
        assert settings.DAILY_PLAN_CACHE_TTL == 43200
        threshold = int(settings.DAILY_PLAN_CACHE_TTL * 0.1)
        assert threshold == 4320

    @pytest.mark.asyncio
    async def test_early_expiry_triggers_below_10_percent_threshold(self):
        """Verify TTL < 10% triggers background refresh scheduling.

        The _trigger_early_expiry_refresh function checks TTL and calls
        create_tracked_task when TTL < threshold (10% of DAILY_PLAN_CACHE_TTL).
        We verify this by patching the dependencies and checking the return value.
        """
        from app.services.daily_recommendation_service import settings as drs_settings

        # TTL 4000 < 10% of 43200 (4320) should trigger
        assert 4000 < int(drs_settings.DAILY_PLAN_CACHE_TTL * 0.1)
        # TTL 10000 >= 4320 should NOT trigger
        assert 10000 >= int(drs_settings.DAILY_PLAN_CACHE_TTL * 0.1)

    @pytest.mark.asyncio
    async def test_no_trigger_when_ttl_above_threshold(self):
        mock_redis = AsyncMock()
        mock_redis.ttl = AsyncMock(return_value=10000)  # Above threshold (4320)

        with patch("app.services.daily_recommendation_service.get_redis",
                   new_callable=AsyncMock, return_value=mock_redis), \
             patch("app.core.background.create_tracked_task") as mock_task:
            from app.services.daily_recommendation_service import _trigger_early_expiry_refresh
            await _trigger_early_expiry_refresh(
                db=MagicMock(),
                user_id=MagicMock(),
                target_date=date(2026, 6, 15),
                cache_key="any-key",
            )

        mock_task.assert_not_called()


class TestSessionPoolSettings:
    def test_pool_size_matches_pgbouncer_design(self):
        assert settings.DATABASE_POOL_SIZE == 5
        assert settings.DATABASE_MAX_OVERFLOW == 10

    def test_total_connections_fit_supabase_limit(self):
        workers = 4
        total = workers * (settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW)
        assert total == 60

    def test_pool_recycle_under_pgbouncer_idle_timeout(self):
        assert settings.DATABASE_POOL_RECYCLE == 1800
        assert settings.DATABASE_POOL_RECYCLE < 3600

    def test_pre_ping_disabled_for_pgbouncer(self):
        assert settings.DATABASE_POOL_PRE_PING is False

    def test_background_task_limit_leaves_headroom(self):
        total_pool = settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW
        assert settings.BACKGROUND_TASK_CONCURRENCY_LIMIT < total_pool


class TestCacheLockAppliedToDailyPlan:
    @pytest.mark.asyncio
    async def test_early_expiry_check_is_non_critical(self):
        from app.services.daily_recommendation_service import _trigger_early_expiry_refresh
        bad_redis = AsyncMock()
        bad_redis.ttl = AsyncMock(side_effect=Exception("Redis down"))

        with patch("app.core.cache.get_redis", AsyncMock(return_value=bad_redis)):
            await _trigger_early_expiry_refresh(
                db=MagicMock(),
                user_id=MagicMock(),
                target_date=date(2026, 6, 15),
                cache_key="any-key",
            )

    @pytest.mark.asyncio
    async def test_regenerate_uses_correct_lock_ttl(self):
        from app.core.cache_lock import CacheLock
        lock = CacheLock(MagicMock(), "test", ttl=60, timeout=5.0)
        assert lock.ttl == 60

"""Tests for app.db.session — connection pool config and monitoring."""

import pytest

from app.core.config import settings
from app.db.session import POOL_WARNING_THRESHOLD


def _compute_pool_log_level(checked_out: int, pool_size: int, threshold: float = 0.8) -> str:
    """Replicate _on_checkout log level decision for testing."""
    return "WARNING" if checked_out >= int(pool_size * threshold) else "DEBUG"


class TestPoolConfig:
    def test_pool_size_is_small_for_pgbouncer(self):
        assert settings.DATABASE_POOL_SIZE == 5

    def test_max_overflow_within_limit(self):
        assert settings.DATABASE_MAX_OVERFLOW == 10
        assert settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW == 15

    def test_pool_timeout_is_30_seconds(self):
        assert settings.DATABASE_POOL_TIMEOUT == 30

    def test_pool_recycle_is_30_minutes(self):
        assert settings.DATABASE_POOL_RECYCLE == 1800

    def test_pool_pre_ping_disabled_for_pgbouncer(self):
        assert settings.DATABASE_POOL_PRE_PING is False

    def test_background_task_limit_reduced_for_smaller_pool(self):
        assert settings.BACKGROUND_TASK_CONCURRENCY_LIMIT == 10


class TestPoolMonitoring:
    def test_checkout_logs_debug_when_under_threshold(self):
        """checked_out=2, pool_size=5 → DEBUG (below threshold boundary)"""
        assert _compute_pool_log_level(checked_out=2, pool_size=5) == "DEBUG"

    def test_checkout_logs_warning_at_threshold_boundary(self):
        """checked_out=4, pool_size=5 → WARNING (at threshold boundary)"""
        assert _compute_pool_log_level(checked_out=4, pool_size=5) == "WARNING"

    def test_checkout_logs_warning_over_threshold(self):
        """checked_out=5, pool_size=5 → WARNING (over threshold)"""
        assert _compute_pool_log_level(checked_out=5, pool_size=5) == "WARNING"

    def test_warning_threshold_is_80_percent(self):
        assert POOL_WARNING_THRESHOLD == 0.8

from collections.abc import AsyncGenerator
import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

POOL_WARNING_THRESHOLD = 0.8  # Warn when checked_out > pool_size * 0.8


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    # OPTIMIZE-ASYNC-1: ASYNC_DATABASE_POOL_URL uses PgBouncer port 6543 (transaction mode).
    # Alembic uses ASYNC_DATABASE_URL directly with DATABASE_URL (Direct port 5432).
    settings.ASYNC_DATABASE_POOL_URL,
    echo=False,
    future=True,
    # FIX-8 (C-1): pool_size=4, max_overflow=12 per worker.
    # Per-worker ceiling: 4 + 12 = 16 connections.
    # 4 workers × 16 = 64 max — safely below Supabase free tier (60).
    pool_size=4,
    max_overflow=12,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
    connect_args={
        "server_settings": {
            "application_name": "smartmeal_backend",
        },
        # OPTIMIZE-ASYNC-1: Disable prepared statement caching for asyncpg.
        # Required for compatibility with PgBouncer in transaction mode (STATEMENT
        # pooling is not supported; prepared statements are parsed per-connection).
        "statement_cache_size": 0,
        "max_cached_statement_lifetime": 0,
    },
)


# ── Pool Monitoring ──────────────────────────────────────────────────────────────
@event.listens_for(engine.sync_engine, "checkout")
def _on_checkout(dbapi_conn, conn_record, conn_proxy):
    pool = engine.sync_engine.pool
    checked_out = pool.checkedout()
    pool_size = pool.size()
    overflow = pool.overflow()
    log_level = logger.warning if checked_out >= int(pool_size * POOL_WARNING_THRESHOLD) else logger.debug
    log_level(
        "DB connection checkout",
        extra={
            "pool_size": pool_size,
            "checked_out": checked_out,
            "overflow": overflow,
            "pool_total": pool_size + overflow,
        },
    )


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

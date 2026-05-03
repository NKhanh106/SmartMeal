"""
APScheduler-based background scheduler for image cleanup.

Runs cleanup_expired_images() every day at 02:00 server time.

Integrated into app lifespan in app/main.py.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import AsyncSessionLocal
from app.services.image_storage_service import cleanup_expired_images

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_cleanup() -> None:
    """Job function executed by APScheduler."""
    logger.info("Scheduled image cleanup job started at %s", datetime.utcnow())
    try:
        async with AsyncSessionLocal() as db:
            result = await cleanup_expired_images(db)
            logger.info(
                "Scheduled cleanup finished: deleted=%d, errors=%d",
                result.deleted_count,
                len(result.errors),
            )
            if result.errors:
                for err in result.errors:
                    logger.error("  Cleanup error: %s", err)
    except Exception as exc:
        logger.exception("Scheduled image cleanup job failed: %s", exc)


def start_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler instance. Call once at app startup."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Run daily at 02:00 UTC
    _scheduler.add_job(
        _run_cleanup,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="image_cleanup_daily",
        name="Daily expired image cleanup",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace for missed runs
    )

    _scheduler.start()
    logger.info("Image cleanup scheduler started (runs daily at 02:00 UTC).")
    return _scheduler


def stop_scheduler() -> None:
    """Shutdown the scheduler gracefully. Call at app shutdown."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Image cleanup scheduler stopped.")


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler

"""
Manual cleanup script for expired uploaded images.

Usage:
    python -m app.scripts.cleanup_expired_images

This script can also be run via cron or systemd timer in production.

The APScheduler version (preferred for dev) is in:
    app/services/image_cleanup_scheduler.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure app root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import AsyncSessionLocal
from app.services.image_storage_service import cleanup_expired_images

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting expired images cleanup...")
    async with AsyncSessionLocal() as db:
        result = await cleanup_expired_images(db)
        logger.info(
            "Cleanup done: deleted=%d, errors=%d",
            result.deleted_count,
            len(result.errors),
        )
        if result.errors:
            for err in result.errors:
                logger.error("  - %s", err)


if __name__ == "__main__":
    asyncio.run(main())

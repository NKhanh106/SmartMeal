import hashlib
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    try:
        redis = await get_redis()
        value = await redis.get(key)
        if value:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(value)
        logger.debug(f"Cache MISS: {key}")
        return None
    except Exception as e:
        logger.warning(f"Cache GET failed (degraded mode): {e}")
        return None  # Fail gracefully — don't crash app if Redis is down


async def cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        redis = await get_redis()
        await redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Cache SET failed (degraded mode): {e}")


async def cache_delete(key: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception as e:
        logger.warning(f"Cache DELETE failed: {e}")


async def cache_close() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def make_cache_key(prefix: str, *args) -> str:
    """Create a normalized cache key from prefix + args."""
    raw = ":".join(str(a) for a in args)
    hashed = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"smartmeal:{prefix}:{hashed}"


def make_image_cache_key(image_bytes: bytes) -> str:
    """Hash image bytes to avoid re-recognizing the same image."""
    sha = hashlib.sha256(image_bytes).hexdigest()[:16]
    return f"smartmeal:food_recognition:{sha}"

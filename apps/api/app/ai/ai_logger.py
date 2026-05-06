"""
AI Call Logger — structured logging decorator for all AI operations.

Usage:
    from app.ai.ai_logger import log_ai_call

    @log_ai_call(feature="food_recognition")
    async def recognize_food_from_image(...):
        ...
"""

import logging
import time
from functools import wraps

logger = logging.getLogger("smartmeal.ai")


def log_ai_call(feature: str):
    """
    Decorator to log every AI call with latency metrics.

    On success: logs INFO with latency_ms
    On failure: logs ERROR with latency_ms and error type
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                latency_ms = int((time.perf_counter() - start) * 1000)
                logger.info(
                    "AI_CALL_SUCCESS | feature=%s | latency=%dms",
                    feature,
                    latency_ms,
                )
                return result
            except Exception as e:
                latency_ms = int((time.perf_counter() - start) * 1000)
                logger.error(
                    "AI_CALL_FAILED | feature=%s | latency=%dms | error=%s: %s",
                    feature,
                    latency_ms,
                    type(e).__name__,
                    e,
                )
                raise
        return wrapper
    return decorator

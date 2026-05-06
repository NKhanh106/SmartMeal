"""
AI Health Check endpoint — exposes circuit breaker states and Redis connectivity.

This endpoint is used for monitoring:
- Circuit breaker states for Groq and Gemini
- Redis cache connectivity
- Overall AI system health

Accessible without authentication so monitoring tools can probe it.
"""

from fastapi import APIRouter

from app.ai.circuit_breaker import groq_circuit, gemini_circuit
from app.core.cache import get_redis

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/ai", summary="AI System Health Check")
async def ai_health_check():
    """
    Returns the health status of AI providers, circuit breakers, and Redis cache.

    This endpoint does NOT require authentication so monitoring tools
    (e.g. UptimeRobot, Datadog) can probe it without a token.
    """
    redis_ok = False
    redis_error = None
    try:
        redis = await get_redis()
        await redis.ping()
        redis_ok = True
    except Exception as e:
        redis_error = str(e)

    return {
        "status": "ok",
        "providers": {
            "groq": {
                "circuit_state": groq_circuit.state.value,
                "available": groq_circuit.is_available(),
            },
            "gemini": {
                "circuit_state": gemini_circuit.state.value,
                "available": gemini_circuit.is_available(),
            },
        },
        "cache": {
            "redis_connected": redis_ok,
            "status": "active" if redis_ok else f"degraded — {redis_error}",
        },
    }

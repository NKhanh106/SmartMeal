from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.v1 import (
    admin_agents,
    ai_chatbot,
    ai_daily_planner,
    auth,
    dashboard,
    food_nutrition,
    meal_logs,
    nutrition_goals,
    progress_logs,
    user_profiles,
    workout_plans,
)
from app.api.v1 import health as ai_health
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.cache import get_redis, cache_close

# Setup structured logging when not in debug mode
ENV = os.getenv("ENVIRONMENT", "development")
if ENV == "production":
    from app.core.logging_config import setup_logging
    setup_logging()

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up Redis connection
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable — running without cache: {e}")

    # FIX-6 A4: Start the extractor queue worker.
    # This runs as a tracked background task inside the worker process.
    # Each gunicorn worker starts its own worker loop — all share the Redis queue.
    # The worker blocks on BRPOP, so it uses no CPU when idle.
    from app.core.background import extractor_queue_worker_loop, create_tracked_task
    create_tracked_task(
        extractor_queue_worker_loop(),
        task_name="extractor_queue_worker",
    )
    logger.info("[Lifespan] Extractor queue worker started")

    yield

    # Shutdown
    await cache_close()
    logger.info("[Lifespan] Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for SmartMeal nutrition and fitness assistant - Powered by FastAPI",
    lifespan=lifespan,
    # Hide API docs in production
    docs_url="/docs" if ENV != "production" else None,
    redoc_url="/redoc" if ENV != "production" else None,
    openapi_url="/openapi.json" if ENV != "production" else None,
)

# Prometheus metrics instrumentation
if ENV == "production":
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except ImportError:
        logger.warning("prometheus-fastapi-instrumentator not installed — /metrics endpoint disabled")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # connect-src: 'self' for same-origin API calls.
        # api.anthropic.com is included for future Anthropic SDK usage on the backend
        # (Groq calls happen server-side and are not affected by browser CSP).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.anthropic.com; "
            "frame-ancestors 'none'"
        )
        return response


# Security headers middleware MUST be the outermost layer so it sees the final
# response AFTER all other middleware (including CORS) have processed it.
# In Starlette, the last-registered middleware wraps the route closest,
# executing innermost on request and outermost on response.
app.add_middleware(SecurityHeadersMiddleware)

if settings.BACKEND_CORS_ORIGINS:
    cors_origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS]

    # Guard: disallow wildcard "*" with allow_credentials=True per CORS spec.
    # If wildcard is detected, strip it and warn so the server still starts.
    if "*" in cors_origins:
        import warnings
        warnings.warn(
            "BACKEND_CORS_ORIGINS contains '*' — removing wildcard "
            "because allow_credentials=True requires explicit origins.",
            stacklevel=2,
        )
        logger.warning(
            "CORS wildcard '*' detected and removed from allow_origins. "
            "Set explicit BACKEND_CORS_ORIGINS in production."
        )
        cors_origins = [o for o in cors_origins if o != "*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(user_profiles.router, prefix=settings.API_V1_STR)
app.include_router(nutrition_goals.router, prefix=settings.API_V1_STR)
app.include_router(food_nutrition.router, prefix=settings.API_V1_STR)
app.include_router(meal_logs.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(progress_logs.router, prefix=settings.API_V1_STR)
app.include_router(workout_plans.router, prefix=settings.API_V1_STR)
app.include_router(ai_daily_planner.router, prefix=settings.API_V1_STR)
app.include_router(ai_chatbot.router, prefix=settings.API_V1_STR)
app.include_router(admin_agents.router, prefix=settings.API_V1_STR)
# Health check endpoint (no auth required, registered at root level)
app.include_router(ai_health.router)



@app.get("/", tags=["General"])
async def root():
    return {
        "message": "SmartMeal API is running.",
        "version": settings.VERSION,
    }


@app.get("/health", tags=["General"])
async def health_check():
    return {
        "status": "ok",
        "version": settings.VERSION,
    }


@app.get("/health/ready", tags=["General"])
async def readiness_check():
    """
    Readiness probe — checks DB and Redis connectivity.
    Used by load balancers and orchestrators (Kubernetes, Docker Compose healthcheck).
    """
    from app.core.cache import get_redis

    checks: dict = {}

    # DB check — delegated to health.py which has the DB session
    # We do a lightweight check here since we don't have Depends injection
    # in a standalone function. Real DB check lives in health.py /readiness.
    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis check
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"degraded: {e}"

    is_healthy = checks.get("database") == "ok"
    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={
            "status": "ready" if is_healthy else "not_ready",
            "checks": checks,
        },
    )

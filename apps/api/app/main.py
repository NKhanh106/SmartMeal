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

from app.api.v1 import (
    admin_agents,
    ai_chatbot,
    ai_daily_planner,
    ai_meal_update,
    auth,
    dashboard,
    food_nutrition,
    meal_logs,
    nutrition_goals,
    progress_logs,
    uploads,
    user_profiles,
    workout_plans,
)
from app.api.v1 import health as ai_health
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.cache import get_redis, cache_close
from app.services.image_cleanup_scheduler import start_scheduler, stop_scheduler

# Setup structured logging when not in debug mode
ENV = os.getenv("ENVIRONMENT", "development")
if ENV == "production":
    from app.core.logging_config import setup_logging
    setup_logging()

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    # Warm up Redis connection
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable — running without cache: {e}")
    yield
    # Shutdown
    stop_scheduler()
    await cache_close()


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
app.include_router(ai_meal_update.router, prefix=settings.API_V1_STR)
app.include_router(uploads.router, prefix=settings.API_V1_STR)
app.include_router(admin_agents.router, prefix=settings.API_V1_STR)
# Health check endpoint (no auth required, registered at root level)
app.include_router(ai_health.router)

# ── Static files for uploaded images ─────────────────────────────────────────
_upload_dir = Path(settings.UPLOAD_DIR).resolve()
if not _upload_dir.exists():
    _upload_dir.mkdir(parents=True, exist_ok=True)
app.mount(settings.IMAGE_PUBLIC_BASE_URL, StaticFiles(directory=str(_upload_dir)), name="uploads")


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

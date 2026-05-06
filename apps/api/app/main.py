from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
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
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.services.image_cleanup_scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for SmartMeal nutrition and fitness assistant - Powered by FastAPI",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    }

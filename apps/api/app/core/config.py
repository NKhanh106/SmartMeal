from pathlib import Path
from typing import List

from pydantic import AnyHttpUrl, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    config_path = Path(__file__).resolve()
    # Container: /app/app/core/config.py → /app/.env.production
    app_root = config_path.parents[2]
    container_env = app_root / ".env.production"
    container_fallback = app_root / ".env"

    if container_env.exists():
        return str(container_env)
    if container_fallback.exists():
        return str(container_fallback)
    return ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "SmartMeal API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["http://localhost:3000"]

    SECRET_KEY: str = "dev-only-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "smartmeal"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: str = ""
    DATABASE_POOL_URL: str | None = None  # Pooled URL for FastAPI runtime (PgBouncer port 6543)
    TEST_DATABASE_URL: str | None = None

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Async URL for Alembic migrations — always uses DATABASE_URL (Direct, port 5432)."""
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def ASYNC_DATABASE_POOL_URL(self) -> str:
        """
        Async URL for FastAPI runtime — uses DATABASE_POOL_URL if available (PgBouncer port 6543).

        Priority:
          1. DATABASE_POOL_URL  — Pooled connection (recommended for app runtime)
          2. DATABASE_URL        — Direct connection fallback (dev / no pooler configured)

        DATABASE_POOL_URL should include ?pgbouncer=true to signal transaction pooling mode.
        """
        url = self.DATABASE_POOL_URL or self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    AI_MEAL_PROVIDER: str = "gemini"
    AI_CHAT_PROVIDER: str = "groq"
    AI_PLANNER_PROVIDER: str = "groq"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    GROQ_API_KEYS: str | None = None  # Comma-separated list: key1,key2,key3
    GROQ_TEXT_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    @computed_field
    @property
    def GROQ_API_KEYS_LIST(self) -> list[str]:
        """Parse GROQ_API_KEYS into a list of valid keys."""
        if self.GROQ_API_KEYS:
            keys = [k.strip() for k in self.GROQ_API_KEYS.split(",") if k.strip()]
            return keys
        return []

    @computed_field
    @property
    def GROQ_API_KEY(self) -> str | None:
        """Backward compatibility: return first key if available."""
        keys = self.GROQ_API_KEYS_LIST
        return keys[0] if keys else None

    USDA_API_KEY: str = ""

    TAVILY_API_KEY: str = ""
    TAVILY_ENABLED: bool = True


    # ── Redis Cache Settings ──────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 20
    AI_CACHE_TTL_SECONDS: int = 3600          # Cache AI result 1 hour
    FOOD_RECOGNITION_CACHE_TTL: int = 86400   # Cache food recognition 24 hours
    DAILY_PLAN_CACHE_TTL: int = 43200         # Cache daily plan 12 hours

    # ── Database Connection Pool (tuned for Supabase PgBouncer) ───────────────────
    # Supabase uses PgBouncer in transaction mode as a connection pooler.
    # Two-tier pooling: app pool (SQLAlchemy) sits behind PgBouncer pool.
    #
    # Pool settings per worker: pool_size=8, max_overflow=12
    # Sized so a single Phase-2 request running 3 agents concurrently + the
    # extractor queue worker + buffer can all share the pool without serializing
    # on connection checkout (which previously triggered pool-full warnings).
    #
    # Per-worker ceiling: pool_size + max_overflow = 8 + 12 = 20 connections
    # 4 workers × 20 = 80 max — over Supabase free tier (60) by 20; reduce to
    # 3 workers (60 max) if Supabase rejects idle connections.
    #
    # Key settings for transaction-mode PgBouncer:
    # - pool_pre_ping: disabled (PgBouncer handles connection health)
    # - pool_recycle: 30 min (PgBouncer sessions expire after 60 min idle)
    # - connect_args.statement_cache_size = 0 (asyncpg, see session.py)
    #   disables prepared statements — required because PgBouncer cannot share
    #   prepared statements across connections (each statement is parsed per-connection).
    DATABASE_POOL_SIZE: int = 8
    DATABASE_MAX_OVERFLOW: int = 12
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800   # 30 minutes — PgBouncer max idle is 60 min
    DATABASE_POOL_PRE_PING: bool = False

    # ── Background Task Concurrency ─────────────────────────────────────────────
    # bg_limit=4 equals pool_size=4 per worker.
    # With max_overflow=12, the pool provides headroom for the queue worker.
    # Background tasks hold connections for the full LLM call duration (~3-10s),
    # so the semaphore prevents runaway concurrency.
    BACKGROUND_TASK_CONCURRENCY_LIMIT: int = 4


    @model_validator(mode="after")
    def validate_non_dev_secrets(self) -> "Settings":
        env = self.ENVIRONMENT.lower()
        if env in {"production", "prod", "staging"}:
            if self.SECRET_KEY == "dev-only-change-me":
                raise ValueError(
                    "SECRET_KEY must be set to a secure value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters long in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            if not self.DATABASE_URL and self.POSTGRES_PASSWORD == "postgres":
                raise ValueError(
                    "POSTGRES_PASSWORD or DATABASE_URL must be configured outside development."
                )
            # CORS: reject wildcard origins when allow_credentials=True
            if self.BACKEND_CORS_ORIGINS:
                for origin in self.BACKEND_CORS_ORIGINS:
                    if str(origin).strip() == "*":
                        raise ValueError(
                            "CORS origins cannot be '*' when allow_credentials=True in production. "
                            "Specify exact allowed origins."
                        )
        elif env in {"development", "dev"}:
            if self.SECRET_KEY == "dev-only-change-me":
                import logging
                logging.getLogger(__name__).warning(
                    "[SmartMeal] WARNING: SECRET_KEY is using the default dev value. "
                    "Set a secure SECRET_KEY in production environments. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
        return self

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

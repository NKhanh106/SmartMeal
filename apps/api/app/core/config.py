from pathlib import Path
from typing import List

from pydantic import AnyHttpUrl, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    config_path = Path(__file__).resolve()
    api_env = config_path.parents[2] / ".env"
    root_env = config_path.parents[4] / ".env"

    if api_env.exists():
        return str(api_env)
    if root_env.exists():
        return str(root_env)
    return ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "SmartMeal API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["http://localhost:3000"]

    SECRET_KEY: str = "dev-only-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "smartmeal"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str | None = None

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    AI_MEAL_PROVIDER: str = "gemini"
    AI_CHAT_PROVIDER: str = "groq"
    AI_PLANNER_PROVIDER: str = "groq"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    GROQ_API_KEY: str | None = None
    GROQ_TEXT_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    USDA_API_KEY: str = ""

    @model_validator(mode="after")
    def validate_non_dev_secrets(self) -> "Settings":
        env = self.ENVIRONMENT.lower()
        if env in {"production", "prod", "staging"}:
            if self.SECRET_KEY == "dev-only-change-me":
                raise ValueError("SECRET_KEY must be configured outside development.")
            if not self.DATABASE_URL and self.POSTGRES_PASSWORD == "postgres":
                raise ValueError("POSTGRES_PASSWORD or DATABASE_URL must be configured outside development.")
        return self

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

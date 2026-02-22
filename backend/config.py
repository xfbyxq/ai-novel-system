from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen-plus"
    DASHSCOPE_BASE_URL: str = ""  # Coding Plan Pro 的 base URL

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://novel_user:novel_pass@localhost:5432/novel_system"
    DATABASE_URL_SYNC: str = "postgresql://novel_user:novel_pass@localhost:5432/novel_system"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

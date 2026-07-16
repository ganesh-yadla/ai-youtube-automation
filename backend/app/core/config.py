"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    database_url: str
    redis_url: str = Field(default="redis://localhost:6379/0")

    youtube_api_key: str
    anthropic_api_key: str

    trend_cache_ttl_seconds: int = Field(default=43200)  # 12 hours


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()

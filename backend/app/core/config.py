"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    database_url: str
    redis_url: str = Field(default="redis://localhost:6379/0")

    youtube_api_key: str

    llm_provider: Literal["claude", "gemini"] = Field(default="gemini")
    anthropic_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)

    trend_cache_ttl_seconds: int = Field(default=43200)  # 12 hours

    # Relative to the process working directory (backend/, per how uvicorn is
    # run). Holds generated media - audio, images, video/thumbnails.
    media_root: str = Field(default="media")

    # ffmpeg's drawtext filter needs an explicit font file on platforms
    # without a working Fontconfig setup (confirmed via a real crash on
    # Windows: "Fontconfig error: Cannot load default config file"). Leave
    # unset on platforms where ffmpeg resolves a default font on its own
    # (most Linux builds via fontconfig).
    video_font_file: str | None = Field(default=None)

    @model_validator(mode="after")
    def _require_key_for_selected_provider(self) -> "Settings":
        if self.llm_provider == "claude" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude")
        # Unconditional, not just when LLM_PROVIDER=gemini: Voice Generation
        # always uses Gemini's TTS regardless of LLM_PROVIDER, since Claude
        # has no TTS integration.
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required (default LLM provider, and always used for Voice Generation)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()

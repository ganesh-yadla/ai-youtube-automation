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
    frontend_origin: str = Field(default="http://localhost:3000")

    database_url: str
    redis_url: str = Field(default="redis://localhost:6379/0")

    youtube_api_key: str
    youtube_token_path: str = Field(default="token.json")
    youtube_category_id: str = Field(default="28")  # Science & Technology

    llm_provider: Literal["claude", "gemini", "ollama"] = Field(default="gemini")
    anthropic_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    ollama_base_url: str = Field(default="http://localhost:11434")

    # TTS is a separate capability from text generation (LLMClientInterface
    # vs TTSClientInterface) with its own provider choice - e.g. running
    # ollama for scripts doesn't imply local TTS, and vice versa.
    tts_provider: Literal["gemini", "piper"] = Field(default="gemini")
    piper_model_path: str = Field(default="models/piper/en_US-lessac-medium.onnx")

    # Image generation is likewise its own capability/provider choice,
    # independent of llm_provider and tts_provider.
    image_provider: Literal["gemini", "local"] = Field(default="gemini")

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
        gemini_needed = (
            self.llm_provider == "gemini" or self.tts_provider == "gemini" or self.image_provider == "gemini"
        )
        if gemini_needed and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when LLM_PROVIDER, TTS_PROVIDER, or "
                "IMAGE_PROVIDER is set to gemini"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()

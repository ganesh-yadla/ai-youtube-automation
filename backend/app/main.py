"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.exception_handlers import register_exception_handlers
from app.api.v1.dependencies import get_gemini_client, get_llm_client, get_youtube_client
from app.api.v1.routers.scripts import router as scripts_router
from app.api.v1.routers.trends import router as trends_router
from app.api.v1.routers.video import router as video_router
from app.api.v1.routers.voice import router as voice_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await get_youtube_client().close()
    await get_llm_client().close()
    # get_llm_client() only closes this when LLM_PROVIDER=gemini - Gemini is
    # also always used for TTS regardless, so close it unconditionally too.
    # (Same cached instance either way - lru_cache makes this a no-op double
    # reference, not a second live client.)
    await get_gemini_client().close()
    await get_redis_client().aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory: builds and configures the FastAPI instance."""
    settings = get_settings()
    configure_logging(settings.log_level)

    media_root = Path(settings.media_root)
    media_root.mkdir(parents=True, exist_ok=True)

    fastapi_app = FastAPI(
        title="AI Creator OS",
        description="Trend Intelligence API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @fastapi_app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    fastapi_app.include_router(trends_router, prefix="/api/v1")
    fastapi_app.include_router(scripts_router, prefix="/api/v1")
    fastapi_app.include_router(voice_router, prefix="/api/v1")
    fastapi_app.include_router(video_router, prefix="/api/v1")
    fastapi_app.mount("/media", StaticFiles(directory=media_root), name="media")
    register_exception_handlers(fastapi_app)

    return fastapi_app


app = create_app()

"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.v1.dependencies import get_claude_client, get_youtube_client
from app.api.v1.routers.trends import router as trends_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await get_youtube_client().close()
    await get_claude_client().close()
    await get_redis_client().aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory: builds and configures the FastAPI instance."""
    settings = get_settings()
    configure_logging(settings.log_level)

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
    register_exception_handlers(fastapi_app)

    return fastapi_app


app = create_app()

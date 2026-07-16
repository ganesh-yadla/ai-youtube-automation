"""Maps domain exceptions to HTTP responses, centrally, out of the routers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.trend_exceptions import (
    NoTrendingVideosFoundError,
    TrendAnalysisAlreadyExistsError,
    TrendSearchNotFoundError,
    YouTubeAPIError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NoTrendingVideosFoundError)
    async def handle_no_videos_found(_: Request, exc: NoTrendingVideosFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TrendSearchNotFoundError)
    async def handle_search_not_found(_: Request, exc: TrendSearchNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TrendAnalysisAlreadyExistsError)
    async def handle_analysis_already_exists(
        _: Request, exc: TrendAnalysisAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(YouTubeAPIError)
    async def handle_youtube_api_error(_: Request, exc: YouTubeAPIError) -> JSONResponse:
        logger.error("youtube_api_error", extra={"error": str(exc)})
        return JSONResponse(status_code=502, content={"detail": "Upstream YouTube API error"})

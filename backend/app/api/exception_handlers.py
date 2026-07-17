"""Maps domain exceptions to HTTP responses, centrally, out of the routers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.script_exceptions import ScriptNotFoundError, TrendAnalysisRequiredError
from app.exceptions.trend_exceptions import (
    NoTrendingVideosFoundError,
    TrendAnalysisAlreadyExistsError,
    TrendSearchNotFoundError,
    YouTubeAPIError,
)
from app.exceptions.video_exceptions import VideoAlreadyExistsError, VideoNotFoundError
from app.exceptions.voice_exceptions import NarrationAlreadyExistsError, NarrationNotFoundError

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

    @app.exception_handler(TrendAnalysisRequiredError)
    async def handle_analysis_required(_: Request, exc: TrendAnalysisRequiredError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ScriptNotFoundError)
    async def handle_script_not_found(_: Request, exc: ScriptNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(NarrationAlreadyExistsError)
    async def handle_narration_already_exists(_: Request, exc: NarrationAlreadyExistsError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(NarrationNotFoundError)
    async def handle_narration_not_found(_: Request, exc: NarrationNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(VideoAlreadyExistsError)
    async def handle_video_already_exists(_: Request, exc: VideoAlreadyExistsError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(VideoNotFoundError)
    async def handle_video_not_found(_: Request, exc: VideoNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

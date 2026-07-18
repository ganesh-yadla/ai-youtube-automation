"""FastAPI dependency providers - the composition root for the Trend
Intelligence feature. Routers depend on these, never on concrete
implementations directly.
"""

from functools import lru_cache

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.db.session import get_db
from app.infrastructure.external.claude_client import ClaudeClient
from app.infrastructure.external.ffmpeg_assembler import FFmpegVideoAssembler
from app.infrastructure.external.gemini_client import GeminiClient
from app.infrastructure.external.interfaces.image_client import ImageClientInterface
from app.infrastructure.external.interfaces.llm_client import LLMClientInterface
from app.infrastructure.external.interfaces.tts_client import TTSClientInterface
from app.infrastructure.external.interfaces.video_assembler import VideoAssemblerInterface
from app.infrastructure.external.local_image_client import LocalImageClient
from app.infrastructure.external.ollama_client import OllamaClient
from app.infrastructure.external.piper_client import PiperClient
from app.infrastructure.external.youtube_client import YoutubeClient
from app.infrastructure.external.youtube_upload_client import YoutubeUploadClient
from app.repositories.publish_repository import PublishRepository
from app.repositories.script_repository import ScriptRepository
from app.repositories.trend_repository import TrendRepository
from app.repositories.video_repository import VideoRepository
from app.repositories.voice_repository import VoiceRepository
from app.services.ai_analysis_service import AIAnalysisService
from app.services.orchestration_service import OrchestrationService
from app.services.publish_service import PublishService
from app.services.script_service import ScriptService
from app.services.trend_service import TrendService
from app.services.video_service import VideoService
from app.services.voice_service import VoiceService


@lru_cache
def get_youtube_client() -> YoutubeClient:
    return YoutubeClient()


@lru_cache
def get_gemini_client() -> GeminiClient:
    return GeminiClient()


@lru_cache
def get_ollama_client() -> OllamaClient:
    return OllamaClient()


@lru_cache
def get_llm_client() -> LLMClientInterface:
    settings = get_settings()
    if settings.content_language == "te":
        # Script quality was tested for real, side by side: Ollama's Telugu
        # is valid but noticeably rougher than Gemini's for the same
        # prompt - not a place to default to the cheaper local option.
        return get_gemini_client()
    if settings.llm_provider == "gemini":
        return get_gemini_client()
    if settings.llm_provider == "ollama":
        return get_ollama_client()
    return ClaudeClient()


@lru_cache
def get_piper_client() -> PiperClient:
    return PiperClient()


def get_tts_client() -> TTSClientInterface:
    settings = get_settings()
    if settings.tts_provider == "piper":
        return get_piper_client()
    # Shares the connection with get_llm_client() when that's also Gemini.
    return get_gemini_client()


@lru_cache
def get_local_image_client() -> LocalImageClient:
    return LocalImageClient()


def get_image_client() -> ImageClientInterface:
    settings = get_settings()
    if settings.image_provider == "local":
        return get_local_image_client()
    # Shares the connection with get_llm_client() when that's also Gemini.
    return get_gemini_client()


@lru_cache
def get_video_assembler() -> VideoAssemblerInterface:
    settings = get_settings()
    return FFmpegVideoAssembler(font_file=settings.video_font_file)


def get_trend_repository(session: AsyncSession = Depends(get_db)) -> TrendRepository:
    return TrendRepository(session)


def get_trend_service(
    youtube_client: YoutubeClient = Depends(get_youtube_client),
    repository: TrendRepository = Depends(get_trend_repository),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> TrendService:
    return TrendService(
        youtube_client=youtube_client,
        repository=repository,
        redis=redis,
        cache_ttl_seconds=settings.trend_cache_ttl_seconds,
    )


def get_script_repository(session: AsyncSession = Depends(get_db)) -> ScriptRepository:
    return ScriptRepository(session)


def get_ai_analysis_service(
    llm_client: LLMClientInterface = Depends(get_llm_client),
    repository: TrendRepository = Depends(get_trend_repository),
    script_repository: ScriptRepository = Depends(get_script_repository),
) -> AIAnalysisService:
    return AIAnalysisService(
        llm_client=llm_client, repository=repository, script_repository=script_repository
    )


def get_script_service(
    llm_client: LLMClientInterface = Depends(get_llm_client),
    trend_repository: TrendRepository = Depends(get_trend_repository),
    script_repository: ScriptRepository = Depends(get_script_repository),
    settings: Settings = Depends(get_settings),
) -> ScriptService:
    return ScriptService(
        llm_client=llm_client,
        trend_repository=trend_repository,
        script_repository=script_repository,
        content_language=settings.content_language,
    )


def get_voice_repository(session: AsyncSession = Depends(get_db)) -> VoiceRepository:
    return VoiceRepository(session)


def get_voice_service(
    tts_client: TTSClientInterface = Depends(get_tts_client),
    script_repository: ScriptRepository = Depends(get_script_repository),
    voice_repository: VoiceRepository = Depends(get_voice_repository),
    settings: Settings = Depends(get_settings),
) -> VoiceService:
    return VoiceService(
        tts_client=tts_client,
        script_repository=script_repository,
        voice_repository=voice_repository,
        media_root=settings.media_root,
    )


def get_video_repository(session: AsyncSession = Depends(get_db)) -> VideoRepository:
    return VideoRepository(session)


def get_video_service(
    image_client: ImageClientInterface = Depends(get_image_client),
    video_assembler: VideoAssemblerInterface = Depends(get_video_assembler),
    script_repository: ScriptRepository = Depends(get_script_repository),
    voice_repository: VoiceRepository = Depends(get_voice_repository),
    video_repository: VideoRepository = Depends(get_video_repository),
    settings: Settings = Depends(get_settings),
) -> VideoService:
    return VideoService(
        image_client=image_client,
        video_assembler=video_assembler,
        script_repository=script_repository,
        voice_repository=voice_repository,
        video_repository=video_repository,
        media_root=settings.media_root,
    )


def get_orchestration_service(
    script_service: ScriptService = Depends(get_script_service),
    voice_service: VoiceService = Depends(get_voice_service),
    video_service: VideoService = Depends(get_video_service),
) -> OrchestrationService:
    return OrchestrationService(
        script_service=script_service, voice_service=voice_service, video_service=video_service
    )


@lru_cache
def get_youtube_upload_client() -> YoutubeUploadClient:
    return YoutubeUploadClient()


def get_publish_repository(session: AsyncSession = Depends(get_db)) -> PublishRepository:
    return PublishRepository(session)


def get_publish_service(
    upload_client: YoutubeUploadClient = Depends(get_youtube_upload_client),
    video_repository: VideoRepository = Depends(get_video_repository),
    voice_repository: VoiceRepository = Depends(get_voice_repository),
    script_repository: ScriptRepository = Depends(get_script_repository),
    publish_repository: PublishRepository = Depends(get_publish_repository),
    settings: Settings = Depends(get_settings),
) -> PublishService:
    return PublishService(
        upload_client=upload_client,
        video_repository=video_repository,
        voice_repository=voice_repository,
        script_repository=script_repository,
        publish_repository=publish_repository,
        media_root=settings.media_root,
        category_id=settings.youtube_category_id,
        content_language=settings.content_language,
    )

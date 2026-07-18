"""Business logic for publishing an AssembledVideo to YouTube."""

import logging
import re
from pathlib import Path
from uuid import UUID

from app.domain.models.publish import YoutubeUpload
from app.exceptions.publish_exceptions import VideoAlreadyPublishedError
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.video_exceptions import VideoNotFoundError
from app.exceptions.voice_exceptions import NarrationNotFoundError
from app.infrastructure.external.srt_builder import build_srt
from app.infrastructure.external.youtube_upload_client import YoutubeUploadClient
from app.repositories.interfaces.publish_repository import PublishRepositoryInterface
from app.repositories.interfaces.script_repository import ScriptRepositoryInterface
from app.repositories.interfaces.video_repository import VideoRepositoryInterface
from app.repositories.interfaces.voice_repository import VoiceRepositoryInterface

logger = logging.getLogger(__name__)

_BASE_TAGS = ["Shorts", "AI Tools", "AI World"]
_TAG_STOP_WORDS = {
    "the", "a", "an", "to", "for", "of", "in", "on", "and", "or", "with",
    "your", "you", "how", "this", "that", "is", "are", "it", "using", "why",
}
_MAX_KEYWORD_TAGS = 8


class PublishService:
    """Orchestrates: load AssembledVideo + Script, upload to YouTube, persist the result."""

    def __init__(
        self,
        upload_client: YoutubeUploadClient,
        video_repository: VideoRepositoryInterface,
        voice_repository: VoiceRepositoryInterface,
        script_repository: ScriptRepositoryInterface,
        publish_repository: PublishRepositoryInterface,
        media_root: str,
        category_id: str,
        content_language: str = "en",
    ) -> None:
        self._upload_client = upload_client
        self._video_repository = video_repository
        self._voice_repository = voice_repository
        self._script_repository = script_repository
        self._publish_repository = publish_repository
        self._media_root = Path(media_root)
        self._category_id = category_id
        self._content_language = content_language

    async def publish(self, video_id: UUID) -> YoutubeUpload:
        video = await self._video_repository.get_video(video_id)
        if video is None:
            raise VideoNotFoundError(f"No assembled video found with id '{video_id}'")

        existing = await self._publish_repository.get_upload_by_video_id(video_id)
        if existing is not None:
            raise VideoAlreadyPublishedError(f"Video '{video_id}' has already been published")

        narration = await self._voice_repository.get_narration(video.narration_id)
        if narration is None:
            raise NarrationNotFoundError(f"No voice narration found with id '{video.narration_id}'")

        script = await self._script_repository.get_script(narration.script_id)
        if script is None:
            raise ScriptNotFoundError(f"No script found with id '{narration.script_id}'")

        logger.info("publish_started", extra={"video_id": str(video_id)})

        youtube_video_id = await self._upload_client.upload_video(
            video_path=str(self._media_root / video.video_file_path),
            title=script.title,
            description=self._build_description(script.hook, script.cta),
            tags=self._build_tags(script.title, script.video_idea),
            category_id=self._category_id,
            # Every video this pipeline produces has AI voice narration and
            # AI-generated visuals, so disclosure is always required - not a
            # per-video judgment call.
            contains_synthetic_media=True,
            thumbnail_path=str(self._media_root / video.thumbnail_file_path),
            default_language=self._content_language,
            # Real YouTube caption track, not burned into the video frame -
            # see ffmpeg_assembler.py for why (a real rendering-correctness
            # bug for complex scripts like Telugu). Sidesteps that bug
            # entirely since YouTube's own renderer draws this text, and
            # gives viewers YouTube's built-in auto-translate for free.
            caption_content=build_srt(script, narration),
            caption_language=self._content_language,
        )
        youtube_url = f"https://youtu.be/{youtube_video_id}"
        await self._video_repository.mark_synthetic_content_disclosed(video_id)

        logger.info(
            "publish_completed",
            extra={"video_id": str(video_id), "youtube_video_id": youtube_video_id},
        )

        return await self._publish_repository.create_upload(
            video_id=video_id, youtube_video_id=youtube_video_id, youtube_url=youtube_url
        )

    async def get_by_video_id(self, video_id: UUID) -> YoutubeUpload | None:
        return await self._publish_repository.get_upload_by_video_id(video_id)

    @staticmethod
    def _build_description(hook: str, cta: str) -> str:
        return f"{hook}\n\n{cta}\n\n#Shorts #AI #AIWorld"

    @staticmethod
    def _build_tags(title: str, video_idea: str) -> list[str]:
        # The same 3 static tags on every upload is itself a templating
        # signal (see YouTube's 2026 crackdown on "mass-produced, templated"
        # channels) - deriving tags from each video's own title/idea instead
        # keeps every upload's metadata genuinely distinct without needing
        # an extra LLM call.
        words = re.findall(r"[A-Za-z0-9]+", f"{title} {video_idea}")
        keyword_tags: list[str] = []
        seen: set[str] = set()
        for word in words:
            normalized = word.lower()
            if len(normalized) < 3 or normalized in _TAG_STOP_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            keyword_tags.append(word)
        return _BASE_TAGS + keyword_tags[:_MAX_KEYWORD_TAGS]

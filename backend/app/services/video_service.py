"""Business logic for assembling a final video from a Script and its VoiceNarration."""

import logging
from pathlib import Path
from uuid import UUID

from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.video_exceptions import VideoAlreadyExistsError
from app.exceptions.voice_exceptions import NarrationNotFoundError
from app.infrastructure.external.interfaces.image_client import ImageClientInterface
from app.infrastructure.external.interfaces.video_assembler import VideoAssemblerInterface, VideoScene
from app.repositories.interfaces.script_repository import ScriptRepositoryInterface
from app.repositories.interfaces.video_repository import VideoRepositoryInterface
from app.repositories.interfaces.voice_repository import VoiceRepositoryInterface

logger = logging.getLogger(__name__)

_ASPECT_RATIO = "9:16"


class VideoService:
    """Orchestrates: load Script + VoiceNarration, generate images, assemble video, persist."""

    def __init__(
        self,
        image_client: ImageClientInterface,
        video_assembler: VideoAssemblerInterface,
        script_repository: ScriptRepositoryInterface,
        voice_repository: VoiceRepositoryInterface,
        video_repository: VideoRepositoryInterface,
        media_root: str,
    ) -> None:
        self._image_client = image_client
        self._video_assembler = video_assembler
        self._script_repository = script_repository
        self._voice_repository = voice_repository
        self._video_repository = video_repository
        self._media_root = Path(media_root)

    async def generate(self, narration_id: UUID) -> AssembledVideoDomain:
        narration = await self._voice_repository.get_narration(narration_id)
        if narration is None:
            raise NarrationNotFoundError(f"No voice narration found with id '{narration_id}'")

        existing = await self._video_repository.get_video_by_narration_id(narration_id)
        if existing is not None:
            raise VideoAlreadyExistsError(f"Narration '{narration_id}' already has an assembled video")

        script = await self._script_repository.get_script(narration.script_id)
        if script is None:
            raise ScriptNotFoundError(f"No script found with id '{narration.script_id}'")

        logger.info(
            "video_generation_started",
            extra={"narration_id": str(narration_id), "segment_count": len(script.segments)},
        )

        # Segment images are intermediate/throwaway inputs to ffmpeg, so they
        # live under images/. The thumbnail and final video are permanent,
        # served artifacts, so they live together under videos/.
        images_relative_dir = f"images/{narration_id}"
        video_relative_dir = f"videos/{narration_id}"
        (self._media_root / images_relative_dir).mkdir(parents=True, exist_ok=True)
        (self._media_root / video_relative_dir).mkdir(parents=True, exist_ok=True)

        scenes: list[VideoScene] = []
        for script_segment, voice_segment in zip(script.segments, narration.segments, strict=True):
            image_bytes = await self._image_client.generate_image(
                script_segment.visual_description, aspect_ratio=_ASPECT_RATIO
            )
            image_relative_path = f"{images_relative_dir}/segment_{voice_segment.segment_index}.png"
            (self._media_root / image_relative_path).write_bytes(image_bytes)

            scenes.append(
                VideoScene(
                    image_path=str(self._media_root / image_relative_path),
                    audio_path=str(self._media_root / voice_segment.audio_file_path),
                    caption_text=script_segment.text,
                )
            )

        thumbnail_bytes = await self._image_client.generate_image(
            self._thumbnail_prompt(script.title, script.hook), aspect_ratio=_ASPECT_RATIO
        )
        thumbnail_relative_path = f"{video_relative_dir}/thumbnail.png"
        (self._media_root / thumbnail_relative_path).write_bytes(thumbnail_bytes)

        video_relative_path = f"{video_relative_dir}/final.mp4"
        video_output_path = self._media_root / video_relative_path
        await self._video_assembler.assemble(scenes, str(video_output_path))

        total_duration = sum(segment.duration_seconds for segment in narration.segments)

        logger.info(
            "video_generation_completed",
            extra={"narration_id": str(narration_id), "duration_seconds": round(total_duration, 2)},
        )

        return await self._video_repository.create_video(
            narration_id=narration_id,
            video_file_path=video_relative_path,
            thumbnail_file_path=thumbnail_relative_path,
            duration_seconds=round(total_duration, 2),
        )

    async def get_by_id(self, video_id: UUID) -> AssembledVideoDomain | None:
        return await self._video_repository.get_video(video_id)

    @staticmethod
    def _thumbnail_prompt(title: str, hook: str) -> str:
        return (
            f'A scroll-stopping YouTube Shorts thumbnail for a video titled "{title}". '
            f'The hook is: "{hook}". Bold, high-contrast, eye-catching composition with '
            "large readable text conveying the core idea. Vertical format."
        )

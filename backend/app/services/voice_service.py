"""Business logic for generating per-segment voice narration for a Script."""

import io
import logging
import wave
from pathlib import Path
from uuid import UUID

from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.domain.models.voice import VoiceSegment
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.voice_exceptions import NarrationAlreadyExistsError
from app.infrastructure.external.interfaces.tts_client import DEFAULT_VOICE_NAME, TTSClientInterface
from app.repositories.interfaces.script_repository import ScriptRepositoryInterface
from app.repositories.interfaces.voice_repository import VoiceRepositoryInterface

logger = logging.getLogger(__name__)


class VoiceService:
    """Orchestrates: load a Script, generate per-segment audio via TTS, save to disk, persist."""

    def __init__(
        self,
        tts_client: TTSClientInterface,
        script_repository: ScriptRepositoryInterface,
        voice_repository: VoiceRepositoryInterface,
        media_root: str,
    ) -> None:
        self._tts_client = tts_client
        self._script_repository = script_repository
        self._voice_repository = voice_repository
        self._media_root = Path(media_root)

    async def generate(
        self, script_id: UUID, voice_name: str = DEFAULT_VOICE_NAME
    ) -> VoiceNarrationDomain:
        script = await self._script_repository.get_script(script_id)
        if script is None:
            raise ScriptNotFoundError(f"No script found with id '{script_id}'")

        existing = await self._voice_repository.get_narration_by_script_id(script_id)
        if existing is not None:
            raise NarrationAlreadyExistsError(f"Script '{script_id}' already has a voice narration")

        logger.info(
            "voice_generation_started",
            extra={"script_id": str(script_id), "segment_count": len(script.segments)},
        )

        relative_dir = f"audio/{script_id}"
        (self._media_root / relative_dir).mkdir(parents=True, exist_ok=True)

        # Sequential, not concurrent: TTS providers commonly rate-limit
        # per-minute request counts (confirmed in practice - Gemini's free
        # tier caps gemini-3.1-flash-tts at 3 requests/minute), and firing
        # all segments at once blows past that immediately.
        segments: list[VoiceSegment] = []
        for index, segment in enumerate(script.segments):
            audio_bytes = await self._tts_client.generate_speech(segment.text, voice_name)
            relative_path = f"{relative_dir}/segment_{index}.wav"
            (self._media_root / relative_path).write_bytes(audio_bytes)

            segments.append(
                VoiceSegment(
                    segment_index=index,
                    audio_file_path=relative_path,
                    duration_seconds=self._wav_duration_seconds(audio_bytes),
                )
            )

        return await self._voice_repository.create_narration(
            script_id=script_id,
            segments=segments,
            voice_name=voice_name,
        )

    async def get_by_id(self, narration_id: UUID) -> VoiceNarrationDomain | None:
        return await self._voice_repository.get_narration(narration_id)

    @staticmethod
    def _wav_duration_seconds(wav_bytes: bytes) -> float:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            return round(wf.getnframes() / wf.getframerate(), 2)

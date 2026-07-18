"""Thin async wrapper over local Piper TTS. Implements TTSClientInterface.

Runs entirely on local hardware, no API key, no quota - built specifically
because Gemini's TTS free-tier quota (10 requests/day) was observed at
100% usage during real testing, and Piper sidesteps that wall entirely at
zero cost. Verified end-to-end: real synthesis of an actual narration
segment produced a valid 22050Hz mono WAV in ~2.5s (including one-time
voice load), comparable pacing to Gemini's TTS output for the same text.

`voice_name` is accepted for TTSClientInterface compatibility but ignored -
Piper's voice identity is a downloaded ONNX model file, not a runtime
parameter like Gemini's prebuilt voice names ("Kore" etc.), and only one
local voice is configured today. Revisit if multiple local voices are
ever added.

`synthesize_wav` is a blocking, CPU-bound call (ONNX inference), so it
runs via asyncio.to_thread to avoid blocking the event loop - unlike the
other clients here, which are I/O-bound network calls that are naturally
async.
"""

import asyncio
import io
import wave

from piper import PiperVoice

from app.core.config import get_settings
from app.infrastructure.external.interfaces.tts_client import DEFAULT_VOICE_NAME


class PiperClient:
    """Wraps local Piper TTS synthesis behind TTSClientInterface."""

    def __init__(self, voice: PiperVoice | None = None) -> None:
        settings = get_settings()
        # Whole-channel mode, not per-request - matches the config's own
        # content_language semantics (see Settings.content_language).
        model_path = (
            settings.piper_model_path_te
            if settings.content_language == "te"
            else settings.piper_model_path
        )
        self._voice = voice or PiperVoice.load(model_path)

    async def generate_speech(self, text: str, voice_name: str = DEFAULT_VOICE_NAME) -> bytes:
        return await asyncio.to_thread(self._synthesize, text)

    def _synthesize(self, text: str) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)
        return buffer.getvalue()

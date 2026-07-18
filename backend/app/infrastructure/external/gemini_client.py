"""Thin async wrapper over the Gemini API. Implements LLMClientInterface,
TTSClientInterface, and ImageClientInterface.

SDK usage verified against the installed `google-genai` package source
(GenerateContentConfig field names, the .aio async surface, and the
`response.parsed` structured-output field) and against real API calls for
TTS and image generation specifically (audio bytes / image bytes, mime
types, response shapes all confirmed against live responses) rather than
assumed from docs, since Google's SDK naming has changed across versions
before and doc pages gave conflicting shapes during research.

Both image and speech generation calls intermittently fail mid-stream with
httpx.ReadError - originally found and fixed for image generation only
(~1.5-1.8MB PNGs, reproduced across 6 sequential real calls, 4 succeeded/2
failed, no fixed pattern, even though the underlying SDK's own tenacity
retry already ran and gave up), which looked at the time like flakiness
specific to large response bodies. Confirmed later that TTS hits the exact
same error class - a real voice-generation call failed with an identical
traceback once TTS_PROVIDER was switched from Piper (local, no network) to
Gemini (network) - so this is transport-level flakiness on this connection,
not something tied to response size specifically. Both calls now share one
retry helper (`_call_with_retry`) rather than each having its own copy.
"""

import asyncio
import io
import logging
import wave
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.infrastructure.external.interfaces.llm_client import (
    MAX_OUTPUT_TOKENS,
    SCRIPT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ScriptOutput,
    TrendInsights,
)
from app.infrastructure.external.interfaces.tts_client import DEFAULT_VOICE_NAME

GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Both image and speech responses intermittently fail mid-stream with
# httpx.ReadError - observed as transient, not deterministic (see module
# docstring). Retried here rather than left to the caller since it's a
# property of this transport, not of any particular caller's request.
_TRANSIENT_ERROR_MAX_ATTEMPTS = 3
_TRANSIENT_ERROR_RETRY_DELAY_SECONDS = 2

# Gemini TTS output format, confirmed against a live response's mime type
# (audio/l16; rate=24000; channels=1) - not documented as a stable contract,
# so isolated here rather than scattered through the WAV-writing logic.
_TTS_SAMPLE_RATE_HZ = 24000
_TTS_SAMPLE_WIDTH_BYTES = 2  # 16-bit
_TTS_CHANNELS = 1


class GeminiClient:
    """Wraps structured-output and speech-generation calls to Gemini."""

    def __init__(self, client: genai.Client | None = None) -> None:
        settings = get_settings()
        self._client = client or genai.Client(api_key=settings.gemini_api_key)

    @property
    def model_name(self) -> str:
        return GEMINI_MODEL

    async def close(self) -> None:
        self._client.close()

    @staticmethod
    async def _call_with_retry(call: Callable[[], Awaitable[_T]], *, operation: str) -> _T:
        attempt = 1
        while True:
            try:
                return await call()
            except httpx.ReadError:
                if attempt >= _TRANSIENT_ERROR_MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "gemini_transient_read_error",
                    extra={
                        "operation": operation,
                        "attempt": attempt,
                        "max_attempts": _TRANSIENT_ERROR_MAX_ATTEMPTS,
                    },
                )
                await asyncio.sleep(_TRANSIENT_ERROR_RETRY_DELAY_SECONDS)
                attempt += 1

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights:
        response = await self._call_with_retry(
            lambda: self._client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=TrendInsights,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            ),
            operation="analyze_trending_videos",
        )
        return response.parsed

    async def generate_script(self, prompt: str) -> ScriptOutput:
        response = await self._call_with_retry(
            lambda: self._client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SCRIPT_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=ScriptOutput,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            ),
            operation="generate_script",
        )
        return response.parsed

    async def generate_speech(self, text: str, voice_name: str = DEFAULT_VOICE_NAME) -> bytes:
        response = await self._call_with_retry(
            lambda: self._client.aio.models.generate_content(
                model=GEMINI_TTS_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                        )
                    ),
                ),
            ),
            operation="generate_speech",
        )
        pcm_data = response.candidates[0].content.parts[0].inline_data.data

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(_TTS_CHANNELS)
            wf.setsampwidth(_TTS_SAMPLE_WIDTH_BYTES)
            wf.setframerate(_TTS_SAMPLE_RATE_HZ)
            wf.writeframes(pcm_data)
        return buffer.getvalue()

    async def generate_image(self, prompt: str, aspect_ratio: str = "9:16") -> bytes:
        response = await self._call_with_retry(
            lambda: self._client.aio.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                ),
            ),
            operation="generate_image",
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data
        raise ValueError("Gemini image generation response contained no image data")

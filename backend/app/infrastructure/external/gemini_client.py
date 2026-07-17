"""Thin async wrapper over the Gemini API. Implements LLMClientInterface,
TTSClientInterface, and ImageClientInterface.

SDK usage verified against the installed `google-genai` package source
(GenerateContentConfig field names, the .aio async surface, and the
`response.parsed` structured-output field) and against real API calls for
TTS specifically (audio bytes, WAV write, duration math, mime type all
confirmed against a live response) rather than assumed from docs, since
Google's SDK naming has changed across versions before and doc pages gave
conflicting shapes during research. Image generation config fields
(response_modalities, ImageConfig.aspect_ratio) are verified the same way
against SDK source, but not yet against a live call - billing wasn't
enabled on the Google Cloud project at the time this was written (image
generation has no free tier at all, confirmed via a real 429).
"""

import io
import wave

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

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights:
        response = await self._client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=TrendInsights,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        return response.parsed

    async def generate_script(self, prompt: str) -> ScriptOutput:
        response = await self._client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SCRIPT_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ScriptOutput,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        return response.parsed

    async def generate_speech(self, text: str, voice_name: str = DEFAULT_VOICE_NAME) -> bytes:
        response = await self._client.aio.models.generate_content(
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
        response = await self._client.aio.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data
        raise ValueError("Gemini image generation response contained no image data")

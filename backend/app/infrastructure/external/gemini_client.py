"""Thin async wrapper over the Gemini API. Implements LLMClientInterface.

SDK usage verified against the installed `google-genai` package source
(GenerateContentConfig field names, the .aio async surface, and the
`response.parsed` structured-output field) rather than assumed from docs,
since Google's SDK naming has changed across versions before.
"""

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

GEMINI_MODEL = "gemini-3.5-flash"


class GeminiClient:
    """Wraps structured-output calls to Gemini for trend analysis and scripting."""

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

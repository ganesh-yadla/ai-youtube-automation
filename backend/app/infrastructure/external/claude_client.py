"""Thin async wrapper over the Claude API. Implements LLMClientInterface."""

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.infrastructure.external.interfaces.llm_client import (
    MAX_OUTPUT_TOKENS,
    SCRIPT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ScriptOutput,
    TrendInsights,
)

CLAUDE_MODEL = "claude-opus-4-8"


class ClaudeClient:
    """Wraps structured-output calls to Claude for trend analysis and scripting."""

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    @property
    def model_name(self) -> str:
        return CLAUDE_MODEL

    async def close(self) -> None:
        await self._client.close()

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights:
        response = await self._client.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_format=TrendInsights,
        )
        return response.parsed_output

    async def generate_script(self, prompt: str) -> ScriptOutput:
        response = await self._client.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SCRIPT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_format=ScriptOutput,
        )
        return response.parsed_output

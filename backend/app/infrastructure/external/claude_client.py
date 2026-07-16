"""Thin async wrapper over the Claude API for AI-generated trend insights."""

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.core.config import get_settings

CLAUDE_MODEL = "claude-opus-4-8"
MAX_OUTPUT_TOKENS = 4096

SYSTEM_PROMPT = (
    "You are a YouTube content strategy analyst. Given a set of currently "
    "trending videos for a keyword, identify concrete, actionable patterns "
    "- not generic advice. You only have text metadata (titles, channels, "
    "view counts, publish dates, durations, growth scores) - no thumbnail "
    "images - so infer hook and thumbnail patterns from context and say so "
    "plainly rather than fabricating visual detail you cannot see."
)


class TrendInsights(BaseModel):
    why_performing: str
    common_hooks: list[str]
    common_title_patterns: list[str]
    common_thumbnail_patterns: list[str]
    content_gaps: list[str]
    video_ideas: list[str]


class ClaudeClient:
    """Wraps a single structured-output call to Claude for trend analysis."""

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

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

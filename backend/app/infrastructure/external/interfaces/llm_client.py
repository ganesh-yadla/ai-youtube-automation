"""Provider-neutral LLM contract: the Protocol both ClaudeClient and
GeminiClient implement, the structured output shapes both must produce,
and the shared prompt wording so behavior doesn't drift between providers.

Services depend on LLMClientInterface, never on a concrete client - matches
the same Protocol-based pattern already used for repositories.
"""

from typing import Protocol

from pydantic import BaseModel

MAX_OUTPUT_TOKENS = 4096

SYSTEM_PROMPT = (
    "You are a YouTube content strategy analyst. Given a set of currently "
    "trending videos for a keyword, identify concrete, actionable patterns "
    "- not generic advice. You only have text metadata (titles, channels, "
    "view counts, publish dates, durations, growth scores) - no thumbnail "
    "images - so infer hook and thumbnail patterns from context and say so "
    "plainly rather than fabricating visual detail you cannot see."
)

SCRIPT_SYSTEM_PROMPT = (
    "You are a YouTube Shorts scriptwriter. Given trend analysis insights for "
    "a keyword (why similar videos perform well, common hooks, title "
    "patterns, and suggested video ideas), write a complete Short script.\n\n"
    "Requirements:\n"
    "- Target 30-45 seconds of spoken content (roughly 75-120 words total "
    "across all segments).\n"
    "- Open with a hook that grabs attention in the first 1-3 seconds - no "
    "slow windups.\n"
    "- Break the script into 4-8 segments. Each segment is one spoken beat, "
    "paired with a brief description of what should be shown on screen "
    "while it plays, written for an AI image generator (describe the scene "
    "or subject, not 'insert clip of X').\n"
    "- End with a short call-to-action.\n"
    "- COPYRIGHT SAFETY IS MANDATORY: only write content producible with "
    "100% original material. Never write lyrics or dialogue lifted from "
    "existing copyrighted work. Never describe visuals that require "
    "someone else's video footage, trademarked characters, or real "
    "celebrities' likenesses. Never reference specific copyrighted music "
    "by name. If a suggested video idea would require reproducing someone "
    "else's content (e.g. 'reaction to X's video', 'compilation of Y'), "
    "adapt it into a similar but fully original idea instead.\n"
    "- If a specific video idea is given, write the script for that idea "
    "exactly as given. If none is given, select the strongest original "
    "idea from the analysis's suggested video ideas (adapting it for "
    "originality if needed), or synthesize a new one from the trend "
    "patterns if none are suitable - and report which idea you used."
)


class TrendInsights(BaseModel):
    why_performing: str
    common_hooks: list[str]
    common_title_patterns: list[str]
    common_thumbnail_patterns: list[str]
    content_gaps: list[str]
    video_ideas: list[str]


class ScriptSegmentOutput(BaseModel):
    text: str
    visual_description: str


class ScriptOutput(BaseModel):
    video_idea: str
    title: str
    hook: str
    segments: list[ScriptSegmentOutput]
    cta: str


class LLMClientInterface(Protocol):
    @property
    def model_name(self) -> str:
        """The concrete model identifier actually used - persisted alongside
        generated content so it's always accurate, whichever provider ran.
        """
        ...

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights: ...

    async def generate_script(self, prompt: str) -> ScriptOutput: ...

    async def close(self) -> None: ...

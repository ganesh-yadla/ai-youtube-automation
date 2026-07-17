"""Thin async wrapper over a local Ollama server. Implements LLMClientInterface.

Runs entirely on local hardware (tested against an RTX 4050 laptop GPU, 6GB
VRAM) - no API key, no quota, no cloud dependency. Exists specifically to
route around cloud LLM outages/quota walls (Gemini's `503 UNAVAILABLE`
"high demand" error was persistent enough during real testing to justify a
local fallback) at zero ongoing cost.

`num_gpu` is passed explicitly and high rather than left to Ollama's default
auto-detection - confirmed via real testing that Ollama's default GPU-layer
estimate left ~1.6GB of VRAM unused on this 6GB card, forcing a needless
25% CPU / 75% GPU split that was roughly 10x slower (20s vs 0.2s prompt
eval) than forcing full GPU offload with an explicit high num_gpu value.
"""

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.infrastructure.external.interfaces.llm_client import (
    SCRIPT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ScriptOutput,
    TrendInsights,
)

OLLAMA_MODEL = "llama3.1:8b"
_NUM_CTX = 4096
_NUM_GPU = 99
_MAX_ATTEMPTS = 3


class OllamaClient:
    """Wraps structured-output calls to a local Ollama server for trend
    analysis and scripting.
    """

    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        resolved_base_url = base_url or settings.ollama_base_url
        self._client = client or httpx.AsyncClient(base_url=resolved_base_url, timeout=120.0)

    @property
    def model_name(self) -> str:
        return OLLAMA_MODEL

    async def close(self) -> None:
        await self._client.aclose()

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights:
        return await self._generate(SYSTEM_PROMPT, prompt, TrendInsights)

    async def generate_script(self, prompt: str) -> ScriptOutput:
        return await self._generate(SCRIPT_SYSTEM_PROMPT, prompt, ScriptOutput)

    async def _generate(self, system_prompt: str, prompt: str, output_model: type[BaseModel]) -> BaseModel:
        full_prompt = f"{system_prompt}\n\n{prompt}"
        last_error: ValidationError | None = None

        # Local models are far cheaper/faster to retry than cloud calls, and
        # confirmed via real testing to occasionally produce schema-valid
        # but semantically empty output (e.g. segments: []) - a plain retry
        # reliably gets a well-formed result on a later attempt.
        for _ in range(_MAX_ATTEMPTS):
            response = await self._client.post(
                "/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "format": output_model.model_json_schema(),
                    "options": {"num_ctx": _NUM_CTX, "num_gpu": _NUM_GPU},
                },
            )
            response.raise_for_status()
            data = response.json()
            try:
                return output_model.model_validate_json(data["response"])
            except ValidationError as e:
                last_error = e

        assert last_error is not None
        raise last_error

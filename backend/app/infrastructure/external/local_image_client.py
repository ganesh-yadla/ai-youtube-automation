"""Thin wrapper over a local SD-Turbo pipeline (via diffusers). Implements
ImageClientInterface.

Runs entirely on local hardware - no API key, no quota, no cloud
dependency. Built as the third piece of local generation (after Ollama for
scripts and Piper for voice), completing the free/local path for the
whole pipeline.

CPU-only, not GPU-accelerated: PyTorch's CUDA wheels don't yet support
this machine's Python version (3.14 - too new as of this build), only the
CPU build installed. Verified this is still fast enough to be worth it
anyway - a real timed generation took 8.3s per image on this CPU once the
model was loaded, which is roughly comparable to Gemini's per-image
latency and well within budget for 6 images/video (~50s total). Revisit
GPU acceleration once PyTorch publishes CUDA wheels for this Python
version, or if a Python downgrade is ever done for another reason.

Always generates at SD-Turbo's native 512x512 - the model was specifically
distilled for single-step generation at this resolution, and forcing a
different aspect ratio risks quality loss outside its training
distribution. The `aspect_ratio` parameter is accepted for interface
compliance but not used to change generation dimensions; the existing
ffmpeg scale+crop step in FFmpegVideoAssembler already reshapes whatever
image dimensions it's given to the final 1080x1920 frame, so this doesn't
need to duplicate that logic here.

No safety checker: `stabilityai/sd-turbo` ships without one in its model
repo (not a flag we're disabling). Acceptable here because prompts come
from our own Script Agent (governed by SCRIPT_SYSTEM_PROMPT's content
rules), not arbitrary third-party input - not the "public-facing service
with untrusted prompts" scenario the diffusers safety-checker warning is
about. Revisit if prompts ever come from unvetted user input.
"""

import asyncio
import io

import torch
from diffusers import AutoPipelineForText2Image

from app.core.config import get_settings

_MODEL_ID = "stabilityai/sd-turbo"
_IMAGE_SIZE = 512
_INFERENCE_STEPS = 1
_GUIDANCE_SCALE = 0.0


class LocalImageClient:
    """Wraps local SD-Turbo image generation behind ImageClientInterface."""

    def __init__(self, pipeline: AutoPipelineForText2Image | None = None) -> None:
        get_settings()  # fail fast on missing config, matches other clients
        self._pipeline = pipeline or AutoPipelineForText2Image.from_pretrained(
            _MODEL_ID, torch_dtype=torch.float32
        )

    async def generate_image(self, prompt: str, aspect_ratio: str = "9:16") -> bytes:
        return await asyncio.to_thread(self._generate, prompt)

    def _generate(self, prompt: str) -> bytes:
        image = self._pipeline(
            prompt=prompt,
            num_inference_steps=_INFERENCE_STEPS,
            guidance_scale=_GUIDANCE_SCALE,
            height=_IMAGE_SIZE,
            width=_IMAGE_SIZE,
        ).images[0]

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

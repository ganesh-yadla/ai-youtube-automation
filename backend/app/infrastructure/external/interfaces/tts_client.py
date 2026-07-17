"""Provider-neutral TTS contract.

Kept as a separate interface from LLMClientInterface - text generation and
speech generation are distinct capabilities. A provider may implement one,
both, or neither (a hypothetical future ElevenLabs client would only ever
implement this one, not LLMClientInterface).
"""

from typing import Protocol

DEFAULT_VOICE_NAME = "Kore"


class TTSClientInterface(Protocol):
    async def generate_speech(self, text: str, voice_name: str = DEFAULT_VOICE_NAME) -> bytes:
        """Returns WAV-formatted audio bytes for the given text.

        WAV, not raw PCM, so callers never need provider-specific knowledge
        (sample rate, bit depth, channels) to use or measure the result -
        Python's `wave` module can read duration straight from the header.
        """
        ...

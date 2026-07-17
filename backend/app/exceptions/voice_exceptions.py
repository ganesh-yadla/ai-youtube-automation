"""Domain exceptions for the Voice Generation feature."""


class VoiceGenerationError(Exception):
    """Base exception for all Voice Generation errors."""


class NarrationAlreadyExistsError(VoiceGenerationError):
    """Raised when re-requesting voice narration for a script that already has one."""


class NarrationNotFoundError(VoiceGenerationError):
    """Raised when a requested VoiceNarration id does not exist."""

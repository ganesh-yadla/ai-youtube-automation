"""Domain exceptions for the Script Agent feature."""


class ScriptGenerationError(Exception):
    """Base exception for all Script Agent errors."""


class TrendAnalysisRequiredError(ScriptGenerationError):
    """Raised when script generation is requested for a search that hasn't been analyzed yet."""


class ScriptNotFoundError(ScriptGenerationError):
    """Raised when a requested Script id does not exist."""

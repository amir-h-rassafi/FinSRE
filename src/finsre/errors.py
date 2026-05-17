class FinSREError(Exception):
    """Base class for expected FinSRE failures."""


class ApprovalRequiredError(FinSREError):
    """Raised when an operation needs explicit human approval."""


class ConfigurationError(FinSREError):
    """Raised when required runtime configuration is missing or invalid."""


class OptionalDependencyError(FinSREError):
    """Raised when an optional integration dependency is not installed."""


class LLMProviderError(FinSREError):
    """Raised when an approved LLM provider call fails."""


class UnsupportedProviderError(FinSREError):
    """Raised when a configured provider is not supported."""

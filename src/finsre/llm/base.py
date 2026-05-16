from dataclasses import dataclass
from typing import Protocol

from finsre.errors import ConfigurationError


class MissingLLMConfiguration(ConfigurationError):
    """Raised when an LLM call is requested without required configuration."""


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str


class LLMClient(Protocol):
    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        """Return one completion for bounded investigation context."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class AgentCapability(StrEnum):
    INVESTIGATION = "investigation"
    COST_ANALYSIS = "cost_analysis"
    CHANGE_CORRELATION = "change_correlation"
    REMEDIATION_PLANNING = "remediation_planning"
    DATA_QUALITY = "data_quality"


@dataclass(frozen=True)
class AgentRequest:
    capability: AgentCapability
    goal: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    capability: AgentCapability
    summary: str
    evidence: tuple[dict[str, Any], ...] = ()
    confidence: float | None = None


class Agent(Protocol):
    name: str
    capabilities: tuple[AgentCapability, ...]

    def run(self, request: AgentRequest) -> AgentResult:
        """Run an agent request against bounded context."""

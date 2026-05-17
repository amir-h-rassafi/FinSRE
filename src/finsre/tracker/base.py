from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class WorkStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class Investigation:
    id: str
    title: str
    status: WorkStatus = WorkStatus.OPEN
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Recommendation:
    id: str
    title: str
    estimated_monthly_savings: float | None = None
    status: WorkStatus = WorkStatus.OPEN
    evidence: tuple[dict[str, Any], ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Tracker(Protocol):
    def add_investigation(self, investigation: Investigation) -> None:
        """Persist an investigation."""

    def list_investigations(self) -> list[Investigation]:
        """List investigations known to the tracker."""

    def add_recommendation(self, recommendation: Recommendation) -> None:
        """Persist a recommendation."""

    def list_recommendations(self) -> list[Recommendation]:
        """List recommendations known to the tracker."""

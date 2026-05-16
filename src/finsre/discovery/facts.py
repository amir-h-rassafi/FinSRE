from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class FactSource(StrEnum):
    BILLING = "billing"
    ASSET = "asset"
    NETWORK = "network"
    TELEMETRY = "telemetry"
    CHANGE = "change"
    USER = "user"
    INFERENCE = "inference"


@dataclass(frozen=True)
class ContextFact:
    entity_id: str
    fact_type: str
    value: Any
    source: FactSource
    confidence: float
    evidence: tuple[dict[str, Any], ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


class ContextFactStore:
    def __init__(self) -> None:
        self._facts: list[ContextFact] = []

    def put(self, fact: ContextFact) -> None:
        self._facts.append(fact)

    def list(self, entity_id: str | None = None) -> list[ContextFact]:
        if entity_id is None:
            return list(self._facts)
        return [fact for fact in self._facts if fact.entity_id == entity_id]

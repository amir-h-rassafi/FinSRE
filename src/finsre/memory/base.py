from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class MemoryRecord:
    key: str
    namespace: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MemoryStore(Protocol):
    def put(self, record: MemoryRecord) -> None:
        """Store a memory record."""

    def search(self, namespace: str, query: str, limit: int = 10) -> list[MemoryRecord]:
        """Return relevant memory records for bounded agent context."""

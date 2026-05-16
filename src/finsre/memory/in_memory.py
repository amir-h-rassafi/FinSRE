from finsre.core.components import ComponentKind, ComponentManifest, DeployMode
from finsre.core.events import EventType
from finsre.memory.base import MemoryRecord


class InMemoryStore:
    """Small deterministic store for tests and early CLI workflows."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def put(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def search(self, namespace: str, query: str, limit: int = 10) -> list[MemoryRecord]:
        terms = query.lower().split()
        matches = [
            record
            for record in self._records
            if record.namespace == namespace and all(term in record.text.lower() for term in terms)
        ]
        return matches[:limit]

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name="memory-store",
            kind=ComponentKind.MEMORY,
            version="0.1",
            input_events=(EventType.MEMORY_RECORD_CREATED.value,),
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.SERVICE),
            description="Stores bounded context for retrieval and future vector memory.",
        )

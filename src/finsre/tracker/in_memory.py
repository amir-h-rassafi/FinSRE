from finsre.core.components import ComponentKind, ComponentManifest, DeployMode
from finsre.core.events import EventType
from finsre.tracker.base import Investigation, Recommendation


class InMemoryTracker:
    """Small deterministic tracker for tests and local workflows."""

    def __init__(self) -> None:
        self._investigations: list[Investigation] = []
        self._recommendations: list[Recommendation] = []

    def add_investigation(self, investigation: Investigation) -> None:
        self._investigations.append(investigation)

    def list_investigations(self) -> list[Investigation]:
        return list(self._investigations)

    def add_recommendation(self, recommendation: Recommendation) -> None:
        self._recommendations.append(recommendation)

    def list_recommendations(self) -> list[Recommendation]:
        return list(self._recommendations)

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name="tracker",
            kind=ComponentKind.TRACKER,
            version="0.1",
            input_events=(EventType.INVESTIGATION_UPDATED.value, EventType.RECOMMENDATION_CREATED.value),
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.SERVICE),
            description="Tracks investigation and recommendation lifecycle state.",
        )

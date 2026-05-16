from abc import ABC, abstractmethod
from collections.abc import Iterable

from finsre.core.components import ComponentManifest
from finsre.core.events import EventEnvelope
from finsre.models import CompatibilityReport, ConnectorDescriptor, CostLineItem, TimePeriod


class Connector(ABC):
    """Contract all source connectors must implement."""

    @abstractmethod
    def describe(self) -> ConnectorDescriptor:
        """Return metadata and readiness for this connector."""

    def preview_api_calls(self, period: TimePeriod) -> list[str]:
        """Return source API calls when the connector supports call preview."""
        return []

    def check_compatibility(self, live: bool = False) -> CompatibilityReport:
        """Report local and optional live compatibility for this connector."""
        raise NotImplementedError

    def manifest(self) -> ComponentManifest:
        """Return deployment/event metadata for this connector."""
        raise NotImplementedError

    def compatibility_event(self, live: bool = False) -> EventEnvelope:
        """Return a normalized event for compatibility status."""
        raise NotImplementedError

    def collect_costs(self) -> Iterable[CostLineItem]:
        """Collect normalized cost rows.

        Connectors can override this once a concrete data source client is wired.
        """
        return ()

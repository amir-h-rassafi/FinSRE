from abc import ABC, abstractmethod
from collections.abc import Iterable

from finsre.models import ConnectorDescriptor, CostLineItem, TimePeriod


class Connector(ABC):
    """Contract all source connectors must implement."""

    @abstractmethod
    def describe(self) -> ConnectorDescriptor:
        """Return metadata and readiness for this connector."""

    def preview_api_calls(self, period: TimePeriod) -> list[str]:
        """Return source API calls when the connector supports call preview."""
        return []

    def collect_costs(self) -> Iterable[CostLineItem]:
        """Collect normalized cost rows.

        Connectors can override this once a concrete data source client is wired.
        """
        return ()

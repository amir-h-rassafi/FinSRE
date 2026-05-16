from abc import ABC, abstractmethod
from collections.abc import Iterable

from finsre.models import ConnectorDescriptor, CostLineItem


class Connector(ABC):
    """Contract all source connectors must implement."""

    @abstractmethod
    def describe(self) -> ConnectorDescriptor:
        """Return metadata and readiness for this connector."""

    def preview_query(self) -> str | None:
        """Return a source query when the connector supports query preview."""
        return None

    def collect_costs(self) -> Iterable[CostLineItem]:
        """Collect normalized cost rows.

        Connectors can override this once a concrete data source client is wired.
        """
        return ()

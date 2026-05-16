from finsre.config import Settings
from finsre.connectors.base import Connector
from finsre.connectors.gcp_billing import GcpBillingConnector


class ConnectorRegistry:
    def __init__(self, connectors: list[Connector]) -> None:
        self._connectors = {connector.describe().name: connector for connector in connectors}

    def list(self) -> list[Connector]:
        return list(self._connectors.values())

    def get(self, name: str) -> Connector:
        try:
            return self._connectors[name]
        except KeyError as exc:
            raise KeyError(f"Unknown connector: {name}") from exc


def build_default_registry(settings: Settings) -> ConnectorRegistry:
    return ConnectorRegistry(
        connectors=[
            GcpBillingConnector(
                billing_account=settings.gcp_billing_account,
                currency_code=settings.gcp_billing_currency,
            )
        ]
    )

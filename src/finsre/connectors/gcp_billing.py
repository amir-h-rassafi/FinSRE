from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from finsre.connectors.base import Connector
from finsre.models import CloudProvider, ConnectorDescriptor, ConnectorStatus, CostLineItem


class GcpBillingConnector(Connector):
    """GCP Cloud Billing export connector.

    The first implementation builds the normalized query used by the API and
    keeps BigQuery execution optional so local development does not require GCP.
    """

    name = "gcp-billing"

    def __init__(self, billing_table: str | None, billing_project: str | None = None) -> None:
        self.billing_table = billing_table
        self.billing_project = billing_project

    def describe(self) -> ConnectorDescriptor:
        status = ConnectorStatus.CONFIGURED if self.billing_table else ConnectorStatus.NEEDS_CONFIGURATION
        details: dict[str, Any] = {}
        if self.billing_table:
            details["billing_table"] = self.billing_table
        if self.billing_project:
            details["billing_project"] = self.billing_project
        return ConnectorDescriptor(
            name=self.name,
            provider=CloudProvider.GCP,
            source_type="billing_export",
            status=status,
            capabilities=("daily_cost", "service_cost", "sku_cost", "label_cost"),
            details=details,
        )

    def preview_query(self) -> str | None:
        if not self.billing_table:
            return None
        return self.daily_cost_query()

    def daily_cost_query(self) -> str:
        if not self.billing_table:
            raise ValueError("GCP billing table is not configured.")

        table = self._quoted_table(self.billing_table)
        return f"""
SELECT
  DATE(usage_start_time) AS usage_date,
  project.id AS project_id,
  service.description AS service,
  sku.description AS sku,
  location.region AS region,
  currency,
  labels,
  SUM(cost) AS cost,
  SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0)) AS credits,
  SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0)) AS net_cost
FROM {table}
WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 32 DAY)
GROUP BY usage_date, project_id, service, sku, region, currency, labels
ORDER BY usage_date DESC, net_cost DESC
""".strip()

    def normalize_row(self, row: dict[str, Any]) -> CostLineItem:
        labels = row.get("labels") or {}
        if isinstance(labels, list):
            labels = {
                str(item.get("key")): str(item.get("value"))
                for item in labels
                if item.get("key") is not None and item.get("value") is not None
            }

        usage_date = row["usage_date"]
        if not isinstance(usage_date, date):
            usage_date = date.fromisoformat(str(usage_date))

        return CostLineItem(
            provider=CloudProvider.GCP,
            account_id=str(row.get("project_id") or ""),
            project_id=row.get("project_id"),
            service=str(row.get("service") or ""),
            sku=str(row.get("sku") or ""),
            region=row.get("region"),
            usage_start_date=usage_date,
            currency=str(row.get("currency") or "USD"),
            cost=Decimal(str(row.get("net_cost", row.get("cost", "0")))),
            labels=labels,
            source=self.name,
        )

    def collect_costs(self) -> Iterable[CostLineItem]:
        if not self.billing_project:
            raise RuntimeError("FINSRE_GCP_BILLING_PROJECT is required to execute BigQuery queries.")

        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise RuntimeError("Install the gcp extra to execute BigQuery queries: pip install '.[gcp]'") from exc

        client = bigquery.Client(project=self.billing_project)
        for row in client.query(self.daily_cost_query()).result():
            yield self.normalize_row(dict(row.items()))

    @staticmethod
    def _quoted_table(table: str) -> str:
        if table.startswith("`") and table.endswith("`"):
            return table
        return f"`{table}`"

from datetime import date
from decimal import Decimal
from unittest import TestCase

from finsre.connectors.gcp_billing import GcpBillingConnector
from finsre.models import ConnectorStatus


class GcpBillingConnectorTest(TestCase):
    def test_describe_reports_missing_configuration(self) -> None:
        connector = GcpBillingConnector(billing_table=None)

        descriptor = connector.describe()

        self.assertEqual(descriptor.name, "gcp-billing")
        self.assertEqual(descriptor.status, ConnectorStatus.NEEDS_CONFIGURATION)

    def test_daily_cost_query_uses_configured_table(self) -> None:
        connector = GcpBillingConnector(billing_table="billing.dataset.export")

        query = connector.daily_cost_query()

        self.assertIn("FROM `billing.dataset.export`", query)
        self.assertIn("SUM(cost)", query)
        self.assertIn("net_cost", query)

    def test_normalize_row_accepts_billing_label_records(self) -> None:
        connector = GcpBillingConnector(billing_table="billing.dataset.export")

        item = connector.normalize_row(
            {
                "usage_date": "2026-05-15",
                "project_id": "analytics-prod",
                "service": "BigQuery",
                "sku": "Analysis",
                "region": "europe-west2",
                "currency": "USD",
                "net_cost": "12.34",
                "labels": [{"key": "team", "value": "data"}],
            }
        )

        self.assertEqual(item.usage_start_date, date(2026, 5, 15))
        self.assertEqual(item.cost, Decimal("12.34"))
        self.assertEqual(item.labels, {"team": "data"})

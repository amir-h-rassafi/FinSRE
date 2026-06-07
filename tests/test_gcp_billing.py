from datetime import date

from finsre.connectors.gcp_billing import GcpBillingApiConnector
from finsre.models import ConnectorContract, TimePeriod


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str] | None]] = []
        self.responses: list[dict[str, object]] = []

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, object]:
        self.calls.append((path, params))
        return self.responses.pop(0)


def test_describe_reports_api_connector_capabilities() -> None:
    connector = GcpBillingApiConnector(billing_account=None)

    descriptor = connector.describe()

    assert descriptor.name == "gcp-billing"
    assert descriptor.source_type == "cloud_billing_api"
    assert "sku_pricing_by_period" in descriptor.capabilities
    assert descriptor.contract.upstream == "cloudbilling.googleapis.com/v1"
    assert descriptor.contract.schema == "finsre.gcp_billing.v1"
    assert descriptor.contract.version == "1.0"


def test_check_compatibility_reports_contract_without_live_probe() -> None:
    connector = GcpBillingApiConnector()

    report = connector.check_compatibility()

    assert report.connector == "gcp-billing"
    assert report.ok is True
    assert report.checked_live is False
    assert report.contract.upstream == "cloudbilling.googleapis.com/v1"
    assert report.problems == ()
    assert "Historical usage-cost line items" in report.warnings[0]


def test_check_compatibility_can_run_live_probe_with_injected_transport() -> None:
    transport = FakeTransport()
    transport.responses.append({"billingAccounts": []})
    connector = GcpBillingApiConnector(transport=transport)

    report = connector.check_compatibility(live=True)

    assert report.ok is True
    assert report.checked_live is True
    assert report.problems == ()
    assert transport.calls[0][0] == "/v1/billingAccounts"


def test_check_compatibility_detects_contract_mismatch() -> None:
    class BrokenContractApiConnector(GcpBillingApiConnector):
        contract = ConnectorContract(version="2.0", upstream="wrong/v9", schema="wrong.schema")

    report = BrokenContractApiConnector().check_compatibility()

    assert report.ok is False
    assert len(report.problems) == 2


def test_check_compatibility_detects_missing_required_capability() -> None:
    class MissingCapabilityApiConnector(GcpBillingApiConnector):
        def describe(self):
            descriptor = super().describe()
            return type(descriptor)(
                name=descriptor.name,
                provider=descriptor.provider,
                source_type=descriptor.source_type,
                capabilities=("billing_account_discovery",),
                contract=descriptor.contract,
                details=descriptor.details,
            )

    report = MissingCapabilityApiConnector().check_compatibility()

    assert report.ok is False
    assert "Missing required capability: sku_pricing_by_period." in report.problems


def test_manifest_describes_deployable_connector_boundary() -> None:
    connector = GcpBillingApiConnector()

    manifest = connector.manifest()

    assert manifest.name == "gcp-billing"
    assert manifest.kind.value == "connector"
    assert "cli_job" in [mode.value for mode in manifest.deploy_modes]
    assert "finsre.connector.compatibility.checked" in manifest.output_events


def test_compatibility_event_uses_normalized_envelope() -> None:
    connector = GcpBillingApiConnector()

    event = connector.compatibility_event()

    assert event.type == "finsre.connector.compatibility.checked"
    assert event.source == "connector/gcp-billing"
    assert event.subject == "gcp-billing"
    assert event.data["ok"] is True


def test_preview_api_calls_include_period() -> None:
    connector = GcpBillingApiConnector(billing_account="012345-6789AB-CDEF01")

    calls = connector.preview_api_calls(TimePeriod(date(2026, 5, 1), date(2026, 5, 16)))

    assert "https://cloudbilling.googleapis.com/v1/billingAccounts" in calls
    assert "billingAccounts/012345-6789AB-CDEF01/projects" in calls[2]
    assert "startTime=2026-05-01T00%3A00%3A00Z" in calls[3]
    assert "endTime=2026-05-16T00%3A00%3A00Z" in calls[3]


def test_list_projects_uses_configured_billing_account() -> None:
    transport = FakeTransport()
    transport.responses.append({"projectBillingInfo": [{"projectId": "analytics-prod"}]})
    connector = GcpBillingApiConnector(billing_account="012345-6789AB-CDEF01", transport=transport)

    projects = connector.list_projects()

    assert projects == [{"projectId": "analytics-prod"}]
    assert transport.calls[0][0] == "/v1/billingAccounts/012345-6789AB-CDEF01/projects"


def test_list_skus_for_service_uses_period_and_pagination() -> None:
    transport = FakeTransport()
    transport.responses.extend(
        [
            {"skus": [{"skuId": "sku-1"}], "nextPageToken": "next"},
            {"skus": [{"skuId": "sku-2"}]},
        ]
    )
    connector = GcpBillingApiConnector(transport=transport)
    period = TimePeriod(date(2026, 5, 1), date(2026, 5, 16))

    skus = connector.list_skus_for_service("6F81-5844-456A", period, "GBP")

    assert skus == [{"skuId": "sku-1"}, {"skuId": "sku-2"}]
    assert transport.calls[0][0] == "/v1/services/6F81-5844-456A/skus"
    assert transport.calls[0][1]["startTime"] == "2026-05-01T00:00:00Z"
    assert transport.calls[0][1]["endTime"] == "2026-05-16T00:00:00Z"
    assert transport.calls[0][1]["currencyCode"] == "GBP"
    assert transport.calls[1][1]["pageToken"] == "next"

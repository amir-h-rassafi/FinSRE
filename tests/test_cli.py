import json
from io import StringIO
from unittest.mock import patch

from finsre.cli import main


def test_connectors_list_outputs_json() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["connectors", "list"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload[0]["name"] == "gcp-billing"
    assert payload[0]["source_type"] == "cloud_billing_api"


def test_gcp_billing_api_preview_outputs_period_calls() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(
            [
                "gcp",
                "billing",
                "api-preview",
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-16",
            ]
        )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["period"] == {"start_date": "2026-05-01", "end_date": "2026-05-16"}
    assert payload["calls"][0] == "https://cloudbilling.googleapis.com/v1/billingAccounts"


def test_connectors_check_outputs_compatibility_report() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["connectors", "check", "--name", "gcp-billing"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload[0]["connector"] == "gcp-billing"
    assert payload[0]["status"] == "compatible"
    assert payload[0]["contract"]["provider_api"] == "cloudbilling.googleapis.com"
    assert payload[0]["contract"]["provider_api_version"] == "v1"


def test_components_list_outputs_deployable_boundaries() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["components", "list"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert [component["name"] for component in payload] == ["gcp-billing", "agent-router", "memory-store", "tracker"]


def test_gcp_billing_compatibility_event_outputs_event_envelope() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["gcp", "billing", "compatibility-event"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["type"] == "finsre.connector.compatibility.checked"
    assert payload["data"]["connector"] == "gcp-billing"


def test_discovery_plan_sku_outputs_probes_and_questions() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(
            [
                "discovery",
                "plan-sku",
                "--service",
                "Compute Engine",
                "--sku-id",
                "egress-1",
                "--sku-description",
                "Inter-region Egress",
                "--cost",
                "42.50",
                "--project-id",
                "prod-api",
            ]
        )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["classification"]["domain"] == "network_egress"
    assert [probe["kind"] for probe in payload["probes"]] == ["network", "telemetry", "change"]
    assert payload["questions"][0]["id"] == "prod-api:traffic-intent"

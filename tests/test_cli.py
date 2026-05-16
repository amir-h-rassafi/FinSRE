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

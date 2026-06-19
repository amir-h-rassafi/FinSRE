import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from finsre.cli import main
from finsre.llm.base import LLMResponse


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
    assert payload[0]["ok"] is True


def test_components_list_outputs_deployable_boundaries() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["components", "list"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert [component["name"] for component in payload] == [
        "gcp-billing",
        "local-csv-billing",
        "billing-discovery",
        "asset-discovery",
        "network-discovery",
        "telemetry-discovery",
        "change-discovery",
        "agent-router",
        "memory-store",
        "tracker",
    ]


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
                "--sku-description",
                "Inter-region Egress",
                "--project-id",
                "prod-api",
            ]
        )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["classification"]["domain"] == "network_egress"
    assert [probe["kind"] for probe in payload["probes"]] == ["billing", "network", "telemetry", "change"]
    assert payload["questions"][0]["id"] == "prod-api:traffic-intent"


def test_discovery_classify_sku_accepts_catalog_fields() -> None:
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(
            [
                "discovery",
                "classify-sku",
                "--service",
                "Compute Engine",
                "--sku-description",
                "Standard usage",
                "--resource-family",
                "Network",
                "--resource-group",
                "Egress",
            ]
        )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["domain"] == "network_egress"


def test_investigate_detect_flags_anomalies(tmp_path) -> None:
    csv_path = _write_spike_csv(tmp_path)
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["investigate", "detect", "--path", str(csv_path)])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["series_count"] == 1
    assert payload["anomaly_count"] == 1
    assert payload["profile"]["format"] == "row"
    assert payload["total_cost"] == "90"
    anomaly = payload["anomalies"][0]
    assert anomaly["classification"]["domain"] == "network_egress"
    assert anomaly["magnitude_pct"] == "100"
    assert anomaly["probe_names"] == [
        "billing-sku-context",
        "network-paths",
        "network-traffic",
        "network-config-changes",
    ]
    assert anomaly["question_count"] == 1
    assert "probes" not in anomaly
    assert "questions" not in anomaly


def test_investigate_detect_full_preserves_detailed_anomaly_payload(tmp_path) -> None:
    csv_path = _write_spike_csv(tmp_path)
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["investigate", "detect", "--path", str(csv_path), "--full"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["anomalies"][0]["anomaly"]["magnitude_pct"] == "100"
    assert payload["anomalies"][0]["classification"]["domain"] == "network_egress"


def test_investigate_detect_can_group_by_service(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    header = "service,sku,cost,project,usage start date"
    rows = [header]
    for day in range(1, 8):
        rows.append(f"Compute Engine,cpu,10,prod-api,2026-05-{day:02d}")
        rows.append(f"Compute Engine,ram,10,prod-api,2026-05-{day:02d}")
    rows.append("Compute Engine,cpu,20,prod-api,2026-05-08")
    rows.append("Compute Engine,ram,20,prod-api,2026-05-08")
    csv_path.write_text("\n".join(rows), encoding="utf-8")
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["investigate", "detect", "--path", str(csv_path), "--group-by", "service"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["group_by"] == "service"
    assert payload["series_count"] == 1
    assert payload["anomalies"][0]["sku"] == "__service_total__"


def test_investigate_detect_filters_small_anomalies(tmp_path) -> None:
    csv_path = _write_spike_csv(tmp_path)
    stdout = StringIO()

    with patch("sys.stdout", stdout):
        exit_code = main(["investigate", "detect", "--path", str(csv_path), "--min-cost", "11"])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["anomaly_count"] == 0


def test_investigate_run_uses_approved_llm_path(fake_langgraph, tmp_path) -> None:
    csv_path = _write_spike_csv(tmp_path)
    llm = FakeLLM()
    stdout = StringIO()

    with (
        patch("finsre.cli_commands.build_llm_client", return_value=llm),
        patch("sys.stdout", stdout),
    ):
        exit_code = main(["investigate", "run", "--approve-llm", "--path", str(csv_path)])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["anomaly_count"] == 1
    assert llm.calls == 1
    assert payload["investigations"][0]["result"]["summary"] == "Fake investigation summary."
    evidence = payload["investigations"][0]["result"]["evidence"][0]
    assert evidence["context"]["classification"]["domain"] == "network_egress"
    assert evidence["context"]["anomaly"]["magnitude_pct"] == "100"


def test_investigate_run_requires_approval(tmp_path) -> None:
    csv_path = _write_spike_csv(tmp_path)
    stderr = StringIO()

    with patch("sys.stderr", stderr):
        exit_code = main(["investigate", "run", "--path", str(csv_path)])

    assert exit_code == 1
    assert "Refusing to call LLM without --approve-llm" in stderr.getvalue()


def test_investigate_run_with_approval_fails_without_api_key(monkeypatch, tmp_path) -> None:
    csv_path = _write_spike_csv(tmp_path)
    stderr = StringIO()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("sys.stderr", stderr):
        exit_code = main(["investigate", "run", "--approve-llm", "--path", str(csv_path)])

    assert exit_code == 1
    assert "OPENAI_API_KEY is required" in stderr.getvalue()


def _write_spike_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "billing.csv"
    header = "service,sku,sku description,cost,project,usage start date"
    rows = [header]
    for day in range(1, 8):
        rows.append(f"Compute Engine,egress-1,Inter-region Egress,10,prod-api,2026-05-{day:02d}")
    rows.append("Compute Engine,egress-1,Inter-region Egress,20,prod-api,2026-05-08")
    csv_path.write_text("\n".join(rows), encoding="utf-8")
    return csv_path


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, _messages):
        self.calls += 1
        return LLMResponse(content="Fake investigation summary.", model="fake")

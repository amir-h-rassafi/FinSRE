from decimal import Decimal

from finsre.connectors.local_csv_billing import CsvBillingColumnMap, LocalCsvBillingConnector


def test_local_csv_connector_emits_cost_line_items(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text(
        "\n".join(
            [
                "service,sku,sku description,cost,project,region,usage start date",
                "Compute Engine,egress-1,Inter-region Egress,42.50,prod-api,europe-west1,2026-05-08",
            ]
        ),
        encoding="utf-8",
    )
    connector = LocalCsvBillingConnector(path=csv_path)

    items = list(connector.collect_costs())

    assert len(items) == 1
    assert items[0].service == "Compute Engine"
    assert items[0].sku == "egress-1"
    assert items[0].sku_description == "Inter-region Egress"
    assert items[0].cost == Decimal("42.50")
    assert items[0].project_id == "prod-api"
    assert items[0].region == "europe-west1"
    assert items[0].usage_start_date.isoformat() == "2026-05-08"


def test_local_csv_connector_supports_explicit_column_map(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Service Name,Resource ID,Unrounded Cost ($),Usage Start Date",
                "BigQuery,res-1,20.50,01-08-2024 22:24",
            ]
        ),
        encoding="utf-8",
    )
    connector = LocalCsvBillingConnector(
        path=csv_path,
        columns=CsvBillingColumnMap(service="Service Name", sku="Resource ID", cost="Unrounded Cost ($)"),
    )

    costs = list(connector.collect_costs())

    assert len(costs) == 1
    assert costs[0].service == "BigQuery"
    assert costs[0].usage_start_date.isoformat() == "2024-08-01"


def test_local_csv_connector_unpivots_daily_cost_matrix(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Service,SKU,2026-02-25,2026-02-26",
                "TOTAL,,10,12",
                "Artifact Registry,Inter Region Egress,1.25,0",
            ]
        ),
        encoding="utf-8",
    )
    connector = LocalCsvBillingConnector(path=csv_path)

    items = list(connector.collect_costs())

    assert len(items) == 1
    assert items[0].service == "Artifact Registry"
    assert items[0].sku == "Inter Region Egress"
    assert items[0].cost == Decimal("1.25")
    assert items[0].usage_start_date.isoformat() == "2026-02-25"


def test_local_csv_connector_compatibility_reports_missing_columns(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text("name,amount\nwrong,1\n", encoding="utf-8")
    connector = LocalCsvBillingConnector(path=csv_path)

    report = connector.check_compatibility()

    assert report.ok is False
    assert "service" in report.problems[0]

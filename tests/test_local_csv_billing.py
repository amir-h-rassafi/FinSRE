from decimal import Decimal

from finsre.connectors.local_csv_billing import CsvBillingColumnMap, LocalCsvBillingConnector
from finsre.models import SERVICE_TOTAL_SKU


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


def test_local_csv_connector_accepts_service_level_rows(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text(
        "\n".join(
            [
                "service,cost,usage start date",
                "Cloud SQL,100,2026-05-08",
            ]
        ),
        encoding="utf-8",
    )
    connector = LocalCsvBillingConnector(path=csv_path)

    items = list(connector.collect_costs())
    profile = connector.profile()

    assert len(items) == 1
    assert items[0].sku == SERVICE_TOTAL_SKU
    assert items[0].metadata["csv_grain"] == "service"
    assert profile.grain == "service"


def test_local_csv_connector_maps_optional_finops_fields(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text(
        "\n".join(
            [
                "service,sku,cost,credit,discount,usage amount,usage unit,invoice month,labels,tags,usage start date",
                "Compute Engine,vm-1,50,5,2,10,hour,2026-05,team=platform,env=prod,2026-05-08",
            ]
        ),
        encoding="utf-8",
    )
    connector = LocalCsvBillingConnector(path=csv_path)

    item = list(connector.collect_costs())[0]
    profile = connector.profile()

    assert item.credit == Decimal("5")
    assert item.discount == Decimal("2")
    assert item.usage_amount == Decimal("10")
    assert item.usage_unit == "hour"
    assert item.invoice_month == "2026-05"
    assert item.labels["team"] == "platform"
    assert item.tags["env"] == "prod"
    assert "credit" in profile.available_fields


def test_local_csv_connector_profile_reports_shape_and_warnings(tmp_path) -> None:
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

    profile = connector.profile()

    assert profile.format == "daily_matrix"
    assert profile.row_count == 2
    assert profile.item_count == 1
    assert profile.grain == "sku"
    assert profile.date_range[0].isoformat() == "2026-02-25"
    assert "CSV has no project/account attribution column." in profile.warnings


def test_local_csv_connector_compatibility_reports_missing_columns(tmp_path) -> None:
    csv_path = tmp_path / "billing.csv"
    csv_path.write_text("name,amount\nwrong,1\n", encoding="utf-8")
    connector = LocalCsvBillingConnector(path=csv_path)

    report = connector.check_compatibility()

    assert report.ok is False
    assert "service" in report.problems[0]

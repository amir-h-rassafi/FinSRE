from datetime import date, timedelta
from decimal import Decimal

from finsre.core.series import to_daily_series
from finsre.detectors.daily_baseline import DailyBaselineDetector
from finsre.models import CloudProvider, CostLineItem, CostSeries


def test_to_daily_series_groups_by_service_sku_project_currency() -> None:
    base = date(2026, 5, 1)
    rows = [
        _row(base, "Compute Engine", "egress-1", "prod-api", "USD", Decimal("10")),
        _row(base, "Compute Engine", "egress-1", "prod-api", "USD", Decimal("5")),
        _row(base + timedelta(days=1), "Compute Engine", "egress-1", "prod-api", "USD", Decimal("12")),
        _row(base, "Compute Engine", "egress-1", "prod-api", "EUR", Decimal("9")),
    ]

    series = sorted(to_daily_series(rows), key=lambda s: s.currency)

    assert len(series) == 2
    usd = series[1]
    assert usd.points == ((base, Decimal("15")), (base + timedelta(days=1), Decimal("12")))
    assert series[0].currency == "EUR"


def test_to_daily_series_picks_first_non_empty_sku_description() -> None:
    rows = [
        _row(date(2026, 5, 1), "BigQuery", "analysis-bytes", "p", "USD", Decimal("1"), description=None),
        _row(date(2026, 5, 2), "BigQuery", "analysis-bytes", "p", "USD", Decimal("1"), description="Analysis bytes"),
    ]

    series = to_daily_series(rows)

    assert series[0].sku_description == "Analysis bytes"


def test_daily_baseline_detector_flags_spike_above_threshold() -> None:
    series = _series([10, 10, 10, 10, 10, 10, 10, 20])

    anomaly = DailyBaselineDetector(threshold_pct=Decimal("25"), baseline_days=7).detect(series)

    assert anomaly is not None
    assert anomaly.inflection_date == date(2026, 5, 8)
    assert anomaly.baseline_cost == Decimal("10")
    assert anomaly.observed_cost == Decimal("20")
    assert anomaly.magnitude_pct == Decimal("100")


def test_daily_baseline_detector_returns_none_when_below_threshold() -> None:
    series = _series([10, 10, 10, 10, 10, 10, 10, 11])

    assert DailyBaselineDetector(threshold_pct=Decimal("25"), baseline_days=7).detect(series) is None


def test_daily_baseline_detector_skips_when_series_shorter_than_window() -> None:
    series = _series([10, 10, 10])

    assert DailyBaselineDetector(baseline_days=7).detect(series) is None


def test_daily_baseline_detector_picks_largest_movement() -> None:
    series = _series([10, 10, 10, 10, 10, 10, 10, 15, 100])

    anomaly = DailyBaselineDetector(threshold_pct=Decimal("25"), baseline_days=7).detect(series)

    assert anomaly is not None
    assert anomaly.inflection_date == date(2026, 5, 9)
    assert anomaly.observed_cost == Decimal("100")


def _row(
    usage_date: date,
    service: str,
    sku: str,
    project_id: str,
    currency: str,
    cost: Decimal,
    description: str | None = None,
) -> CostLineItem:
    return CostLineItem(
        provider=CloudProvider.GCP,
        account_id="acc-1",
        service=service,
        sku=sku,
        sku_description=description,
        usage_start_date=usage_date,
        currency=currency,
        cost=cost,
        project_id=project_id,
    )


def _series(daily_costs: list[int]) -> CostSeries:
    base = date(2026, 5, 1)
    points = tuple((base + timedelta(days=i), Decimal(value)) for i, value in enumerate(daily_costs))
    return CostSeries(
        service="Compute Engine",
        sku="egress-1",
        sku_description="Inter-region Egress",
        project_id="prod-api",
        currency="USD",
        points=points,
    )

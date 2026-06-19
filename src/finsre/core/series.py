from collections import defaultdict
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal

from finsre.models import SERVICE_TOTAL_SKU, CostLineItem, CostSeries

_SeriesKey = tuple[str, str, str | None, str]


def to_daily_series(rows: Iterable[CostLineItem], group_by: str = "sku") -> list[CostSeries]:
    """Group cost line items into daily series.

    `group_by="sku"` preserves the current SKU-level behavior.
    `group_by="service"` rolls all SKUs into a service-level series.
    """
    if group_by not in {"sku", "service"}:
        raise ValueError("group_by must be 'sku' or 'service'.")

    totals: dict[_SeriesKey, dict] = defaultdict(lambda: {"description": None, "by_date": defaultdict(Decimal)})
    for row in rows:
        sku = SERVICE_TOTAL_SKU if group_by == "service" else row.sku
        bucket = totals[(row.service, sku, row.project_id, row.currency)]
        bucket["by_date"][row.usage_start_date] += row.cost
        if group_by == "sku" and bucket["description"] is None and row.sku_description:
            bucket["description"] = row.sku_description

    series: list[CostSeries] = []
    for (service, sku, project_id, currency), bucket in totals.items():
        points = tuple(sorted(bucket["by_date"].items()))
        series.append(
            CostSeries(
                service=service,
                sku=sku,
                sku_description=bucket["description"],
                project_id=project_id,
                currency=currency,
                points=points,
            )
        )
    return series


def filter_series_by_lookback(series: Iterable[CostSeries], lookback_days: int | None) -> list[CostSeries]:
    if lookback_days is None:
        return list(series)
    if lookback_days < 1:
        raise ValueError("lookback_days must be >= 1.")

    all_days = [day for item in series for day, _ in item.points]
    if not all_days:
        return list(series)
    start_date = max(all_days) - timedelta(days=lookback_days - 1)

    filtered: list[CostSeries] = []
    for item in series:
        points = tuple((day, cost) for day, cost in item.points if day >= start_date)
        if points:
            filtered.append(
                CostSeries(
                    service=item.service,
                    sku=item.sku,
                    sku_description=item.sku_description,
                    project_id=item.project_id,
                    currency=item.currency,
                    points=points,
                )
            )
    return filtered

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from finsre.models import CostLineItem, CostSeries

_SeriesKey = tuple[str, str, str | None, str]


def to_daily_series(rows: Iterable[CostLineItem]) -> list[CostSeries]:
    """Group cost line items into one daily series per (service, sku, project, currency)."""
    totals: dict[_SeriesKey, dict] = defaultdict(lambda: {"description": None, "by_date": defaultdict(Decimal)})
    for row in rows:
        bucket = totals[(row.service, row.sku, row.project_id, row.currency)]
        bucket["by_date"][row.usage_start_date] += row.cost
        if bucket["description"] is None and row.sku_description:
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

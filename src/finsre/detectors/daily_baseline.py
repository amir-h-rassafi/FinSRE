from decimal import Decimal
from statistics import mean

from finsre.models import Anomaly, CostSeries

_HUNDRED = Decimal("100")


class DailyBaselineDetector:
    """Flag the day whose cost exceeds the trailing window mean by `threshold_pct`."""

    def __init__(self, threshold_pct: Decimal = Decimal("25"), baseline_days: int = 7) -> None:
        if baseline_days < 1:
            raise ValueError("baseline_days must be >= 1")
        self._threshold_pct = threshold_pct
        self._baseline_days = baseline_days

    def detect(self, series: CostSeries) -> Anomaly | None:
        points = series.points
        if len(points) <= self._baseline_days:
            return None
        best: tuple[Decimal, int, Decimal] | None = None
        for index in range(self._baseline_days, len(points)):
            window = [cost for _, cost in points[index - self._baseline_days : index]]
            baseline = Decimal(mean(window))
            if baseline <= 0:
                continue
            observed = points[index][1]
            magnitude = (observed - baseline) / baseline * _HUNDRED
            if magnitude >= self._threshold_pct and (best is None or magnitude > best[0]):
                best = (magnitude, index, baseline)
        if best is None:
            return None
        magnitude, index, baseline = best
        observed_date, observed_cost = points[index]
        return Anomaly(
            series=series,
            inflection_date=observed_date,
            baseline_cost=baseline,
            observed_cost=observed_cost,
            magnitude_pct=magnitude,
        )

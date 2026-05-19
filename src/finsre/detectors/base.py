from typing import Protocol

from finsre.models import Anomaly, CostSeries


class AnomalyDetector(Protocol):
    def detect(self, series: CostSeries) -> Anomaly | None:
        """Return the most significant anomaly in the series, if any."""

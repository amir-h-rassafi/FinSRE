from datetime import date

from finsre.models import TimePeriod


def parse_period(start_date: str, end_date: str) -> TimePeriod:
    return TimePeriod(
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date),
    )

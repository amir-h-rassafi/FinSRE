from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Any


class CloudProvider(StrEnum):
    GCP = "gcp"


@dataclass(frozen=True)
class ConnectorContract:
    """Small compatibility contract for connector outputs.

    This is a FinSRE contract, not an upstream cloud standard.
    """

    version: str
    upstream: str
    schema: str
    docs_url: str | None = None


@dataclass(frozen=True)
class CompatibilityReport:
    connector: str
    ok: bool
    contract: ConnectorContract
    checked_live: bool
    problems: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorDescriptor:
    name: str
    provider: CloudProvider
    source_type: str
    capabilities: tuple[str, ...]
    contract: ConnectorContract
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TimePeriod:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")

    @property
    def start_time_rfc3339(self) -> str:
        return _utc_midnight_rfc3339(self.start_date)

    @property
    def end_time_rfc3339(self) -> str:
        return _utc_midnight_rfc3339(self.end_date)


def _utc_midnight_rfc3339(value: date) -> str:
    return datetime.combine(value, time.min, tzinfo=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class CostLineItem:
    provider: CloudProvider
    account_id: str
    service: str
    sku: str
    usage_start_date: date
    currency: str
    cost: Decimal
    project_id: str | None = None
    region: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    source: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

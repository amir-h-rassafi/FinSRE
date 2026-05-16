from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any


class CloudProvider(StrEnum):
    GCP = "gcp"
    AWS = "aws"
    AZURE = "azure"
    GENERIC = "generic"


class ConnectorStatus(StrEnum):
    CONFIGURED = "configured"
    NEEDS_CONFIGURATION = "needs_configuration"
    UNAVAILABLE = "unavailable"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    NEEDS_CONFIGURATION = "needs_configuration"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ApiContract:
    provider_api: str
    provider_api_version: str
    connector_contract_version: str
    min_supported_contract_version: str
    docs_url: str
    stability: str = "public"


@dataclass(frozen=True)
class CompatibilityReport:
    connector: str
    status: CompatibilityStatus
    contract: ApiContract
    checked_live: bool
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorDescriptor:
    name: str
    provider: CloudProvider
    source_type: str
    status: ConnectorStatus
    capabilities: tuple[str, ...]
    contract: ApiContract
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
        return datetime.combine(self.start_date, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    @property
    def end_time_rfc3339(self) -> str:
        return datetime.combine(self.end_date, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


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
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

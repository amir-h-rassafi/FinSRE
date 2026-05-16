from dataclasses import dataclass, field
from datetime import date, datetime, timezone
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


@dataclass(frozen=True)
class ConnectorDescriptor:
    name: str
    provider: CloudProvider
    source_type: str
    status: ConnectorStatus
    capabilities: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)


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

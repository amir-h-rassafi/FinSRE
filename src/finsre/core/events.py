from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class EventType(StrEnum):
    CONNECTOR_COMPATIBILITY_CHECKED = "finsre.connector.compatibility.checked"
    CONNECTOR_DISCOVERED = "finsre.connector.discovered"
    BILLING_ACCOUNT_DISCOVERED = "finsre.billing.account.discovered"
    PROJECT_BILLING_DISCOVERED = "finsre.billing.project.discovered"
    SKU_PRICING_DISCOVERED = "finsre.billing.sku_pricing.discovered"
    INVESTIGATION_REQUESTED = "finsre.investigation.requested"
    INVESTIGATION_UPDATED = "finsre.investigation.updated"
    RECOMMENDATION_CREATED = "finsre.recommendation.created"
    MEMORY_RECORD_CREATED = "finsre.memory.record.created"


@dataclass(frozen=True)
class EventEnvelope:
    """CloudEvents-inspired envelope used between deployable FinSRE parts."""

    type: str
    source: str
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    specversion: str = "1.0"
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    subject: str | None = None
    datacontenttype: str = "application/json"
    dataschema: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


def new_event(
    event_type: EventType | str,
    source: str,
    data: dict[str, Any],
    *,
    subject: str | None = None,
    dataschema: str | None = None,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        type=str(event_type),
        source=source,
        data=data,
        subject=subject,
        dataschema=dataschema,
        correlation_id=correlation_id,
        trace_id=trace_id,
    )

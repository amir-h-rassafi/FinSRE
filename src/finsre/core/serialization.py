from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from finsre.core.components import ComponentManifest
from finsre.core.events import EventEnvelope
from finsre.discovery.probes import DiscoveryProbe
from finsre.discovery.questions import Question
from finsre.discovery.sku import BillingSkuSignal, SkuClassification
from finsre.models import ApiContract, CompatibilityReport, ConnectorDescriptor


def connector_to_dict(descriptor: ConnectorDescriptor) -> dict[str, Any]:
    return {
        "name": descriptor.name,
        "provider": descriptor.provider.value,
        "source_type": descriptor.source_type,
        "status": descriptor.status.value,
        "capabilities": list(descriptor.capabilities),
        "contract": contract_to_dict(descriptor.contract),
        "details": descriptor.details,
    }


def compatibility_to_dict(report: CompatibilityReport) -> dict[str, Any]:
    return {
        "connector": report.connector,
        "status": report.status.value,
        "checked_live": report.checked_live,
        "contract": contract_to_dict(report.contract),
        "messages": list(report.messages),
    }


def contract_to_dict(contract: ApiContract) -> dict[str, Any]:
    return {
        "provider_api": contract.provider_api,
        "provider_api_version": contract.provider_api_version,
        "connector_contract_version": contract.connector_contract_version,
        "min_supported_contract_version": contract.min_supported_contract_version,
        "docs_url": contract.docs_url,
        "stability": contract.stability,
    }


def component_to_dict(manifest: ComponentManifest) -> dict[str, Any]:
    return {
        "name": manifest.name,
        "kind": manifest.kind.value,
        "version": manifest.version,
        "input_events": list(manifest.input_events),
        "output_events": list(manifest.output_events),
        "deploy_modes": [mode.value for mode in manifest.deploy_modes],
        "dependencies": list(manifest.dependencies),
        "description": manifest.description,
    }


def event_to_dict(event: EventEnvelope) -> dict[str, Any]:
    return {
        "specversion": event.specversion,
        "id": event.id,
        "type": event.type,
        "source": event.source,
        "subject": event.subject,
        "time": event.time,
        "datacontenttype": event.datacontenttype,
        "dataschema": event.dataschema,
        "correlation_id": event.correlation_id,
        "trace_id": event.trace_id,
        "data": event.data,
    }


def sku_signal_to_dict(signal: BillingSkuSignal) -> dict[str, Any]:
    return {
        "service": signal.service,
        "sku_id": signal.sku_id,
        "sku_description": signal.sku_description,
        "cost": signal.cost,
        "currency": signal.currency,
        "project_id": signal.project_id,
        "usage_amount": signal.usage_amount,
        "usage_unit": signal.usage_unit,
        "labels": signal.labels,
    }


def sku_classification_to_dict(classification: SkuClassification) -> dict[str, Any]:
    return {
        "domain": classification.domain.value,
        "confidence": classification.confidence,
        "reasons": list(classification.reasons),
        "signal": sku_signal_to_dict(classification.signal),
    }


def discovery_probe_to_dict(probe: DiscoveryProbe) -> dict[str, Any]:
    return {
        "kind": probe.kind.value,
        "name": probe.name,
        "reason": probe.reason,
        "required": probe.required,
    }


def question_to_dict(question: Question) -> dict[str, Any]:
    return {
        "id": question.id,
        "entity_id": question.entity_id,
        "text": question.text,
        "reason": question.reason,
        "blocks_recommendation": question.blocks_recommendation,
    }


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

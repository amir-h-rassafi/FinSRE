import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any

from finsre.agents.investigation import InvestigationAgent
from finsre.agents.langgraph_investigation import LangGraphInvestigationAgent
from finsre.config import get_settings
from finsre.connectors.gcp_billing import GcpBillingConnector
from finsre.connectors.local_csv_billing import CsvBillingColumnMap, LocalCsvBillingConnector
from finsre.connectors.registry import build_default_registry
from finsre.core.catalog import build_component_catalog
from finsre.core.serialization import (
    compatibility_to_dict,
    component_to_dict,
    connector_to_dict,
    cost_line_item_to_dict,
    discovery_probe_to_dict,
    event_to_dict,
    question_to_dict,
    sku_classification_to_dict,
)
from finsre.core.time import parse_period
from finsre.discovery.sku import BillingSkuSignal, SkuClassifier
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.errors import ApprovalRequiredError
from finsre.llm.factory import build_llm_client


def list_connectors(_: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    return [connector_to_dict(connector.describe()) for connector in registry.list()]


def list_components(_: argparse.Namespace) -> list[dict[str, Any]]:
    return [component_to_dict(component) for component in build_component_catalog(get_settings())]


def classify_sku(args: argparse.Namespace) -> dict[str, Any]:
    signal = _sku_signal_from_args(args)
    return sku_classification_to_dict(SkuClassifier().classify(signal))


def plan_sku_discovery(args: argparse.Namespace) -> dict[str, Any]:
    signal = _sku_signal_from_args(args)
    plan = SkuDiscoveryWorkflow().plan(signal)
    return {
        "classification": sku_classification_to_dict(plan.classification),
        "probes": [discovery_probe_to_dict(probe) for probe in plan.probes],
        "questions": [question_to_dict(question) for question in plan.questions],
    }


def investigate_sku_draft(args: argparse.Namespace) -> dict[str, Any]:
    signal = _sku_signal_from_args(args)
    draft = InvestigationAgent().draft_from_sku(signal)
    return {
        "llm_required": draft.llm_required,
        "approval_reason": draft.approval_reason,
        "classification": sku_classification_to_dict(draft.discovery_plan.classification),
        "probes": [discovery_probe_to_dict(probe) for probe in draft.discovery_plan.probes],
        "questions": [question_to_dict(question) for question in draft.discovery_plan.questions],
    }


def investigate_sku_run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.approve_llm:
        raise ApprovalRequiredError("Refusing to call LLM without --approve-llm.")
    signal = _sku_signal_from_args(args)
    agent = LangGraphInvestigationAgent(llm_client=build_llm_client(get_settings()))
    result = agent.run_from_sku(signal)
    return {
        "capability": result.capability.value,
        "summary": result.summary,
        "confidence": result.confidence,
        "evidence": list(result.evidence),
    }


def investigate_csv_draft(args: argparse.Namespace) -> dict[str, Any]:
    connector = local_csv_billing_connector(args)
    agent = InvestigationAgent()
    drafts = []
    for signal in connector.collect_sku_signals(limit=args.limit):
        draft = agent.draft_from_sku(signal)
        drafts.append(
            {
                "llm_required": draft.llm_required,
                "approval_reason": draft.approval_reason,
                "classification": sku_classification_to_dict(draft.discovery_plan.classification),
                "probes": [discovery_probe_to_dict(probe) for probe in draft.discovery_plan.probes],
                "questions": [question_to_dict(question) for question in draft.discovery_plan.questions],
            }
        )
    return {
        "connector": connector.name,
        "path": str(connector.path),
        "count": len(drafts),
        "drafts": drafts,
    }


def check_connectors(args: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    if args.name == LocalCsvBillingConnector.name and args.path:
        connectors = [LocalCsvBillingConnector(path=args.path)]
    else:
        connectors = [registry.get(args.name)] if args.name else registry.list()
    return [compatibility_to_dict(connector.check_compatibility(live=args.live)) for connector in connectors]


def preview_csv_costs(args: argparse.Namespace) -> dict[str, Any]:
    connector = local_csv_billing_connector(args)
    items = []
    for item in connector.collect_costs():
        items.append(cost_line_item_to_dict(item))
        if len(items) >= args.limit:
            break
    return {
        "connector": connector.name,
        "path": str(connector.path),
        "count": len(items),
        "items": items,
    }


def gcp_billing_api_preview(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    period = parse_period(args.start_date, args.end_date)
    return {
        "connector": connector.name,
        "period": {
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "calls": connector.preview_api_calls(period),
    }


def gcp_billing_compatibility_event(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return event_to_dict(connector.compatibility_event(live=args.live))


def gcp_billing_accounts(_: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_billing_accounts()}


def gcp_billing_projects(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_projects(args.billing_account)}


def gcp_billing_services(_: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_services()}


def gcp_billing_skus(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    period = parse_period(args.start_date, args.end_date)
    return {
        "connector": connector.name,
        "data": connector.list_skus_for_service(args.service_name, period, args.currency_code),
    }


def gcp_billing_connector() -> GcpBillingConnector:
    settings = get_settings()
    return GcpBillingConnector(
        billing_account=settings.gcp_billing_account,
        currency_code=settings.gcp_billing_currency,
    )


def local_csv_billing_connector(args: argparse.Namespace) -> LocalCsvBillingConnector:
    return LocalCsvBillingConnector(
        path=Path(args.path),
        columns=CsvBillingColumnMap(
            service=args.service_column,
            sku=args.sku_column,
            sku_description=args.sku_description_column,
            cost=args.cost_column,
            currency=args.currency_column,
            project_id=args.project_column,
            region=args.region_column,
            usage_amount=args.usage_amount_column,
            usage_unit=args.usage_unit_column,
            usage_start_date=args.usage_start_date_column,
        ),
        currency=args.currency,
    )


def _sku_signal_from_args(args: argparse.Namespace) -> BillingSkuSignal:
    return BillingSkuSignal(
        service=args.service,
        sku_id=args.sku_id,
        sku_description=args.sku_description,
        cost=Decimal(args.cost),
        currency=args.currency,
        project_id=args.project_id,
    )

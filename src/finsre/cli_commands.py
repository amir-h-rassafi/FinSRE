import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any

from finsre.agents.base import AgentResult
from finsre.agents.investigation import InvestigationContext
from finsre.agents.langgraph_investigation import LangGraphInvestigationAgent
from finsre.config import get_settings
from finsre.connectors.gcp_billing import GcpBillingApiConnector
from finsre.connectors.local_csv_billing import CsvBillingColumnMap, LocalCsvBillingConnector
from finsre.connectors.registry import build_default_registry
from finsre.core.catalog import build_component_catalog
from finsre.core.serialization import (
    anomaly_to_dict,
    compatibility_to_dict,
    component_to_dict,
    connector_to_dict,
    cost_line_item_to_dict,
    discovery_probe_to_dict,
    event_to_dict,
    question_to_dict,
    sku_classification_to_dict,
)
from finsre.core.series import to_daily_series
from finsre.core.time import parse_period
from finsre.detectors.daily_baseline import DailyBaselineDetector
from finsre.discovery.sku import SkuClassifier
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.errors import ApprovalRequiredError
from finsre.llm.factory import build_llm_client


def list_connectors(_: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    return [connector_to_dict(connector.describe()) for connector in registry.list()]


def list_components(_: argparse.Namespace) -> list[dict[str, Any]]:
    return [component_to_dict(component) for component in build_component_catalog(get_settings())]


def classify_sku(args: argparse.Namespace) -> dict[str, Any]:
    return sku_classification_to_dict(SkuClassifier().classify(args.service, args.sku_description))


def plan_sku_discovery(args: argparse.Namespace) -> dict[str, Any]:
    plan = SkuDiscoveryWorkflow().plan_for_sku(args.service, args.sku_description, args.project_id)
    return {
        "classification": sku_classification_to_dict(plan.classification),
        "probes": [discovery_probe_to_dict(probe) for probe in plan.probes],
        "questions": [question_to_dict(question) for question in plan.questions],
    }


def investigate_detect(args: argparse.Namespace) -> dict[str, Any]:
    pipeline = _build_pipeline(args)
    drafts = []
    for anomaly, plan in pipeline.find_anomalies_with_plans():
        drafts.append(
            {
                "anomaly": anomaly_to_dict(anomaly),
                "classification": sku_classification_to_dict(plan.classification),
                "probes": [discovery_probe_to_dict(probe) for probe in plan.probes],
                "questions": [question_to_dict(question) for question in plan.questions],
            }
        )
    return {
        "connector": pipeline.connector.name,
        "path": str(pipeline.connector.path),
        "series_count": pipeline.series_count,
        "anomaly_count": len(drafts),
        "anomalies": drafts,
    }


def investigate_run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.approve_llm:
        raise ApprovalRequiredError("Refusing to call LLM without --approve-llm.")
    pipeline = _build_pipeline(args)
    agent = _langgraph_investigation_agent()
    investigations = []
    for anomaly, plan in pipeline.find_anomalies_with_plans():
        context = InvestigationContext(anomaly=anomaly, discovery_plan=plan)
        investigations.append(
            {
                "anomaly": anomaly_to_dict(anomaly),
                "result": _agent_result_to_dict(agent.investigate(context)),
            }
        )
    return {
        "connector": pipeline.connector.name,
        "path": str(pipeline.connector.path),
        "series_count": pipeline.series_count,
        "anomaly_count": len(investigations),
        "investigations": investigations,
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


def gcp_billing_connector() -> GcpBillingApiConnector:
    settings = get_settings()
    return GcpBillingApiConnector(
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
            usage_start_date=args.usage_start_date_column,
        ),
        currency=args.currency,
    )


class _Pipeline:
    def __init__(self, connector: LocalCsvBillingConnector, args: argparse.Namespace) -> None:
        self.connector = connector
        self.series = to_daily_series(connector.collect_costs())
        self._workflow = SkuDiscoveryWorkflow()
        self._detector = DailyBaselineDetector(
            threshold_pct=Decimal(str(args.threshold_pct)),
            baseline_days=args.baseline_days,
        )

    @property
    def series_count(self) -> int:
        return len(self.series)

    def find_anomalies_with_plans(self):
        for series in self.series:
            anomaly = self._detector.detect(series)
            if anomaly is None:
                continue
            yield anomaly, self._workflow.plan_for_anomaly(anomaly)


def _build_pipeline(args: argparse.Namespace) -> _Pipeline:
    return _Pipeline(local_csv_billing_connector(args), args)


def _langgraph_investigation_agent() -> LangGraphInvestigationAgent:
    return LangGraphInvestigationAgent(llm_client=build_llm_client(get_settings()))


def _agent_result_to_dict(result: AgentResult) -> dict[str, Any]:
    return {
        "capability": result.capability.value,
        "summary": result.summary,
        "confidence": result.confidence,
        "evidence": list(result.evidence),
    }

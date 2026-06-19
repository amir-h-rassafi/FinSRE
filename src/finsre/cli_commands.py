import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any

from finsre.agents.base import AgentResult
from finsre.agents.investigation import InvestigationContext
from finsre.agents.langgraph_investigation import LangGraphInvestigationAgent
from finsre.config import get_settings
from finsre.connectors.gcp_billing import GcpBillingApiConnector
from finsre.connectors.local_csv_billing import CsvBillingColumnMap, CsvBillingProfile, LocalCsvBillingConnector
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
from finsre.core.series import filter_series_by_lookback, to_daily_series
from finsre.core.time import parse_period
from finsre.detectors.daily_baseline import DailyBaselineDetector
from finsre.discovery.sku import GcpSkuClassifier
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.errors import ApprovalRequiredError
from finsre.llm.factory import build_llm_client
from finsre.models import Anomaly, CostSeries


def list_connectors(_: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    return [connector_to_dict(connector.describe()) for connector in registry.list()]


def list_components(_: argparse.Namespace) -> list[dict[str, Any]]:
    return [component_to_dict(component) for component in build_component_catalog(get_settings())]


def classify_sku(args: argparse.Namespace) -> dict[str, Any]:
    return sku_classification_to_dict(
        GcpSkuClassifier().classify(args.service, args.sku_description, **_sku_classifier_kwargs(args))
    )


def plan_sku_discovery(args: argparse.Namespace) -> dict[str, Any]:
    plan = SkuDiscoveryWorkflow().plan_for_sku(
        args.service,
        args.sku_description,
        args.project_id,
        **_sku_classifier_kwargs(args),
    )
    return {
        "classification": sku_classification_to_dict(plan.classification),
        "probes": [discovery_probe_to_dict(probe) for probe in plan.probes],
        "questions": [question_to_dict(question) for question in plan.questions],
    }


def investigate_detect(args: argparse.Namespace) -> dict[str, Any]:
    pipeline = _build_local_csv_investigation_pipeline(args)
    drafts = _anomaly_drafts(pipeline)
    if args.full:
        return _detailed_detection_payload(pipeline, drafts)
    return _summary_detection_payload(pipeline, drafts)


def investigate_run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.approve_llm:
        raise ApprovalRequiredError("Refusing to call LLM without --approve-llm.")
    pipeline = _build_local_csv_investigation_pipeline(args)
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


def _sku_classifier_kwargs(args: argparse.Namespace) -> dict[str, str | None]:
    return {
        "sku_id": args.sku_id,
        "service_id": args.service_id,
        "resource_family": args.resource_family,
        "resource_group": args.resource_group,
        "usage_type": args.usage_type,
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
            credit=args.credit_column,
            discount=args.discount_column,
            usage_amount=args.usage_amount_column,
            usage_unit=args.usage_unit_column,
            invoice_month=args.invoice_month_column,
            currency=args.currency_column,
            project_id=args.project_column,
            region=args.region_column,
            labels=args.labels_column,
            tags=args.tags_column,
            usage_start_date=args.usage_start_date_column,
        ),
        currency=args.currency,
    )


class _LocalCsvInvestigationPipeline:
    def __init__(self, connector: LocalCsvBillingConnector, args: argparse.Namespace) -> None:
        self.connector = connector
        self.profile = connector.profile()
        self.group_by = args.group_by
        self.lookback_days = args.lookback_days
        self.min_cost = Decimal(str(args.min_cost))
        self.threshold_pct = Decimal(str(args.threshold_pct))
        self.baseline_days = args.baseline_days
        self.rows = tuple(connector.collect_costs())
        self.series = filter_series_by_lookback(
            to_daily_series(self.rows, group_by=args.group_by),
            args.lookback_days,
        )
        self._workflow = SkuDiscoveryWorkflow()
        self._detector = DailyBaselineDetector(
            threshold_pct=self.threshold_pct,
            baseline_days=args.baseline_days,
        )

    @property
    def series_count(self) -> int:
        return len(self.series)

    def find_anomalies_with_plans(self):
        for series in self.series:
            anomaly = self._detector.detect(series)
            if anomaly is None or _anomaly_delta(anomaly) < self.min_cost:
                continue
            yield anomaly, self._workflow.plan_for_anomaly(anomaly)


def _anomaly_drafts(pipeline: _LocalCsvInvestigationPipeline) -> list[dict[str, Any]]:
    drafts = []
    for anomaly, plan in pipeline.find_anomalies_with_plans():
        drafts.append(
            {
                "anomaly": anomaly,
                "classification": plan.classification,
                "probes": plan.probes,
                "questions": plan.questions,
            }
        )
    drafts.sort(key=lambda draft: _anomaly_delta(draft["anomaly"]), reverse=True)
    return drafts


def _detailed_detection_payload(
    pipeline: _LocalCsvInvestigationPipeline,
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "connector": pipeline.connector.name,
        "path": str(pipeline.connector.path),
        "profile": _csv_profile_to_dict(pipeline.profile),
        "group_by": pipeline.group_by,
        "lookback_days": pipeline.lookback_days,
        "min_cost": pipeline.min_cost,
        "series_count": pipeline.series_count,
        "anomaly_count": len(drafts),
        "anomalies": [_detailed_anomaly_draft(draft) for draft in drafts],
    }


def _summary_detection_payload(
    pipeline: _LocalCsvInvestigationPipeline,
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "connector": pipeline.connector.name,
        "path": str(pipeline.connector.path),
        "profile": _csv_profile_to_dict(pipeline.profile),
        "group_by": pipeline.group_by,
        "lookback_days": pipeline.lookback_days,
        "min_cost": pipeline.min_cost,
        "threshold_pct": pipeline.threshold_pct,
        "baseline_days": pipeline.baseline_days,
        "series_count": pipeline.series_count,
        "anomaly_count": len(drafts),
        "total_cost": _total_series_cost(pipeline.series),
        "top_services": _top_services(pipeline.series),
        "anomalies": [_summary_anomaly_draft(draft) for draft in drafts],
        "attribution_gaps": _attribution_gaps(pipeline),
    }


def _detailed_anomaly_draft(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "anomaly": anomaly_to_dict(draft["anomaly"]),
        "classification": sku_classification_to_dict(draft["classification"]),
        "probes": [discovery_probe_to_dict(probe) for probe in draft["probes"]],
        "questions": [question_to_dict(question) for question in draft["questions"]],
    }


def _summary_anomaly_draft(draft: dict[str, Any]) -> dict[str, Any]:
    anomaly: Anomaly = draft["anomaly"]
    series = anomaly.series
    probes = draft["probes"]
    questions = draft["questions"]
    return {
        "service": series.service,
        "sku": series.sku,
        "project_id": series.project_id,
        "currency": series.currency,
        "inflection_date": anomaly.inflection_date,
        "baseline_cost": anomaly.baseline_cost,
        "observed_cost": anomaly.observed_cost,
        "delta_cost": _anomaly_delta(anomaly),
        "magnitude_pct": anomaly.magnitude_pct,
        "classification": sku_classification_to_dict(draft["classification"]),
        "probe_names": [probe.name for probe in probes],
        "required_probe_count": sum(1 for probe in probes if probe.required),
        "question_count": len(questions),
        "blocking_question_count": sum(1 for question in questions if question.blocks_recommendation),
    }


def _csv_profile_to_dict(profile: CsvBillingProfile) -> dict[str, Any]:
    return {
        "path": profile.path,
        "format": profile.format,
        "row_count": profile.row_count,
        "item_count": profile.item_count,
        "grain": profile.grain,
        "date_range": list(profile.date_range) if profile.date_range else None,
        "available_fields": list(profile.available_fields),
        "missing_optional_fields": list(profile.missing_optional_fields),
        "warnings": list(profile.warnings),
    }


def _top_services(series: tuple[CostSeries, ...] | list[CostSeries], limit: int = 10) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str | None, str], Decimal] = {}
    for item in series:
        key = (item.service, item.project_id, item.currency)
        totals[key] = totals.get(key, Decimal("0")) + _series_total(item)
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [
        {"service": service, "project_id": project_id, "currency": currency, "cost": cost}
        for (service, project_id, currency), cost in ranked
    ]


def _total_series_cost(series: tuple[CostSeries, ...] | list[CostSeries]) -> Decimal:
    return sum((_series_total(item) for item in series), Decimal("0"))


def _series_total(series: CostSeries) -> Decimal:
    return sum((cost for _, cost in series.points), Decimal("0"))


def _anomaly_delta(anomaly: Anomaly) -> Decimal:
    return anomaly.observed_cost - anomaly.baseline_cost


def _attribution_gaps(pipeline: _LocalCsvInvestigationPipeline) -> list[str]:
    gaps = []
    if "project_id" in pipeline.profile.missing_optional_fields:
        gaps.append("missing_project")
    if pipeline.profile.grain in {"service", "mixed"}:
        gaps.append("missing_sku_for_some_rows")
    if "credit" in pipeline.profile.missing_optional_fields and "discount" in pipeline.profile.missing_optional_fields:
        gaps.append("missing_credit_discount")
    if (
        "usage_amount" in pipeline.profile.missing_optional_fields
        or "usage_unit" in pipeline.profile.missing_optional_fields
    ):
        gaps.append("missing_usage")
    return gaps


def _build_local_csv_investigation_pipeline(args: argparse.Namespace) -> _LocalCsvInvestigationPipeline:
    return _LocalCsvInvestigationPipeline(local_csv_billing_connector(args), args)


def _langgraph_investigation_agent() -> LangGraphInvestigationAgent:
    return LangGraphInvestigationAgent(llm_client=build_llm_client(get_settings()))


def _agent_result_to_dict(result: AgentResult) -> dict[str, Any]:
    return {
        "capability": result.capability.value,
        "summary": result.summary,
        "confidence": result.confidence,
        "evidence": list(result.evidence),
    }

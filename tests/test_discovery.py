from datetime import date
from decimal import Decimal

from finsre.discovery.facts import ContextFact, FactSource
from finsre.discovery.probes import ProbeKind, ProbePlanner
from finsre.discovery.sku import SkuClassifier, SkuDomain
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.models import Anomaly, CostSeries


def test_sku_classifier_identifies_network_egress() -> None:
    classification = SkuClassifier().classify(
        "Compute Engine",
        "Inter-region Egress from europe-west2 to us-central1",
    )

    assert classification.domain == SkuDomain.NETWORK_EGRESS
    assert classification.confidence == 0.75
    assert "egress" in classification.reasons


def test_sku_classifier_routes_gcp_service_families() -> None:
    examples = [
        ("Gemini API", SkuDomain.AI),
        ("Cloud Pub/Sub", SkuDomain.MESSAGING),
        ("Cloud Dataflow", SkuDomain.DATA_PROCESSING),
        ("Security Command Center", SkuDomain.SECURITY),
        ("Places API", SkuDomain.API_PLATFORM),
        ("Cloud Run", SkuDomain.SERVERLESS),
        ("Cloud Memorystore for Redis", SkuDomain.CACHE),
        ("Cloud DNS", SkuDomain.DNS),
    ]

    for service, domain in examples:
        assert SkuClassifier().classify(service, "Standard usage").domain == domain


def test_probe_planner_maps_network_egress_to_network_telemetry_and_change() -> None:
    classification = SkuClassifier().classify("Compute Engine", "Inter-region Egress")

    probes = ProbePlanner().plan(classification)

    assert [probe.kind for probe in probes] == [ProbeKind.NETWORK, ProbeKind.TELEMETRY, ProbeKind.CHANGE]


def test_workflow_plan_for_anomaly_asks_for_network_intent() -> None:
    anomaly = _build_anomaly(service="Compute Engine", sku_description="Inter-region Egress", project_id="prod-api")

    plan = SkuDiscoveryWorkflow().plan_for_anomaly(anomaly)

    assert plan.questions[0].id == "prod-api:traffic-intent"
    assert "HA, migration, or customer traffic" in plan.questions[0].text


def test_workflow_skips_network_intent_when_fact_exists() -> None:
    anomaly = _build_anomaly(service="Compute Engine", sku_description="Inter-region Egress", project_id="prod-api")
    fact = ContextFact(
        entity_id="prod-api",
        fact_type="traffic_intent",
        value="required for migration",
        source=FactSource.USER,
        confidence=0.95,
    )

    plan = SkuDiscoveryWorkflow().plan_for_anomaly(anomaly, facts=(fact,))

    assert plan.questions == ()


def test_workflow_plan_for_sku_supports_debug_inputs() -> None:
    plan = SkuDiscoveryWorkflow().plan_for_sku(
        service="Compute Engine",
        sku_description="Inter-region Egress",
        project_id="prod-api",
    )

    assert plan.classification.domain == SkuDomain.NETWORK_EGRESS
    assert plan.questions[0].id == "prod-api:traffic-intent"


def _build_anomaly(service: str, sku_description: str, project_id: str | None) -> Anomaly:
    series = CostSeries(
        service=service,
        sku="sku-1",
        sku_description=sku_description,
        project_id=project_id,
        currency="USD",
        points=(),
    )
    return Anomaly(
        series=series,
        inflection_date=date(2026, 5, 10),
        baseline_cost=Decimal("10"),
        observed_cost=Decimal("20"),
        magnitude_pct=Decimal("100"),
    )

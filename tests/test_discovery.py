from datetime import date
from decimal import Decimal

from finsre.discovery.facts import ContextFact, FactSource
from finsre.discovery.probes import ProbeKind, ProbePlanner
from finsre.discovery.sku import GcpSkuClassifier, SkuClassification, SkuDomain
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.models import Anomaly, CostSeries


def test_gcp_sku_classifier_identifies_network_egress_from_meter() -> None:
    classification = GcpSkuClassifier().classify(
        "Compute Engine",
        "Inter-region Egress from europe-west2 to us-central1",
    )

    assert classification.domain == SkuDomain.NETWORK_EGRESS
    assert classification.confidence == 0.85
    assert "egress" in classification.reasons


def test_gcp_sku_classifier_routes_gcp_service_families() -> None:
    examples = [
        ("BigQuery", SkuDomain.DATA_WAREHOUSE),
        ("Google Kubernetes Engine", SkuDomain.KUBERNETES),
        ("Cloud SQL", SkuDomain.DATABASE),
        ("Artifact Registry", SkuDomain.BUILD_ARTIFACTS),
        ("Cloud Storage", SkuDomain.STORAGE),
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
        assert GcpSkuClassifier().classify(service, "Standard usage").domain == domain


def test_gcp_sku_classifier_uses_catalog_category_fields() -> None:
    classification = GcpSkuClassifier().classify(
        "Compute Engine",
        "Standard usage",
        resource_family="Network",
        resource_group="Egress",
        usage_type="OnDemand",
    )

    assert classification.domain == SkuDomain.NETWORK_EGRESS
    assert "egress" in classification.reasons


def test_gcp_sku_classifier_keeps_generic_sku_words_under_service_family() -> None:
    classifier = GcpSkuClassifier()

    assert classifier.classify("Cloud SQL", "Query processing").domain == SkuDomain.DATABASE
    assert classifier.classify("Cloud Logging", "Logs storage").domain == SkuDomain.LOGGING
    assert classifier.classify("Artifact Registry", "Storage").domain == SkuDomain.BUILD_ARTIFACTS


def test_probe_planner_starts_with_billing_context_for_network_egress() -> None:
    classification = GcpSkuClassifier().classify("Compute Engine", "Inter-region Egress")

    probes = ProbePlanner().plan(classification)

    assert [probe.kind for probe in probes] == [
        ProbeKind.BILLING,
        ProbeKind.NETWORK,
        ProbeKind.TELEMETRY,
        ProbeKind.CHANGE,
    ]
    assert probes[0].evidence_sources == ("bigquery_billing_export", "cloud_billing_catalog_api")
    assert "vpc_flow_logs" in probes[1].evidence_sources


def test_probe_planner_keeps_billing_context_for_unknown_skus() -> None:
    probes = ProbePlanner().plan(SkuClassification(domain=SkuDomain.UNKNOWN, confidence=0.2))

    assert [probe.kind for probe in probes] == [ProbeKind.BILLING, ProbeKind.ASSET]
    assert probes[1].name == "generic-assets"


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


def test_workflow_plan_for_sku_supports_catalog_inputs() -> None:
    plan = SkuDiscoveryWorkflow().plan_for_sku(
        service="Compute Engine",
        sku_description="Standard usage",
        project_id="prod-api",
        resource_family="Network",
        resource_group="Egress",
    )

    assert plan.classification.domain == SkuDomain.NETWORK_EGRESS
    assert plan.probes[0].kind == ProbeKind.BILLING
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

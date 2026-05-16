from decimal import Decimal

from finsre.discovery.facts import ContextFact, FactSource
from finsre.discovery.probes import ProbeKind, ProbePlanner
from finsre.discovery.questions import QuestionPlanner
from finsre.discovery.sku import BillingSkuSignal, SkuClassifier, SkuDomain
from finsre.discovery.workflow import SkuDiscoveryWorkflow


def test_sku_classifier_identifies_network_egress() -> None:
    signal = BillingSkuSignal(
        service="Compute Engine",
        sku_id="egress-1",
        sku_description="Inter-region Egress from europe-west2 to us-central1",
        cost=Decimal("42.50"),
        project_id="prod-api",
    )

    classification = SkuClassifier().classify(signal)

    assert classification.domain == SkuDomain.NETWORK_EGRESS
    assert classification.confidence == 0.75
    assert "egress" in classification.reasons


def test_probe_planner_maps_network_egress_to_network_telemetry_and_change() -> None:
    signal = BillingSkuSignal(
        service="Compute Engine",
        sku_id="egress-1",
        sku_description="Inter-region Egress",
        cost=Decimal("42.50"),
    )
    classification = SkuClassifier().classify(signal)

    probes = ProbePlanner().plan(classification)

    assert [probe.kind for probe in probes] == [ProbeKind.NETWORK, ProbeKind.TELEMETRY, ProbeKind.CHANGE]


def test_question_planner_asks_for_network_intent_when_missing() -> None:
    signal = BillingSkuSignal(
        service="Compute Engine",
        sku_id="egress-1",
        sku_description="Inter-region Egress",
        cost=Decimal("42.50"),
        project_id="prod-api",
    )

    plan = SkuDiscoveryWorkflow().plan(signal)

    assert plan.questions[0].id == "prod-api:traffic-intent"
    assert "HA, migration, or customer traffic" in plan.questions[0].text


def test_question_planner_skips_network_intent_when_fact_exists() -> None:
    signal = BillingSkuSignal(
        service="Compute Engine",
        sku_id="egress-1",
        sku_description="Inter-region Egress",
        cost=Decimal("42.50"),
        project_id="prod-api",
    )
    fact = ContextFact(
        entity_id="prod-api",
        fact_type="traffic_intent",
        value="required for migration",
        source=FactSource.USER,
        confidence=0.95,
    )

    plan = SkuDiscoveryWorkflow().plan(signal, facts=(fact,))

    assert plan.questions == ()

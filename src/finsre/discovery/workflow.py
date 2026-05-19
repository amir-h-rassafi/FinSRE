from dataclasses import dataclass

from finsre.discovery.facts import ContextFact
from finsre.discovery.probes import DiscoveryProbe, ProbePlanner
from finsre.discovery.questions import Question, QuestionPlanner
from finsre.discovery.sku import SkuClassification, SkuClassifier
from finsre.models import Anomaly


@dataclass(frozen=True)
class DiscoveryPlan:
    classification: SkuClassification
    probes: tuple[DiscoveryProbe, ...]
    questions: tuple[Question, ...]


class SkuDiscoveryWorkflow:
    def __init__(
        self,
        classifier: SkuClassifier | None = None,
        probe_planner: ProbePlanner | None = None,
        question_planner: QuestionPlanner | None = None,
    ) -> None:
        self._classifier = classifier or SkuClassifier()
        self._probe_planner = probe_planner or ProbePlanner()
        self._question_planner = question_planner or QuestionPlanner()

    def plan_for_anomaly(self, anomaly: Anomaly, facts: tuple[ContextFact, ...] = ()) -> DiscoveryPlan:
        series = anomaly.series
        return self._build(
            service=series.service,
            sku_description=series.sku_description or series.sku,
            project_id=series.project_id,
            facts=facts,
        )

    def plan_for_sku(
        self,
        service: str,
        sku_description: str,
        project_id: str | None = None,
        facts: tuple[ContextFact, ...] = (),
    ) -> DiscoveryPlan:
        return self._build(service=service, sku_description=sku_description, project_id=project_id, facts=facts)

    def _build(
        self,
        service: str,
        sku_description: str,
        project_id: str | None,
        facts: tuple[ContextFact, ...],
    ) -> DiscoveryPlan:
        classification = self._classifier.classify(service, sku_description)
        probes = self._probe_planner.plan(classification)
        questions = self._question_planner.plan(classification, probes, facts, project_id=project_id)
        return DiscoveryPlan(classification=classification, probes=probes, questions=questions)

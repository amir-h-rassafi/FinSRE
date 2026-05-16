from dataclasses import dataclass

from finsre.discovery.facts import ContextFact
from finsre.discovery.probes import DiscoveryProbe, ProbePlanner
from finsre.discovery.questions import Question, QuestionPlanner
from finsre.discovery.sku import BillingSkuSignal, SkuClassification, SkuClassifier


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

    def plan(self, signal: BillingSkuSignal, facts: tuple[ContextFact, ...] = ()) -> DiscoveryPlan:
        classification = self._classifier.classify(signal)
        probes = self._probe_planner.plan(classification)
        questions = self._question_planner.plan(classification, probes, facts)
        return DiscoveryPlan(classification=classification, probes=probes, questions=questions)

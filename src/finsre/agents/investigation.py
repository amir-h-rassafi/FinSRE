import json
from dataclasses import dataclass
from typing import Any

from finsre.agents.base import AgentCapability, AgentRequest, AgentResult
from finsre.discovery.facts import ContextFact
from finsre.discovery.workflow import DiscoveryPlan, SkuDiscoveryWorkflow
from finsre.errors import ConfigurationError
from finsre.llm.base import LLMClient, LLMMessage
from finsre.models import Anomaly


@dataclass(frozen=True)
class InvestigationContext:
    anomaly: Anomaly
    discovery_plan: DiscoveryPlan
    facts: tuple[ContextFact, ...] = ()


@dataclass(frozen=True)
class InvestigationDraft:
    context: InvestigationContext
    llm_required: bool
    approval_reason: str


class InvestigationAgent:
    name = "investigation-agent"
    capabilities = (AgentCapability.INVESTIGATION,)

    def __init__(self, llm_client: LLMClient | None = None, workflow: SkuDiscoveryWorkflow | None = None) -> None:
        self._llm_client = llm_client
        self._workflow = workflow or SkuDiscoveryWorkflow()

    def build_context(self, anomaly: Anomaly, facts: tuple[ContextFact, ...] = ()) -> InvestigationContext:
        return InvestigationContext(
            anomaly=anomaly,
            discovery_plan=self._workflow.plan_for_anomaly(anomaly, facts),
            facts=facts,
        )

    def draft(self, context: InvestigationContext) -> InvestigationDraft:
        return InvestigationDraft(
            context=context,
            llm_required=True,
            approval_reason="LLM approval is required before sending bounded anomaly context to a provider.",
        )

    def investigate(self, context: InvestigationContext) -> AgentResult:
        if self._llm_client is None:
            raise ConfigurationError("LLM client is required to run investigation agent.")
        payload = investigation_payload(context)
        response = self._llm_client.complete(
            [
                LLMMessage(role="system", content=_SYSTEM_PROMPT),
                LLMMessage(role="user", content=json.dumps(payload, sort_keys=True)),
            ]
        )
        return AgentResult(
            capability=AgentCapability.INVESTIGATION,
            summary=response.content,
            evidence=({"source": "investigation_context", "context": payload},),
            confidence=None,
        )

    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            capability=request.capability,
            summary="Use investigate(context) for the current MVP investigation path.",
            confidence=0.1,
        )


_SYSTEM_PROMPT = (
    "You are a cloud cost investigation agent. Use only the provided context. "
    "Return concise hypotheses, missing evidence, and safe next steps."
)


def investigation_payload(context: InvestigationContext) -> dict[str, Any]:
    plan = context.discovery_plan
    anomaly = context.anomaly
    series = anomaly.series
    return {
        "anomaly": {
            "service": series.service,
            "sku": series.sku,
            "sku_description": series.sku_description,
            "project_id": series.project_id,
            "currency": series.currency,
            "inflection_date": anomaly.inflection_date.isoformat(),
            "baseline_cost": str(anomaly.baseline_cost),
            "observed_cost": str(anomaly.observed_cost),
            "magnitude_pct": str(anomaly.magnitude_pct),
            "points": [[day.isoformat(), str(cost)] for day, cost in series.points],
        },
        "classification": {
            "domain": plan.classification.domain.value,
            "confidence": plan.classification.confidence,
            "reasons": list(plan.classification.reasons),
        },
        "planned_probes": [
            {"kind": probe.kind.value, "name": probe.name, "reason": probe.reason, "required": probe.required}
            for probe in plan.probes
        ],
        "questions": [
            {
                "id": question.id,
                "entity_id": question.entity_id,
                "text": question.text,
                "reason": question.reason,
                "blocks_recommendation": question.blocks_recommendation,
            }
            for question in plan.questions
        ],
        "known_facts": [
            {"entity_id": fact.entity_id, "fact_type": fact.fact_type, "value": fact.value} for fact in context.facts
        ],
    }

import json
from dataclasses import dataclass
from typing import Any

from finsre.agents.base import AgentCapability, AgentRequest, AgentResult
from finsre.discovery.sku import BillingSkuSignal
from finsre.discovery.workflow import DiscoveryPlan, SkuDiscoveryWorkflow
from finsre.errors import ConfigurationError
from finsre.llm.base import LLMClient, LLMMessage


@dataclass(frozen=True)
class InvestigationDraft:
    discovery_plan: DiscoveryPlan
    llm_required: bool
    approval_reason: str


class InvestigationAgent:
    name = "investigation-agent"
    capabilities = (AgentCapability.INVESTIGATION,)

    def __init__(self, llm_client: LLMClient | None = None, workflow: SkuDiscoveryWorkflow | None = None) -> None:
        self._llm_client = llm_client
        self._workflow = workflow or SkuDiscoveryWorkflow()

    def draft_from_sku(self, signal: BillingSkuSignal) -> InvestigationDraft:
        return InvestigationDraft(
            discovery_plan=self._workflow.plan(signal),
            llm_required=True,
            approval_reason="LLM approval is required before sending bounded billing/discovery context to a provider.",
        )

    def run_from_sku(self, signal: BillingSkuSignal) -> AgentResult:
        if self._llm_client is None:
            raise ConfigurationError("LLM client is required to run investigation agent.")

        draft = self.draft_from_sku(signal)
        context = _discovery_plan_context(draft.discovery_plan)
        response = self._llm_client.complete(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are a cloud cost investigation agent. Use only the provided context. "
                        "Return concise hypotheses, missing evidence, and safe next steps."
                    ),
                ),
                LLMMessage(role="user", content=json.dumps(context, sort_keys=True)),
            ]
        )
        return AgentResult(
            capability=AgentCapability.INVESTIGATION,
            summary=response.content,
            evidence=({"source": "sku_discovery_plan", "context": context},),
            confidence=None,
        )

    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            capability=request.capability,
            summary="Use run_from_sku for the current MVP investigation path.",
            confidence=0.1,
        )


def _discovery_plan_context(plan: DiscoveryPlan) -> dict[str, Any]:
    return {
        "classification": {
            "domain": plan.classification.domain.value,
            "confidence": plan.classification.confidence,
            "reasons": list(plan.classification.reasons),
            "signal": {
                "service": plan.classification.signal.service,
                "sku_id": plan.classification.signal.sku_id,
                "sku_description": plan.classification.signal.sku_description,
                "cost": str(plan.classification.signal.cost),
                "currency": plan.classification.signal.currency,
                "project_id": plan.classification.signal.project_id,
            },
        },
        "planned_probes": [
            {
                "kind": probe.kind.value,
                "name": probe.name,
                "reason": probe.reason,
                "required": probe.required,
            }
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
    }

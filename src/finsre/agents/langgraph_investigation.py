from typing import Any, TypedDict

from finsre.agents.base import AgentCapability, AgentResult
from finsre.agents.investigation import _discovery_plan_context
from finsre.discovery.sku import BillingSkuSignal
from finsre.discovery.workflow import SkuDiscoveryWorkflow
from finsre.errors import OptionalDependencyError
from finsre.llm.base import LLMClient, LLMMessage


class InvestigationState(TypedDict, total=False):
    signal: BillingSkuSignal
    context: dict[str, Any]
    summary: str


class LangGraphInvestigationAgent:
    """LangGraph-backed investigation workflow.

    LangGraph is optional for the base CLI. Running this agent requires the
    `llm` extra and explicit human approval in the CLI.
    """

    name = "langgraph-investigation-agent"
    capabilities = (AgentCapability.INVESTIGATION,)

    def __init__(self, llm_client: LLMClient, workflow: SkuDiscoveryWorkflow | None = None) -> None:
        self._llm_client = llm_client
        self._workflow = workflow or SkuDiscoveryWorkflow()
        self._graph = self._build_graph()

    def run_from_sku(self, signal: BillingSkuSignal) -> AgentResult:
        state = self._graph.invoke({"signal": signal})
        return AgentResult(
            capability=AgentCapability.INVESTIGATION,
            summary=state["summary"],
            evidence=({"source": "langgraph_investigation_context", "context": state["context"]},),
            confidence=None,
        )

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise OptionalDependencyError("Install the LLM extra first: pip install '.[llm]'") from exc

        graph = StateGraph(InvestigationState)
        graph.add_node("plan_context", self._plan_context)
        graph.add_node("investigate", self._investigate)
        graph.set_entry_point("plan_context")
        graph.add_edge("plan_context", "investigate")
        graph.add_edge("investigate", END)
        return graph.compile()

    def _plan_context(self, state: InvestigationState) -> InvestigationState:
        plan = self._workflow.plan(state["signal"])
        return {"context": _discovery_plan_context(plan)}

    def _investigate(self, state: InvestigationState) -> InvestigationState:
        response = self._llm_client.complete(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are a cloud cost investigation agent. Use only the provided context. "
                        "Return concise hypotheses, missing evidence, and safe next steps."
                    ),
                ),
                LLMMessage(role="user", content=str(state["context"])),
            ]
        )
        return {"summary": response.content}

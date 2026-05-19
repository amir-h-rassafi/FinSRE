import json
import warnings
from typing import Any, TypedDict

from finsre.agents.base import AgentCapability, AgentResult
from finsre.agents.investigation import InvestigationContext, investigation_payload
from finsre.errors import OptionalDependencyError
from finsre.llm.base import LLMClient, LLMMessage

_SYSTEM_PROMPT = (
    "You are a cloud cost investigation agent. Use only the provided context. "
    "Return concise hypotheses, missing evidence, and safe next steps."
)


class InvestigationState(TypedDict, total=False):
    context: InvestigationContext
    payload: dict[str, Any]
    summary: str


class LangGraphInvestigationAgent:
    """LangGraph-backed investigation workflow.

    LangGraph is optional for the base CLI. Running this agent requires the
    `llm` extra and explicit human approval in the CLI.
    """

    name = "langgraph-investigation-agent"
    capabilities = (AgentCapability.INVESTIGATION,)

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client
        self._graph = self._build_graph()

    def investigate(self, context: InvestigationContext) -> AgentResult:
        state = self._graph.invoke({"context": context})
        return AgentResult(
            capability=AgentCapability.INVESTIGATION,
            summary=state["summary"],
            evidence=({"source": "langgraph_investigation_context", "context": state["payload"]},),
            confidence=None,
        )

    def _build_graph(self):
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"The default value of `allowed_objects` will change.*",
                    category=Warning,
                )
                from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise OptionalDependencyError("Install the LLM extra first: pip install '.[llm]'") from exc

        graph = StateGraph(InvestigationState)
        graph.add_node("prepare", self._prepare)
        graph.add_node("investigate", self._investigate)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", "investigate")
        graph.add_edge("investigate", END)
        return graph.compile()

    def _prepare(self, state: InvestigationState) -> InvestigationState:
        return {"payload": investigation_payload(state["context"])}

    def _investigate(self, state: InvestigationState) -> InvestigationState:
        response = self._llm_client.complete(
            [
                LLMMessage(role="system", content=_SYSTEM_PROMPT),
                LLMMessage(role="user", content=json.dumps(state["payload"], sort_keys=True)),
            ]
        )
        return {"summary": response.content}

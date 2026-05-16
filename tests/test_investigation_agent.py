import sys
import types
from unittest.mock import patch
from decimal import Decimal

from finsre.agents.langgraph_investigation import LangGraphInvestigationAgent
from finsre.discovery.sku import BillingSkuSignal
from finsre.errors import OptionalDependencyError
from finsre.llm.base import LLMResponse


class FakeLLM:
    def __init__(self) -> None:
        self.messages = []

    def complete(self, messages):
        self.messages = messages
        return LLMResponse(content="Investigate network egress and missing traffic intent.", model="fake")


def test_langgraph_investigation_agent_runs_with_fake_langgraph(monkeypatch) -> None:
    install_fake_langgraph(monkeypatch)
    llm = FakeLLM()
    agent = LangGraphInvestigationAgent(llm_client=llm)
    signal = BillingSkuSignal(
        service="Compute Engine",
        sku_id="egress-1",
        sku_description="Inter-region Egress",
        cost=Decimal("42.50"),
        project_id="prod-api",
    )

    result = agent.run_from_sku(signal)

    assert result.summary == "Investigate network egress and missing traffic intent."
    assert result.evidence[0]["context"]["classification"]["domain"] == "network_egress"
    assert "provided context" in llm.messages[0].content


def test_langgraph_investigation_agent_raises_repo_error_without_langgraph(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "langgraph.graph", raising=False)
    monkeypatch.delitem(sys.modules, "langgraph", raising=False)

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "langgraph.graph":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=blocked_import):
        try:
            LangGraphInvestigationAgent(llm_client=FakeLLM())
        except OptionalDependencyError as exc:
            assert "Install the LLM extra" in str(exc)
        else:
            raise AssertionError("expected OptionalDependencyError")


def install_fake_langgraph(monkeypatch) -> None:
    graph_module = types.ModuleType("langgraph.graph")

    class FakeCompiledGraph:
        def __init__(self, graph):
            self.graph = graph

        def invoke(self, state):
            current = self.graph.entry
            while current != "__end__":
                state.update(self.graph.nodes[current](state))
                current = self.graph.edges[current]
            return state

    class FakeStateGraph:
        def __init__(self, _state_type):
            self.nodes = {}
            self.edges = {}
            self.entry = None

        def add_node(self, name, func):
            self.nodes[name] = func

        def set_entry_point(self, name):
            self.entry = name

        def add_edge(self, start, end):
            self.edges[start] = end

        def compile(self):
            return FakeCompiledGraph(self)

    graph_module.END = "__end__"
    graph_module.StateGraph = FakeStateGraph
    langgraph_module = types.ModuleType("langgraph")
    monkeypatch.setitem(sys.modules, "langgraph", langgraph_module)
    monkeypatch.setitem(sys.modules, "langgraph.graph", graph_module)

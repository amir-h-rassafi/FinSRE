import sys
import types

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.unit)


@pytest.fixture
def fake_langgraph(monkeypatch) -> None:
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
    monkeypatch.setitem(sys.modules, "langgraph", types.ModuleType("langgraph"))
    monkeypatch.setitem(sys.modules, "langgraph.graph", graph_module)

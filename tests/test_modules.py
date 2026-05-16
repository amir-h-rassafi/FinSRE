from finsre.agents.base import AgentCapability, AgentRequest, AgentResult
from finsre.agents.router import AgentRouter
from finsre.config import Settings
from finsre.core.catalog import build_component_catalog
from finsre.core.events import EventType, new_event
from finsre.core.in_memory_bus import InMemoryEventBus
from finsre.memory.base import MemoryRecord
from finsre.memory.in_memory import InMemoryStore
from finsre.tracker.base import Investigation, Recommendation
from finsre.tracker.in_memory import InMemoryTracker


class FakeAgent:
    name = "fake-cost-agent"
    capabilities = (AgentCapability.COST_ANALYSIS,)

    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(capability=request.capability, summary=f"handled: {request.goal}")


def test_agent_router_routes_by_capability() -> None:
    router = AgentRouter([FakeAgent()])

    result = router.route(AgentRequest(capability=AgentCapability.COST_ANALYSIS, goal="explain cost"))

    assert result.summary == "handled: explain cost"
    assert router.capabilities() == (AgentCapability.COST_ANALYSIS,)


def test_memory_store_searches_within_namespace() -> None:
    store = InMemoryStore()
    store.put(MemoryRecord(key="1", namespace="investigation", text="bigquery sku increase"))
    store.put(MemoryRecord(key="2", namespace="other", text="bigquery sku increase"))

    results = store.search("investigation", "bigquery increase")

    assert [record.key for record in results] == ["1"]


def test_tracker_stores_investigations_and_recommendations() -> None:
    tracker = InMemoryTracker()
    tracker.add_investigation(Investigation(id="inv-1", title="Cost spike"))
    tracker.add_recommendation(Recommendation(id="rec-1", title="Review SKU"))

    assert tracker.list_investigations()[0].id == "inv-1"
    assert tracker.list_recommendations()[0].id == "rec-1"


def test_component_catalog_lists_deployable_boundaries() -> None:
    components = build_component_catalog(Settings())

    names = [component.name for component in components]
    assert names == ["gcp-billing", "agent-router", "memory-store", "tracker"]
    assert "cli_job" in [mode.value for mode in components[0].deploy_modes]


def test_in_memory_event_bus_publishes_and_handles_events() -> None:
    class Handler:
        def handle(self, event):
            return [new_event(EventType.INVESTIGATION_UPDATED, source="test", data={"from": event.id})]

    bus = InMemoryEventBus()
    bus.subscribe(EventType.INVESTIGATION_REQUESTED.value, Handler())

    bus.publish(new_event(EventType.INVESTIGATION_REQUESTED, source="test", data={"id": "inv-1"}))

    assert [event.type for event in bus.published] == [
        EventType.INVESTIGATION_REQUESTED.value,
        EventType.INVESTIGATION_UPDATED.value,
    ]

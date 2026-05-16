from finsre.agents.router import AgentRouter
from finsre.config import Settings
from finsre.connectors.registry import build_default_registry
from finsre.core.components import ComponentManifest
from finsre.discovery.modules import AssetDiscovery, ChangeDiscovery, NetworkDiscovery, TelemetryDiscovery
from finsre.memory.in_memory import InMemoryStore
from finsre.tracker.in_memory import InMemoryTracker


def build_component_catalog(settings: Settings) -> list[ComponentManifest]:
    registry = build_default_registry(settings)
    components: list[ComponentManifest] = [connector.manifest() for connector in registry.list()]
    components.extend(
        [
            AssetDiscovery().manifest(),
            NetworkDiscovery().manifest(),
            TelemetryDiscovery().manifest(),
            ChangeDiscovery().manifest(),
            AgentRouter().manifest(),
            InMemoryStore().manifest(),
            InMemoryTracker().manifest(),
        ]
    )
    return components

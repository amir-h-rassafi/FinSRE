from typing import Protocol

from finsre.core.components import ComponentManifest
from finsre.core.events import EventEnvelope


class Component(Protocol):
    def manifest(self) -> ComponentManifest:
        """Return the component deployment and event contract."""


class EventPublisher(Protocol):
    def publish(self, event: EventEnvelope) -> None:
        """Publish one event to the configured transport."""


class EventHandler(Protocol):
    def handle(self, event: EventEnvelope) -> list[EventEnvelope]:
        """Handle one event and return follow-up events."""


class EventBus(EventPublisher, Protocol):
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""

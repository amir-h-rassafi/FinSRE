from collections import defaultdict

from finsre.core.events import EventEnvelope
from finsre.core.ports import EventHandler


class InMemoryEventBus:
    """Synchronous event bus for tests and local MVP flows."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self.published: list[EventEnvelope] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)
        for handler in self._handlers.get(event.type, []):
            for follow_up in handler.handle(event):
                self.publish(follow_up)

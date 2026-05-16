from finsre.agents.base import Agent, AgentCapability, AgentRequest, AgentResult
from finsre.core.components import ComponentKind, ComponentManifest, DeployMode
from finsre.core.events import EventType


class AgentRouter:
    """Routes bounded requests to specialist agents."""

    def __init__(self, agents: list[Agent] | None = None) -> None:
        self._agents = agents or []

    def route(self, request: AgentRequest) -> AgentResult:
        for agent in self._agents:
            if request.capability in agent.capabilities:
                return agent.run(request)
        raise LookupError(f"No agent registered for capability: {request.capability}")

    def capabilities(self) -> tuple[AgentCapability, ...]:
        seen: list[AgentCapability] = []
        for agent in self._agents:
            for capability in agent.capabilities:
                if capability not in seen:
                    seen.append(capability)
        return tuple(seen)

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name="agent-router",
            kind=ComponentKind.AGENT,
            version="0.1",
            input_events=(EventType.INVESTIGATION_REQUESTED.value,),
            output_events=(EventType.INVESTIGATION_UPDATED.value, EventType.RECOMMENDATION_CREATED.value),
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB, DeployMode.QUEUE_WORKER),
            description="Routes bounded investigation requests to specialist agents.",
        )

from typing import Protocol

from finsre.core.components import ComponentKind, ComponentManifest, DeployMode
from finsre.discovery.facts import ContextFact
from finsre.discovery.probes import DiscoveryProbe


class DiscoveryModule(Protocol):
    name: str

    def discover(self, probe: DiscoveryProbe) -> tuple[ContextFact, ...]:
        """Run one read-only discovery probe and return context facts."""


class AssetDiscovery:
    name = "asset-discovery"

    def discover(self, probe: DiscoveryProbe) -> tuple[ContextFact, ...]:
        return ()

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name=self.name,
            kind=ComponentKind.DISCOVERY,
            version="0.1",
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB, DeployMode.QUEUE_WORKER),
            description="Discovers cloud assets and ownership hints from read-only inventory APIs.",
        )


class NetworkDiscovery:
    name = "network-discovery"

    def discover(self, probe: DiscoveryProbe) -> tuple[ContextFact, ...]:
        return ()

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name=self.name,
            kind=ComponentKind.DISCOVERY,
            version="0.1",
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB, DeployMode.QUEUE_WORKER),
            description="Discovers VPC, subnet, NAT, load balancer, and traffic topology facts.",
        )


class TelemetryDiscovery:
    name = "telemetry-discovery"

    def discover(self, probe: DiscoveryProbe) -> tuple[ContextFact, ...]:
        return ()

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name=self.name,
            kind=ComponentKind.DISCOVERY,
            version="0.1",
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB, DeployMode.QUEUE_WORKER),
            description="Discovers metrics and usage signals for cross-validating billing signals.",
        )


class ChangeDiscovery:
    name = "change-discovery"

    def discover(self, probe: DiscoveryProbe) -> tuple[ContextFact, ...]:
        return ()

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name=self.name,
            kind=ComponentKind.DISCOVERY,
            version="0.1",
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB, DeployMode.QUEUE_WORKER),
            description="Discovers deployment, audit, and infrastructure change facts.",
        )

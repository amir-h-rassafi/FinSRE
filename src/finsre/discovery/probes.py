from dataclasses import dataclass
from enum import StrEnum

from finsre.discovery.sku import SkuClassification, SkuDomain


class ProbeKind(StrEnum):
    ASSET = "asset"
    NETWORK = "network"
    TELEMETRY = "telemetry"
    CHANGE = "change"
    RECOMMENDER = "recommender"


@dataclass(frozen=True)
class DiscoveryProbe:
    kind: ProbeKind
    name: str
    reason: str
    required: bool = True


class ProbePlanner:
    _domain_probes: dict[SkuDomain, tuple[DiscoveryProbe, ...]] = {
        SkuDomain.NETWORK_EGRESS: (
            DiscoveryProbe(ProbeKind.NETWORK, "vpc-topology", "Identify VPC, subnet, route, NAT, LB, VPN, and region shape."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "network-traffic", "Validate bytes, requests, and source/destination hints."),
            DiscoveryProbe(ProbeKind.CHANGE, "network-config-changes", "Find recent route, NAT, LB, or deployment changes."),
        ),
        SkuDomain.NAT: (
            DiscoveryProbe(ProbeKind.NETWORK, "nat-gateways", "Find NAT gateways and private egress paths."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "nat-traffic", "Validate NAT byte volume where metrics/logs exist."),
        ),
        SkuDomain.LOAD_BALANCER: (
            DiscoveryProbe(ProbeKind.NETWORK, "load-balancers", "Find forwarding rules, backend services, and regions."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "lb-traffic", "Validate request and byte metrics."),
        ),
        SkuDomain.BIGQUERY: (
            DiscoveryProbe(ProbeKind.ASSET, "bigquery-assets", "Find datasets, reservations, and scheduled query surfaces."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "bigquery-jobs", "Validate query bytes, jobs, and reservations if accessible."),
        ),
        SkuDomain.GKE: (
            DiscoveryProbe(ProbeKind.ASSET, "gke-clusters", "Find clusters, node pools, namespaces, and workload hints."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "gke-utilization", "Validate node and workload utilization."),
        ),
        SkuDomain.LOGGING: (
            DiscoveryProbe(ProbeKind.ASSET, "logging-config", "Find log buckets, sinks, exclusions, and retention."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "log-volume", "Find top log producers where available."),
        ),
        SkuDomain.STORAGE: (
            DiscoveryProbe(ProbeKind.ASSET, "storage-assets", "Find buckets, disks, snapshots, regions, and lifecycle settings."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "storage-usage", "Validate size and operation metrics where available."),
        ),
        SkuDomain.COMPUTE: (
            DiscoveryProbe(ProbeKind.ASSET, "compute-assets", "Find instances, disks, machine types, zones, and labels."),
            DiscoveryProbe(ProbeKind.RECOMMENDER, "compute-recommenders", "Check native rightsizing or idle recommendations."),
        ),
        SkuDomain.SQL: (
            DiscoveryProbe(ProbeKind.ASSET, "sql-instances", "Find HA, replicas, backups, regions, and machine shape."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "sql-utilization", "Validate CPU, storage, memory, and connection metrics."),
        ),
    }

    def plan(self, classification: SkuClassification) -> tuple[DiscoveryProbe, ...]:
        return self._domain_probes.get(
            classification.domain,
            (DiscoveryProbe(ProbeKind.ASSET, "generic-assets", "Find resources related to the billed project/service."),),
        )

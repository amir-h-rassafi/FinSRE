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
            DiscoveryProbe(
                ProbeKind.NETWORK,
                "vpc-topology",
                "Identify VPC, subnet, route, NAT, LB, VPN, and region shape.",
            ),
            DiscoveryProbe(
                ProbeKind.TELEMETRY,
                "network-traffic",
                "Validate bytes, requests, and source/destination hints.",
            ),
            DiscoveryProbe(
                ProbeKind.CHANGE,
                "network-config-changes",
                "Find recent route, NAT, LB, or deployment changes.",
            ),
        ),
        SkuDomain.NAT: (
            DiscoveryProbe(ProbeKind.NETWORK, "nat-gateways", "Find NAT gateways and private egress paths."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "nat-traffic", "Validate NAT byte volume where metrics/logs exist."),
        ),
        SkuDomain.LOAD_BALANCER: (
            DiscoveryProbe(
                ProbeKind.NETWORK,
                "load-balancers",
                "Find forwarding rules, backend services, and regions.",
            ),
            DiscoveryProbe(ProbeKind.TELEMETRY, "lb-traffic", "Validate request and byte metrics."),
        ),
        SkuDomain.BIGQUERY: (
            DiscoveryProbe(
                ProbeKind.ASSET,
                "bigquery-assets",
                "Find datasets, reservations, and scheduled query surfaces.",
            ),
            DiscoveryProbe(
                ProbeKind.TELEMETRY,
                "bigquery-jobs",
                "Validate query bytes, jobs, and reservations if accessible.",
            ),
        ),
        SkuDomain.GKE: (
            DiscoveryProbe(
                ProbeKind.ASSET,
                "gke-clusters",
                "Find clusters, node pools, namespaces, and workload hints.",
            ),
            DiscoveryProbe(ProbeKind.TELEMETRY, "gke-utilization", "Validate node and workload utilization."),
        ),
        SkuDomain.LOGGING: (
            DiscoveryProbe(ProbeKind.ASSET, "logging-config", "Find log buckets, sinks, exclusions, and retention."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "log-volume", "Find top log producers where available."),
        ),
        SkuDomain.STORAGE: (
            DiscoveryProbe(
                ProbeKind.ASSET,
                "storage-assets",
                "Find buckets, disks, snapshots, regions, and lifecycle settings.",
            ),
            DiscoveryProbe(
                ProbeKind.TELEMETRY,
                "storage-usage",
                "Validate size and operation metrics where available.",
            ),
        ),
        SkuDomain.COMPUTE: (
            DiscoveryProbe(
                ProbeKind.ASSET,
                "compute-assets",
                "Find instances, disks, machine types, zones, and labels.",
            ),
            DiscoveryProbe(
                ProbeKind.RECOMMENDER,
                "compute-recommenders",
                "Check native rightsizing or idle recommendations.",
            ),
        ),
        SkuDomain.SQL: (
            DiscoveryProbe(ProbeKind.ASSET, "sql-instances", "Find HA, replicas, backups, regions, and machine shape."),
            DiscoveryProbe(
                ProbeKind.TELEMETRY,
                "sql-utilization",
                "Validate CPU, storage, memory, and connection metrics.",
            ),
        ),
        SkuDomain.SERVERLESS: (
            DiscoveryProbe(ProbeKind.ASSET, "serverless-services", "Find services, revisions, jobs, and regions."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "serverless-traffic", "Validate requests, CPU, memory, and egress."),
        ),
        SkuDomain.MESSAGING: (
            DiscoveryProbe(ProbeKind.ASSET, "messaging-assets", "Find topics, subscriptions, and regions."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "messaging-volume", "Validate message and byte volume."),
        ),
        SkuDomain.DATA_PROCESSING: (
            DiscoveryProbe(ProbeKind.ASSET, "data-processing-assets", "Find jobs, pipelines, and workers."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "data-processing-usage", "Validate worker and data volume."),
        ),
        SkuDomain.AI: (
            DiscoveryProbe(ProbeKind.ASSET, "ai-assets", "Find models, endpoints, and API usage surfaces."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "ai-usage", "Validate request, token, or prediction volume."),
        ),
        SkuDomain.SECURITY: (
            DiscoveryProbe(ProbeKind.ASSET, "security-assets", "Find scanners, secrets, keys, and certificates."),
            DiscoveryProbe(ProbeKind.CHANGE, "security-config-changes", "Find recent policy or key changes."),
        ),
        SkuDomain.DEVELOPER_TOOLS: (
            DiscoveryProbe(ProbeKind.ASSET, "developer-tool-assets", "Find builds, repositories, and artifacts."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "developer-tool-usage", "Validate build or artifact volume."),
        ),
        SkuDomain.API_PLATFORM: (
            DiscoveryProbe(ProbeKind.ASSET, "api-platform-assets", "Find API keys, projects, and enabled APIs."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "api-platform-usage", "Validate request volume and referrers."),
        ),
        SkuDomain.CACHE: (
            DiscoveryProbe(ProbeKind.ASSET, "cache-assets", "Find cache instances, tiers, memory, and regions."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "cache-utilization", "Validate memory, CPU, and connection metrics."),
        ),
        SkuDomain.DNS: (
            DiscoveryProbe(ProbeKind.ASSET, "dns-assets", "Find zones, policies, and forwarding rules."),
            DiscoveryProbe(ProbeKind.TELEMETRY, "dns-query-volume", "Validate query volume and top zones."),
        ),
    }

    def plan(self, classification: SkuClassification) -> tuple[DiscoveryProbe, ...]:
        return self._domain_probes.get(
            classification.domain,
            (
                DiscoveryProbe(
                    ProbeKind.ASSET,
                    "generic-assets",
                    "Find resources related to the billed project/service.",
                ),
            ),
        )

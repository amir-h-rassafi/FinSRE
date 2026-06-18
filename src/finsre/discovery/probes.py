from dataclasses import dataclass
from enum import StrEnum

from finsre.discovery.sku import SkuClassification, SkuDomain


class ProbeKind(StrEnum):
    BILLING = "billing"
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
    evidence_sources: tuple[str, ...] = ()


BILLING_CONTEXT_PROBE = DiscoveryProbe(
    ProbeKind.BILLING,
    "billing-sku-context",
    "Resolve service id, SKU id, SKU category, labels, and affected cost series.",
    evidence_sources=("bigquery_billing_export", "cloud_billing_catalog_api"),
)

GENERIC_ASSET_PROBE = DiscoveryProbe(
    ProbeKind.ASSET,
    "generic-assets",
    "Find resources related to the billed project/service.",
    evidence_sources=("cloud_asset_inventory",),
)


def _probe(kind: ProbeKind, name: str, reason: str, *sources: str, required: bool = True) -> DiscoveryProbe:
    return DiscoveryProbe(kind, name, reason, required=required, evidence_sources=tuple(sources))


class ProbePlanner:
    _domain_probes: dict[SkuDomain, tuple[DiscoveryProbe, ...]] = {
        SkuDomain.NETWORK_EGRESS: (
            _probe(
                ProbeKind.NETWORK,
                "network-paths",
                "Identify VPC, subnet, route, NAT, LB, VPN, peering, and region shape.",
                "cloud_asset_inventory",
                "vpc_flow_logs",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "network-traffic",
                "Validate bytes, requests, and source/destination hints.",
                "cloud_monitoring",
                "vpc_flow_logs",
            ),
            _probe(
                ProbeKind.CHANGE,
                "network-config-changes",
                "Find recent route, NAT, LB, firewall, or deployment changes.",
                "cloud_audit_logs",
                "asset_history",
            ),
        ),
        SkuDomain.NAT: (
            _probe(
                ProbeKind.NETWORK,
                "nat-gateways",
                "Find NAT gateways and private egress paths.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "nat-traffic",
                "Validate NAT byte volume where metrics/logs exist.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.LOAD_BALANCER: (
            _probe(
                ProbeKind.NETWORK,
                "load-balancers",
                "Find forwarding rules, backend services, certificates, and regions.",
                "cloud_asset_inventory",
            ),
            _probe(ProbeKind.TELEMETRY, "lb-traffic", "Validate request and byte metrics.", "cloud_monitoring"),
        ),
        SkuDomain.DATA_WAREHOUSE: (
            _probe(
                ProbeKind.ASSET,
                "warehouse-assets",
                "Find datasets, reservations, scheduled queries, and external table surfaces.",
                "cloud_asset_inventory",
                "bigquery_metadata",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "warehouse-query-usage",
                "Validate query bytes, jobs, slots, reservations, and storage growth.",
                "bigquery_information_schema",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.KUBERNETES: (
            _probe(
                ProbeKind.ASSET,
                "kubernetes-clusters",
                "Find clusters, node pools, namespaces, and workload hints.",
                "cloud_asset_inventory",
                "gke_api",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "kubernetes-utilization",
                "Validate node and workload utilization.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.LOGGING: (
            _probe(
                ProbeKind.ASSET, "logging-config", "Find log buckets, sinks, exclusions, and retention.", "logging_api"
            ),
            _probe(ProbeKind.TELEMETRY, "log-volume", "Find top log producers where available.", "logging_metrics"),
        ),
        SkuDomain.STORAGE: (
            _probe(
                ProbeKind.ASSET,
                "storage-assets",
                "Find buckets, disks, snapshots, regions, classes, and lifecycle settings.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "storage-usage",
                "Validate size, operations, and transfer metrics.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.COMPUTE: (
            _probe(
                ProbeKind.ASSET,
                "compute-assets",
                "Find instances, disks, machine types, zones, reservations, and labels.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "compute-utilization",
                "Validate CPU, memory, disk, and uptime metrics.",
                "cloud_monitoring",
            ),
            _probe(
                ProbeKind.RECOMMENDER,
                "compute-recommenders",
                "Check native rightsizing, idle, committed-use, or reservation recommendations.",
                "recommender_api",
                required=False,
            ),
        ),
        SkuDomain.DATABASE: (
            _probe(
                ProbeKind.ASSET,
                "database-instances",
                "Find database HA, replicas, backups, regions, storage, and machine shape.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "database-utilization",
                "Validate CPU, storage, memory, and connection metrics.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.SERVERLESS: (
            _probe(
                ProbeKind.ASSET,
                "serverless-services",
                "Find services, revisions, jobs, functions, and regions.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "serverless-traffic",
                "Validate requests, CPU, memory, and egress.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.MESSAGING: (
            _probe(
                ProbeKind.ASSET,
                "messaging-assets",
                "Find topics, subscriptions, queues, and regions.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "messaging-volume",
                "Validate message, byte, and backlog volume.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.DATA_PROCESSING: (
            _probe(
                ProbeKind.ASSET,
                "data-processing-assets",
                "Find jobs, pipelines, clusters, and workers.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "data-processing-usage",
                "Validate worker, shuffle, and data volume.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.AI: (
            _probe(
                ProbeKind.ASSET,
                "ai-assets",
                "Find models, endpoints, datasets, accelerators, and API surfaces.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "ai-usage",
                "Validate request, token, prediction, accelerator, or endpoint volume.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.SECURITY: (
            _probe(
                ProbeKind.ASSET,
                "security-assets",
                "Find scanners, secrets, keys, certificates, and posture surfaces.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.CHANGE,
                "security-config-changes",
                "Find recent policy, key, certificate, or scanner changes.",
                "cloud_audit_logs",
            ),
        ),
        SkuDomain.BUILD_ARTIFACTS: (
            _probe(
                ProbeKind.ASSET,
                "build-artifact-assets",
                "Find builds, registries, repositories, images, and artifacts.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "build-artifact-usage",
                "Validate build minutes, artifact storage, or transfer volume.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.API_PLATFORM: (
            _probe(
                ProbeKind.ASSET,
                "api-platform-assets",
                "Find API keys, projects, enabled APIs, and quota surfaces.",
                "service_usage_api",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "api-platform-usage",
                "Validate request volume, methods, and referrers.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.CACHE: (
            _probe(
                ProbeKind.ASSET,
                "cache-assets",
                "Find cache instances, tiers, memory, replicas, and regions.",
                "cloud_asset_inventory",
            ),
            _probe(
                ProbeKind.TELEMETRY,
                "cache-utilization",
                "Validate memory, CPU, evictions, and connection metrics.",
                "cloud_monitoring",
            ),
        ),
        SkuDomain.DNS: (
            _probe(
                ProbeKind.ASSET,
                "dns-assets",
                "Find zones, policies, forwarding rules, and records.",
                "cloud_asset_inventory",
            ),
            _probe(ProbeKind.TELEMETRY, "dns-query-volume", "Validate query volume and top zones.", "cloud_monitoring"),
        ),
    }

    def plan(self, classification: SkuClassification) -> tuple[DiscoveryProbe, ...]:
        domain_probes = self._domain_probes.get(classification.domain, (GENERIC_ASSET_PROBE,))
        return (BILLING_CONTEXT_PROBE, *domain_probes)

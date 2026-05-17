from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class SkuDomain(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK_EGRESS = "network_egress"
    NAT = "nat"
    LOAD_BALANCER = "load_balancer"
    LOGGING = "logging"
    MONITORING = "monitoring"
    BIGQUERY = "bigquery"
    GKE = "gke"
    SQL = "sql"
    SERVERLESS = "serverless"
    MESSAGING = "messaging"
    DATA_PROCESSING = "data_processing"
    AI = "ai"
    SECURITY = "security"
    DEVELOPER_TOOLS = "developer_tools"
    API_PLATFORM = "api_platform"
    CACHE = "cache"
    DNS = "dns"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BillingSkuSignal:
    service: str
    sku_id: str
    sku_description: str
    cost: Decimal
    currency: str = "USD"
    project_id: str | None = None
    usage_amount: Decimal | None = None
    usage_unit: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkuClassification:
    signal: BillingSkuSignal
    domain: SkuDomain
    confidence: float
    reasons: tuple[str, ...] = ()


class SkuClassifier:
    """Deterministic SKU description classifier.

    This is intentionally simple. It routes discovery work; it does not make
    optimization decisions.
    """

    _rules: tuple[tuple[SkuDomain, tuple[str, ...]], ...] = (
        (SkuDomain.NETWORK_EGRESS, ("egress", "inter-region", "inter region", "internet data transfer")),
        (SkuDomain.NAT, ("nat gateway", "cloud nat", "nat data processing")),
        (SkuDomain.LOAD_BALANCER, ("load balanc", "forwarding rule", "backend service")),
        (SkuDomain.LOGGING, ("logging", "log ingestion", "logs storage", "log storage")),
        (SkuDomain.MONITORING, ("monitoring", "metric", "time series")),
        (SkuDomain.BIGQUERY, ("bigquery", "analysis", "slots", "query")),
        (SkuDomain.GKE, ("kubernetes", "gke", "cluster management")),
        (SkuDomain.SQL, ("cloud sql", "sql instance", "database")),
        (SkuDomain.STORAGE, ("storage", "snapshot", "persistent disk", "ssd", "hdd")),
        (SkuDomain.COMPUTE, ("compute", "instance", "core", "ram", "cpu")),
    )
    _service_rules: tuple[tuple[SkuDomain, tuple[str, ...]], ...] = (
        (SkuDomain.SERVERLESS, ("cloud run", "cloud functions", "app engine", "cloud scheduler")),
        (SkuDomain.MESSAGING, ("cloud pub/sub", "pub/sub")),
        (SkuDomain.DATA_PROCESSING, ("cloud dataflow", "dataproc", "datastream")),
        (SkuDomain.AI, ("gemini api", "vertex ai")),
        (
            SkuDomain.SECURITY,
            ("security command center", "secret manager", "key management service", "kms", "certificate manager"),
        ),
        (SkuDomain.DEVELOPER_TOOLS, ("cloud build", "artifact registry", "vm manager")),
        (SkuDomain.API_PLATFORM, ("places api", "geocoding api", "address validation api")),
        (SkuDomain.CACHE, ("memorystore", "redis")),
        (SkuDomain.DNS, ("cloud dns",)),
    )

    def classify(self, signal: BillingSkuSignal) -> SkuClassification:
        text = f"{signal.service} {signal.sku_description}".lower()
        for domain, keywords in self._rules:
            matched = tuple(keyword for keyword in keywords if keyword in text)
            if matched:
                return SkuClassification(signal=signal, domain=domain, confidence=0.75, reasons=matched)
        service = signal.service.lower()
        for domain, services in self._service_rules:
            matched = tuple(name for name in services if name in service)
            if matched:
                return SkuClassification(signal=signal, domain=domain, confidence=0.55, reasons=matched)
        return SkuClassification(signal=signal, domain=SkuDomain.UNKNOWN, confidence=0.2)

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SkuDomain(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK_EGRESS = "network_egress"
    NAT = "nat"
    LOAD_BALANCER = "load_balancer"
    LOGGING = "logging"
    MONITORING = "monitoring"
    DATA_WAREHOUSE = "data_warehouse"
    KUBERNETES = "kubernetes"
    DATABASE = "database"
    SERVERLESS = "serverless"
    MESSAGING = "messaging"
    DATA_PROCESSING = "data_processing"
    AI = "ai"
    SECURITY = "security"
    BUILD_ARTIFACTS = "build_artifacts"
    API_PLATFORM = "api_platform"
    CACHE = "cache"
    DNS = "dns"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SkuClassification:
    domain: SkuDomain
    confidence: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkuSignal:
    """Billing text and optional catalog fields used for SKU routing.

    `service`/`sku_description` are present in BigQuery billing export rows.
    The optional fields line up with Billing Export ids and Cloud Billing
    Catalog SKU category fields, so the classifier can later be backed by a
    cached catalog without changing callers.
    """

    service: str
    sku_description: str
    sku_id: str | None = None
    service_id: str | None = None
    resource_family: str | None = None
    resource_group: str | None = None
    usage_type: str | None = None


@dataclass(frozen=True)
class SkuRule:
    domain: SkuDomain
    service_terms: tuple[str, ...] = ()
    sku_terms: tuple[str, ...] = ()
    catalog_terms: tuple[str, ...] = ()


class SkuClassifierProtocol(Protocol):
    def classify(
        self,
        service: str,
        sku_description: str,
        *,
        sku_id: str | None = None,
        service_id: str | None = None,
        resource_family: str | None = None,
        resource_group: str | None = None,
        usage_type: str | None = None,
    ) -> SkuClassification:
        """Classify provider billing text into a provider-neutral discovery domain."""


GCP_METER_RULES: tuple[SkuRule, ...] = (
    SkuRule(
        SkuDomain.NETWORK_EGRESS,
        sku_terms=("egress", "inter-region", "inter region", "internet data transfer", "data transfer out"),
        catalog_terms=("egress", "inter-region", "inter region"),
    ),
    SkuRule(SkuDomain.NAT, sku_terms=("cloud nat", "nat gateway", "nat data processing"), catalog_terms=(" nat ",)),
    SkuRule(
        SkuDomain.LOAD_BALANCER,
        sku_terms=("load balanc", "forwarding rule", "backend service"),
        catalog_terms=("load balanc",),
    ),
)

GCP_SERVICE_RULES: tuple[SkuRule, ...] = (
    SkuRule(SkuDomain.DATA_WAREHOUSE, service_terms=("bigquery",), sku_terms=("query bytes",)),
    SkuRule(SkuDomain.KUBERNETES, service_terms=("kubernetes engine", "gke")),
    SkuRule(SkuDomain.DATABASE, service_terms=("cloud sql", "alloydb", "spanner", "firestore")),
    SkuRule(SkuDomain.SERVERLESS, service_terms=("cloud run", "cloud functions", "app engine", "cloud scheduler")),
    SkuRule(SkuDomain.MESSAGING, service_terms=("cloud pub/sub", "pub/sub", "cloud tasks")),
    SkuRule(SkuDomain.DATA_PROCESSING, service_terms=("cloud dataflow", "dataproc", "datastream", "cloud composer")),
    SkuRule(SkuDomain.AI, service_terms=("gemini api", "vertex ai", "generative ai", "cloud tpu")),
    SkuRule(
        SkuDomain.SECURITY,
        service_terms=(
            "security command center",
            "secret manager",
            "key management service",
            "cloud kms",
            "certificate manager",
        ),
    ),
    SkuRule(SkuDomain.BUILD_ARTIFACTS, service_terms=("cloud build", "artifact registry", "container registry")),
    SkuRule(
        SkuDomain.API_PLATFORM,
        service_terms=("places api", "geocoding api", "address validation api", "maps platform"),
    ),
    SkuRule(SkuDomain.CACHE, service_terms=("memorystore", "redis")),
    SkuRule(SkuDomain.DNS, service_terms=("cloud dns",)),
    SkuRule(SkuDomain.LOGGING, service_terms=("cloud logging",), sku_terms=("log ingestion", "logs storage")),
    SkuRule(SkuDomain.MONITORING, service_terms=("cloud monitoring",), sku_terms=("metric", "time series")),
)

GCP_FALLBACK_RULES: tuple[SkuRule, ...] = (
    SkuRule(
        SkuDomain.STORAGE,
        service_terms=("cloud storage",),
        sku_terms=("persistent disk", "snapshot", " pd ", " ssd", " hdd"),
    ),
    SkuRule(SkuDomain.COMPUTE, service_terms=("compute engine",), sku_terms=("instance", "core", "ram", "cpu", " vm ")),
)


class GcpSkuClassifier:
    """Deterministic GCP billing SKU classifier.

    Rules are intentionally domain-level, not an embedded copy of every public
    Google SKU. Exact SKU ids should come from Billing Export or the Cloud
    Billing Catalog API and can be passed in through `SkuSignal` fields.
    """

    def classify(
        self,
        service: str,
        sku_description: str,
        *,
        sku_id: str | None = None,
        service_id: str | None = None,
        resource_family: str | None = None,
        resource_group: str | None = None,
        usage_type: str | None = None,
    ) -> SkuClassification:
        signal = SkuSignal(
            service=service,
            sku_description=sku_description,
            sku_id=sku_id,
            service_id=service_id,
            resource_family=resource_family,
            resource_group=resource_group,
            usage_type=usage_type,
        )
        return self.classify_signal(signal)

    def classify_signal(self, signal: SkuSignal) -> SkuClassification:
        for rules, confidence in (
            (GCP_METER_RULES, 0.85),
            (GCP_SERVICE_RULES, 0.75),
            (GCP_FALLBACK_RULES, 0.6),
        ):
            classification = _match_rules(signal, rules, confidence)
            if classification:
                return classification
        return SkuClassification(domain=SkuDomain.UNKNOWN, confidence=0.2)


class SkuClassifier(GcpSkuClassifier):
    """Backward-compatible default classifier for the current GCP-first MVP."""


def _match_rules(signal: SkuSignal, rules: tuple[SkuRule, ...], confidence: float) -> SkuClassification | None:
    service_text = _text(signal.service, signal.service_id)
    sku_text = _text(signal.sku_description, signal.sku_id)
    catalog_text = _text(signal.resource_family, signal.resource_group, signal.usage_type)

    for rule in rules:
        matched = (
            _matches(rule.service_terms, service_text)
            + _matches(rule.sku_terms, sku_text)
            + _matches(rule.catalog_terms, catalog_text)
        )
        if matched:
            return SkuClassification(domain=rule.domain, confidence=confidence, reasons=tuple(matched))
    return None


def _matches(terms: tuple[str, ...], text: str) -> list[str]:
    return [term.strip() for term in terms if term in text]


def _text(*values: str | None) -> str:
    return f" {' '.join(_normalize(value) for value in values if value)} "


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())

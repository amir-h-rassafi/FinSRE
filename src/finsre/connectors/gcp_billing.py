from datetime import date
from typing import Any, Protocol
from urllib.parse import urlencode

from finsre.connectors.base import Connector
from finsre.core.components import ComponentKind, ComponentManifest, DeployMode
from finsre.core.events import EventEnvelope, EventType, new_event
from finsre.core.serialization import compatibility_to_dict
from finsre.errors import OptionalDependencyError
from finsre.models import (
    CloudProvider,
    CompatibilityReport,
    ConnectorContract,
    ConnectorDescriptor,
    TimePeriod,
)


class BillingApiTransport(Protocol):
    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        """Execute a GET request against cloudbilling.googleapis.com."""


class GoogleAuthBillingApiTransport:
    base_url = "https://cloudbilling.googleapis.com"

    def __init__(self) -> None:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:
            raise OptionalDependencyError("Install the GCP extra to call GCP APIs: pip install '.[gcp]'") from exc

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-billing.readonly"])
        self._session = AuthorizedSession(credentials)

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = self._session.get(url, params=params)
        response.raise_for_status()
        return response.json()


class GcpBillingConnector(Connector):
    """GCP Cloud Billing API connector.

    This shard intentionally uses Cloud Billing APIs rather than Billing Export.
    The APIs cover billing account/project discovery and catalog/pricing data.
    Detailed historical usage cost rows are not exposed by the public Cloud
    Billing Account/Catalog APIs, so that future capability will need a separate
    source such as Billing Export or a customer-provided cost feed.
    """

    name = "gcp-billing"
    base_url = "https://cloudbilling.googleapis.com"
    expected_contract = ConnectorContract(
        version="1.0",
        upstream="cloudbilling.googleapis.com/v1",
        schema="finsre.gcp_billing.v1",
        docs_url="https://cloud.google.com/billing/docs/reference/rest",
    )
    contract = ConnectorContract(
        version="1.0",
        upstream="cloudbilling.googleapis.com/v1",
        schema="finsre.gcp_billing.v1",
        docs_url="https://cloud.google.com/billing/docs/reference/rest",
    )

    def __init__(
        self,
        billing_account: str | None = None,
        currency_code: str = "USD",
        transport: BillingApiTransport | None = None,
    ) -> None:
        self.billing_account = self._normalize_billing_account(billing_account)
        self.currency_code = currency_code
        self._transport = transport

    def describe(self) -> ConnectorDescriptor:
        details: dict[str, Any] = {
            "currency_code": self.currency_code,
            "historical_usage_cost_source": "not_available_from_cloud_billing_api",
        }
        if self.billing_account:
            details["billing_account"] = self.billing_account
        return ConnectorDescriptor(
            name=self.name,
            provider=CloudProvider.GCP,
            source_type="cloud_billing_api",
            capabilities=(
                "billing_account_discovery",
                "project_billing_discovery",
                "service_catalog",
                "sku_pricing_by_period",
            ),
            contract=self.contract,
            details=details,
        )

    def check_compatibility(self, live: bool = False) -> CompatibilityReport:
        problems = list(self._contract_problems())
        warnings = ["Historical usage-cost line items are not available from this API family."]

        if live:
            try:
                self.list_billing_accounts()
            except Exception as exc:
                problems.append(f"Live Cloud Billing API probe failed: {exc}")

        return CompatibilityReport(
            connector=self.name,
            ok=not problems,
            contract=self.contract,
            checked_live=live,
            problems=tuple(problems),
            warnings=tuple(warnings),
        )

    def _contract_problems(self) -> tuple[str, ...]:
        problems: list[str] = []
        if self.contract.version != self.expected_contract.version:
            problems.append(
                f"Expected connector contract version {self.expected_contract.version}, got {self.contract.version}."
            )
        if self.contract.upstream != self.expected_contract.upstream:
            problems.append(f"Expected upstream {self.expected_contract.upstream}, got {self.contract.upstream}.")
        if self.contract.schema != self.expected_contract.schema:
            problems.append(f"Expected schema {self.expected_contract.schema}, got {self.contract.schema}.")
        return tuple(problems)

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name=self.name,
            kind=ComponentKind.CONNECTOR,
            version=self.contract.version,
            output_events=(
                EventType.CONNECTOR_COMPATIBILITY_CHECKED.value,
                EventType.BILLING_ACCOUNT_DISCOVERED.value,
                EventType.PROJECT_BILLING_DISCOVERED.value,
                EventType.SKU_PRICING_DISCOVERED.value,
            ),
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB, DeployMode.QUEUE_WORKER),
            dependencies=("cloudbilling.googleapis.com/v1",),
            description="GCP Cloud Billing API connector.",
        )

    def compatibility_event(self, live: bool = False) -> EventEnvelope:
        report = self.check_compatibility(live=live)
        return new_event(
            EventType.CONNECTOR_COMPATIBILITY_CHECKED,
            source=f"connector/{self.name}",
            data=compatibility_to_dict(report),
            subject=self.name,
            dataschema="finsre.compatibility_report.v1",
        )

    def preview_api_calls(self, period: TimePeriod) -> list[str]:
        calls = [
            self._url("/v1/billingAccounts"),
            self._url("/v1/services", {"pageSize": "5000"}),
        ]
        if self.billing_account:
            calls.append(self._url(f"/v1/{self.billing_account}/projects"))
        calls.append(
            self._url(
                "/v1/services/{service_id}/skus",
                {
                    "startTime": period.start_time_rfc3339,
                    "endTime": period.end_time_rfc3339,
                    "currencyCode": self.currency_code,
                    "pageSize": "5000",
                },
            )
        )
        return calls

    def list_billing_accounts(self) -> list[dict[str, Any]]:
        return self._paged_get("/v1/billingAccounts", "billingAccounts")

    def list_projects(self, billing_account: str | None = None) -> list[dict[str, Any]]:
        account = self._normalize_billing_account(billing_account) or self.billing_account
        if not account:
            raise ValueError("A billing account is required to list associated projects.")
        return self._paged_get(f"/v1/{account}/projects", "projectBillingInfo")

    def list_services(self) -> list[dict[str, Any]]:
        return self._paged_get("/v1/services", "services", {"pageSize": "5000"})

    def list_skus_for_service(
        self,
        service_name: str,
        period: TimePeriod,
        currency_code: str | None = None,
    ) -> list[dict[str, Any]]:
        service = self._normalize_service_name(service_name)
        params = {
            "startTime": period.start_time_rfc3339,
            "endTime": period.end_time_rfc3339,
            "currencyCode": currency_code or self.currency_code,
            "pageSize": "5000",
        }
        return self._paged_get(f"/v1/{service}/skus", "skus", params)

    def _paged_get(
        self,
        path: str,
        collection_key: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        transport = self._api_transport()
        page_token: str | None = None
        results: list[dict[str, Any]] = []

        while True:
            page_params = dict(params or {})
            if page_token:
                page_params["pageToken"] = page_token
            payload = transport.get(path, page_params)
            results.extend(payload.get(collection_key, []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                return results

    def _api_transport(self) -> BillingApiTransport:
        if self._transport is None:
            self._transport = GoogleAuthBillingApiTransport()
        return self._transport

    def _url(self, path: str, params: dict[str, str] | None = None) -> str:
        url = f"{self.base_url}{path}"
        if params:
            return f"{url}?{urlencode(params)}"
        return url

    @staticmethod
    def _normalize_billing_account(billing_account: str | None) -> str | None:
        if not billing_account:
            return None
        if billing_account.startswith("billingAccounts/"):
            return billing_account
        return f"billingAccounts/{billing_account}"

    @staticmethod
    def _normalize_service_name(service_name: str) -> str:
        if service_name.startswith("services/"):
            return service_name
        return f"services/{service_name}"


def period_from_dates(start_date: date, end_date: date) -> TimePeriod:
    return TimePeriod(start_date=start_date, end_date=end_date)

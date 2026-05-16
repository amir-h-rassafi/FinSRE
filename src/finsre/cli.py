import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from finsre.config import get_settings
from finsre.connectors.gcp_billing import GcpBillingConnector
from finsre.connectors.registry import build_default_registry
from finsre.models import ConnectorDescriptor, TimePeriod


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = args.func(args)
    except Exception as exc:
        print(f"finsre: {exc}", file=sys.stderr)
        return 1

    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finsre", description="FinSRE CLI agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    connectors = subparsers.add_parser("connectors", help="Inspect configured connectors")
    connectors_sub = connectors.add_subparsers(dest="connectors_command", required=True)
    connectors_list = connectors_sub.add_parser("list", help="List connectors")
    connectors_list.set_defaults(func=_list_connectors)

    gcp = subparsers.add_parser("gcp", help="GCP connector commands")
    gcp_sub = gcp.add_subparsers(dest="gcp_command", required=True)
    billing = gcp_sub.add_parser("billing", help="GCP Cloud Billing API commands")
    billing_sub = billing.add_subparsers(dest="billing_command", required=True)

    api_preview = billing_sub.add_parser("api-preview", help="Preview Cloud Billing API calls for a period")
    _add_period_args(api_preview)
    api_preview.set_defaults(func=_gcp_billing_api_preview)

    accounts = billing_sub.add_parser("accounts", help="List visible billing accounts")
    accounts.set_defaults(func=_gcp_billing_accounts)

    projects = billing_sub.add_parser("projects", help="List projects associated with a billing account")
    projects.add_argument("--billing-account", help="Billing account id or billingAccounts/* resource name")
    projects.set_defaults(func=_gcp_billing_projects)

    services = billing_sub.add_parser("services", help="List public GCP billing services")
    services.set_defaults(func=_gcp_billing_services)

    skus = billing_sub.add_parser("skus", help="List SKUs and pricing for a service over a period")
    skus.add_argument("--service-name", required=True, help="Service id or services/* resource name")
    skus.add_argument("--currency-code", help="ISO 4217 currency code")
    _add_period_args(skus)
    skus.set_defaults(func=_gcp_billing_skus)

    return parser


def _add_period_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Exclusive end date, YYYY-MM-DD")


def _list_connectors(_: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    return [_connector_dict(connector.describe()) for connector in registry.list()]


def _gcp_billing_api_preview(args: argparse.Namespace) -> dict[str, Any]:
    connector = _gcp_billing_connector()
    period = _period_from_args(args)
    return {
        "connector": connector.name,
        "period": {
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "calls": connector.preview_api_calls(period),
    }


def _gcp_billing_accounts(_: argparse.Namespace) -> dict[str, Any]:
    connector = _gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_billing_accounts()}


def _gcp_billing_projects(args: argparse.Namespace) -> dict[str, Any]:
    connector = _gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_projects(args.billing_account)}


def _gcp_billing_services(_: argparse.Namespace) -> dict[str, Any]:
    connector = _gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_services()}


def _gcp_billing_skus(args: argparse.Namespace) -> dict[str, Any]:
    connector = _gcp_billing_connector()
    period = _period_from_args(args)
    return {
        "connector": connector.name,
        "data": connector.list_skus_for_service(args.service_name, period, args.currency_code),
    }


def _gcp_billing_connector() -> GcpBillingConnector:
    return GcpBillingConnector(
        billing_account=get_settings().gcp_billing_account,
        currency_code=get_settings().gcp_billing_currency,
    )


def _period_from_args(args: argparse.Namespace) -> TimePeriod:
    return TimePeriod(
        start_date=date.fromisoformat(args.start_date),
        end_date=date.fromisoformat(args.end_date),
    )


def _connector_dict(descriptor: ConnectorDescriptor) -> dict[str, Any]:
    return {
        "name": descriptor.name,
        "provider": descriptor.provider.value,
        "source_type": descriptor.source_type,
        "status": descriptor.status.value,
        "capabilities": list(descriptor.capabilities),
        "details": descriptor.details,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    raise SystemExit(main())

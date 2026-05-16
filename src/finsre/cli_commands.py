import argparse
from typing import Any

from finsre.config import get_settings
from finsre.connectors.gcp_billing import GcpBillingConnector
from finsre.connectors.registry import build_default_registry
from finsre.core.catalog import build_component_catalog
from finsre.core.serialization import compatibility_to_dict, component_to_dict, connector_to_dict, event_to_dict
from finsre.core.time import parse_period


def list_connectors(_: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    return [connector_to_dict(connector.describe()) for connector in registry.list()]


def list_components(_: argparse.Namespace) -> list[dict[str, Any]]:
    return [component_to_dict(component) for component in build_component_catalog(get_settings())]


def check_connectors(args: argparse.Namespace) -> list[dict[str, Any]]:
    registry = build_default_registry(get_settings())
    connectors = [registry.get(args.name)] if args.name else registry.list()
    return [compatibility_to_dict(connector.check_compatibility(live=args.live)) for connector in connectors]


def gcp_billing_api_preview(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    period = parse_period(args.start_date, args.end_date)
    return {
        "connector": connector.name,
        "period": {
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "calls": connector.preview_api_calls(period),
    }


def gcp_billing_compatibility_event(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return event_to_dict(connector.compatibility_event(live=args.live))


def gcp_billing_accounts(_: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_billing_accounts()}


def gcp_billing_projects(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_projects(args.billing_account)}


def gcp_billing_services(_: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    return {"connector": connector.name, "data": connector.list_services()}


def gcp_billing_skus(args: argparse.Namespace) -> dict[str, Any]:
    connector = gcp_billing_connector()
    period = parse_period(args.start_date, args.end_date)
    return {
        "connector": connector.name,
        "data": connector.list_skus_for_service(args.service_name, period, args.currency_code),
    }


def gcp_billing_connector() -> GcpBillingConnector:
    settings = get_settings()
    return GcpBillingConnector(
        billing_account=settings.gcp_billing_account,
        currency_code=settings.gcp_billing_currency,
    )

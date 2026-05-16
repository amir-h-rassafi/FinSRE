import argparse
import json
import sys

from finsre import cli_commands
from finsre.core.serialization import json_default


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = args.func(args)
    except Exception as exc:
        print(f"finsre: {exc}", file=sys.stderr)
        return 1

    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True, default=json_default))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finsre", description="FinSRE CLI agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    components = subparsers.add_parser("components", help="Inspect deployable module boundaries")
    components_sub = components.add_subparsers(dest="components_command", required=True)
    components_list = components_sub.add_parser("list", help="List component manifests")
    components_list.set_defaults(func=cli_commands.list_components)

    connectors = subparsers.add_parser("connectors", help="Inspect configured connectors")
    connectors_sub = connectors.add_subparsers(dest="connectors_command", required=True)
    connectors_list = connectors_sub.add_parser("list", help="List connectors")
    connectors_list.set_defaults(func=cli_commands.list_connectors)
    connectors_check = connectors_sub.add_parser("check", help="Check connector compatibility")
    connectors_check.add_argument("--name", help="Connector name to check. Defaults to all connectors.")
    connectors_check.add_argument("--live", action="store_true", help="Run lightweight live provider API probes.")
    connectors_check.set_defaults(func=cli_commands.check_connectors)

    gcp = subparsers.add_parser("gcp", help="GCP connector commands")
    gcp_sub = gcp.add_subparsers(dest="gcp_command", required=True)
    billing = gcp_sub.add_parser("billing", help="GCP Cloud Billing API commands")
    billing_sub = billing.add_subparsers(dest="billing_command", required=True)

    api_preview = billing_sub.add_parser("api-preview", help="Preview Cloud Billing API calls for a period")
    _add_period_args(api_preview)
    api_preview.set_defaults(func=cli_commands.gcp_billing_api_preview)

    compatibility_event = billing_sub.add_parser("compatibility-event", help="Emit connector compatibility event")
    compatibility_event.add_argument("--live", action="store_true", help="Run lightweight live provider API probe.")
    compatibility_event.set_defaults(func=cli_commands.gcp_billing_compatibility_event)

    accounts = billing_sub.add_parser("accounts", help="List visible billing accounts")
    accounts.set_defaults(func=cli_commands.gcp_billing_accounts)

    projects = billing_sub.add_parser("projects", help="List projects associated with a billing account")
    projects.add_argument("--billing-account", help="Billing account id or billingAccounts/* resource name")
    projects.set_defaults(func=cli_commands.gcp_billing_projects)

    services = billing_sub.add_parser("services", help="List public GCP billing services")
    services.set_defaults(func=cli_commands.gcp_billing_services)

    skus = billing_sub.add_parser("skus", help="List SKUs and pricing for a service over a period")
    skus.add_argument("--service-name", required=True, help="Service id or services/* resource name")
    skus.add_argument("--currency-code", help="ISO 4217 currency code")
    _add_period_args(skus)
    skus.set_defaults(func=cli_commands.gcp_billing_skus)

    return parser


def _add_period_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Exclusive end date, YYYY-MM-DD")


if __name__ == "__main__":
    raise SystemExit(main())

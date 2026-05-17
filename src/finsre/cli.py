import argparse
import json
import sys

from finsre import cli_commands
from finsre.core.serialization import json_default
from finsre.errors import FinSREError


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = args.func(args)
    except FinSREError as exc:
        print(f"finsre: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"finsre: unexpected error: {exc}", file=sys.stderr)
        return 2

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

    discovery = subparsers.add_parser("discovery", help="Plan SKU-driven discovery")
    discovery_sub = discovery.add_subparsers(dest="discovery_command", required=True)
    classify_sku = discovery_sub.add_parser("classify-sku", help="Classify a billed SKU into a discovery domain")
    _add_sku_signal_args(classify_sku)
    classify_sku.set_defaults(func=cli_commands.classify_sku)
    plan_sku = discovery_sub.add_parser("plan-sku", help="Plan discovery probes for a billed SKU")
    _add_sku_signal_args(plan_sku)
    plan_sku.set_defaults(func=cli_commands.plan_sku_discovery)

    investigate = subparsers.add_parser("investigate", help="Investigation agent commands")
    investigate_sub = investigate.add_subparsers(dest="investigate_command", required=True)
    investigate_draft = investigate_sub.add_parser("draft-from-sku", help="Draft investigation context from one SKU")
    _add_sku_signal_args(investigate_draft)
    investigate_draft.set_defaults(func=cli_commands.investigate_sku_draft)
    investigate_csv = investigate_sub.add_parser(
        "draft-from-csv",
        help="Draft investigations from local CSV billing rows",
    )
    _add_csv_feed_args(investigate_csv)
    investigate_csv.set_defaults(func=cli_commands.investigate_csv_draft)
    investigate_csv_run = investigate_sub.add_parser(
        "run-from-csv",
        help="Run LLM investigations from local CSV billing rows",
    )
    _add_csv_feed_args(investigate_csv_run)
    investigate_csv_run.add_argument(
        "--approve-llm",
        action="store_true",
        help="Explicitly approve sending context to LLM.",
    )
    investigate_csv_run.set_defaults(func=cli_commands.investigate_csv_run)
    investigate_run = investigate_sub.add_parser("run-from-sku", help="Run LLM investigation for one SKU")
    _add_sku_signal_args(investigate_run)
    investigate_run.add_argument(
        "--approve-llm",
        action="store_true",
        help="Explicitly approve sending context to LLM.",
    )
    investigate_run.set_defaults(func=cli_commands.investigate_sku_run)

    connectors = subparsers.add_parser("connectors", help="Inspect configured connectors")
    connectors_sub = connectors.add_subparsers(dest="connectors_command", required=True)
    connectors_list = connectors_sub.add_parser("list", help="List connectors")
    connectors_list.set_defaults(func=cli_commands.list_connectors)
    connectors_check = connectors_sub.add_parser("check", help="Check connector compatibility")
    connectors_check.add_argument("--name", help="Connector name to check. Defaults to all connectors.")
    connectors_check.add_argument("--path", help="Local CSV path when checking local-csv-billing.")
    connectors_check.add_argument("--live", action="store_true", help="Run lightweight live provider API probes.")
    connectors_check.set_defaults(func=cli_commands.check_connectors)
    connectors_csv = connectors_sub.add_parser("preview-csv", help="Preview normalized cost rows from a local CSV")
    _add_csv_feed_args(connectors_csv)
    connectors_csv.set_defaults(func=cli_commands.preview_csv_costs)

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


def _add_sku_signal_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--service", required=True, help="Billing service name, for example Compute Engine")
    parser.add_argument("--sku-id", required=True, help="Provider SKU id")
    parser.add_argument("--sku-description", required=True, help="Provider SKU description")
    parser.add_argument("--cost", required=True, help="Observed cost for this SKU")
    parser.add_argument("--currency", default="USD", help="Cost currency")
    parser.add_argument("--project-id", help="Project/account id associated with the SKU")


def _add_csv_feed_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--path", required=True, help="Path to a local CSV billing feed")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to process")
    parser.add_argument("--currency", default="USD", help="Default currency when the CSV has no currency column")
    parser.add_argument("--service-column", help="CSV column containing service name")
    parser.add_argument("--sku-column", help="CSV column containing SKU or resource id")
    parser.add_argument("--sku-description-column", help="CSV column containing SKU description")
    parser.add_argument("--cost-column", help="CSV column containing cost")
    parser.add_argument("--currency-column", help="CSV column containing currency")
    parser.add_argument("--project-column", help="CSV column containing project or account id")
    parser.add_argument("--region-column", help="CSV column containing region or zone")
    parser.add_argument("--usage-amount-column", help="CSV column containing usage amount")
    parser.add_argument("--usage-unit-column", help="CSV column containing usage unit")
    parser.add_argument("--usage-start-date-column", help="CSV column containing usage start date")


if __name__ == "__main__":
    raise SystemExit(main())

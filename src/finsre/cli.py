import argparse
import json
import logging
import sys
from collections.abc import Callable
from typing import Any

from finsre import cli_commands
from finsre.core.serialization import json_default
from finsre.errors import FinSREError

CommandHandler = Callable[[argparse.Namespace], Any]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_logger = _stream_logger("finsre.output", sys.stdout)
    error_logger = _stream_logger("finsre.error", sys.stderr)

    try:
        payload = args.func(args)
    except FinSREError as exc:
        error_logger.error("finsre: %s", exc)
        return 1
    except Exception as exc:
        error_logger.error("finsre: unexpected error: %s", exc)
        return 2

    if payload is not None:
        output_logger.info(json.dumps(payload, indent=2, sort_keys=True, default=json_default))
    return 0


def _stream_logger(name: str, stream) -> logging.Logger:
    logger = logging.getLogger(name)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finsre", description="FinSRE CLI agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_components_commands(subparsers)
    _add_discovery_commands(subparsers)
    _add_investigate_commands(subparsers)
    _add_connectors_commands(subparsers)
    _add_gcp_commands(subparsers)

    return parser


def _add_components_commands(subparsers: argparse._SubParsersAction) -> None:
    components = subparsers.add_parser("components", help="Inspect deployable module boundaries")
    components_sub = components.add_subparsers(dest="components_command", required=True)

    _add_command(components_sub, "list", "List component manifests", cli_commands.list_components)


def _add_discovery_commands(subparsers: argparse._SubParsersAction) -> None:
    discovery = subparsers.add_parser("discovery", help="Plan SKU-driven discovery")
    discovery_sub = discovery.add_subparsers(dest="discovery_command", required=True)

    classify_sku = _add_command(
        discovery_sub,
        "classify-sku",
        "Classify a billed SKU into a discovery domain",
        cli_commands.classify_sku,
    )
    _add_sku_args(classify_sku)

    plan_sku = _add_command(
        discovery_sub,
        "plan-sku",
        "Plan discovery probes for a billed SKU",
        cli_commands.plan_sku_discovery,
    )
    _add_sku_args(plan_sku)


def _add_investigate_commands(subparsers: argparse._SubParsersAction) -> None:
    investigate = subparsers.add_parser("investigate", help="Anomaly-first investigation pipeline")
    investigate_sub = investigate.add_subparsers(dest="investigate_command", required=True)

    detect = _add_command(
        investigate_sub,
        "detect",
        "Detect anomalies from a billing feed (no LLM)",
        cli_commands.investigate_detect,
    )
    _add_csv_feed_args(detect)

    run = _add_command(
        investigate_sub,
        "run",
        "Run LLM investigations for each detected anomaly",
        cli_commands.investigate_run,
    )
    _add_csv_feed_args(run)
    run.add_argument("--approve-llm", action="store_true", help="Explicitly approve sending context to LLM.")


def _add_connectors_commands(subparsers: argparse._SubParsersAction) -> None:
    connectors = subparsers.add_parser("connectors", help="Inspect configured connectors")
    connectors_sub = connectors.add_subparsers(dest="connectors_command", required=True)

    _add_command(connectors_sub, "list", "List connectors", cli_commands.list_connectors)

    connectors_check = _add_command(
        connectors_sub,
        "check",
        "Check connector compatibility",
        cli_commands.check_connectors,
    )
    connectors_check.add_argument("--name", help="Connector name to check. Defaults to all connectors.")
    connectors_check.add_argument("--path", help="Local CSV path when checking local-csv-billing.")
    connectors_check.add_argument("--live", action="store_true", help="Run lightweight live provider API probes.")

    connectors_csv = _add_command(
        connectors_sub,
        "preview-csv",
        "Preview normalized cost rows from a local CSV",
        cli_commands.preview_csv_costs,
    )
    _add_csv_feed_args(connectors_csv)
    connectors_csv.add_argument("--limit", type=int, default=20, help="Maximum rows to print")


def _add_gcp_commands(subparsers: argparse._SubParsersAction) -> None:
    gcp = subparsers.add_parser("gcp", help="GCP connector commands")
    gcp_sub = gcp.add_subparsers(dest="gcp_command", required=True)
    billing = gcp_sub.add_parser("billing", help="GCP Cloud Billing API commands")
    billing_sub = billing.add_subparsers(dest="billing_command", required=True)

    api_preview = _add_command(
        billing_sub,
        "api-preview",
        "Preview Cloud Billing API calls for a period",
        cli_commands.gcp_billing_api_preview,
    )
    _add_period_args(api_preview)

    compatibility_event = _add_command(
        billing_sub,
        "compatibility-event",
        "Emit connector compatibility event",
        cli_commands.gcp_billing_compatibility_event,
    )
    compatibility_event.add_argument("--live", action="store_true", help="Run lightweight live provider API probe.")

    _add_command(billing_sub, "accounts", "List visible billing accounts", cli_commands.gcp_billing_accounts)

    projects = _add_command(
        billing_sub,
        "projects",
        "List projects associated with a billing account",
        cli_commands.gcp_billing_projects,
    )
    projects.add_argument("--billing-account", help="Billing account id or billingAccounts/* resource name")

    _add_command(billing_sub, "services", "List public GCP billing services", cli_commands.gcp_billing_services)

    skus = _add_command(
        billing_sub,
        "skus",
        "List SKUs and pricing for a service over a period",
        cli_commands.gcp_billing_skus,
    )
    skus.add_argument("--service-name", required=True, help="Service id or services/* resource name")
    skus.add_argument("--currency-code", help="ISO 4217 currency code")
    _add_period_args(skus)


def _add_command(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    handler: CommandHandler,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.set_defaults(func=handler)
    return parser


def _add_period_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Exclusive end date, YYYY-MM-DD")


def _add_sku_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--service", required=True, help="Billing service name, for example Compute Engine")
    parser.add_argument("--sku-description", required=True, help="Provider SKU description")
    parser.add_argument("--project-id", help="Project/account id associated with the SKU")
    parser.add_argument("--sku-id", help="Provider SKU id from billing export or catalog")
    parser.add_argument("--service-id", help="Provider service id from billing export or catalog")
    parser.add_argument("--resource-family", help="Catalog SKU resource family, for example Network")
    parser.add_argument("--resource-group", help="Catalog SKU resource group, for example Egress")
    parser.add_argument("--usage-type", help="Catalog SKU usage type, for example OnDemand")


def _add_csv_feed_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--path", required=True, help="Path to a local CSV billing feed")
    parser.add_argument("--currency", default="USD", help="Default currency when the CSV has no currency column")
    parser.add_argument("--threshold-pct", type=float, default=25.0, help="Percent change vs baseline to flag")
    parser.add_argument("--baseline-days", type=int, default=7, help="Days in the trailing baseline window")
    parser.add_argument("--service-column", help="CSV column containing service name")
    parser.add_argument("--sku-column", help="CSV column containing SKU or resource id")
    parser.add_argument("--sku-description-column", help="CSV column containing SKU description")
    parser.add_argument("--cost-column", help="CSV column containing cost")
    parser.add_argument("--currency-column", help="CSV column containing currency")
    parser.add_argument("--project-column", help="CSV column containing project or account id")
    parser.add_argument("--region-column", help="CSV column containing region or zone")
    parser.add_argument("--usage-start-date-column", help="CSV column containing usage start date")


if __name__ == "__main__":
    raise SystemExit(main())

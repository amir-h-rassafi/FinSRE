import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finsre.connectors.base import Connector
from finsre.core.components import ComponentKind, ComponentManifest, DeployMode
from finsre.core.events import EventEnvelope, EventType, new_event
from finsre.core.serialization import compatibility_to_dict
from finsre.errors import ConfigurationError
from finsre.models import CloudProvider, CompatibilityReport, ConnectorContract, ConnectorDescriptor, CostLineItem


class CsvBillingFormatError(ConfigurationError):
    """Raised when a local CSV cannot be mapped to FinSRE cost line items."""


@dataclass(frozen=True)
class CsvBillingColumnMap:
    service: str | None = None
    sku: str | None = None
    sku_description: str | None = None
    cost: str | None = None
    currency: str | None = None
    project_id: str | None = None
    account_id: str | None = None
    region: str | None = None
    usage_start_date: str | None = None


class LocalCsvBillingConnector(Connector):
    name = "local-csv-billing"
    contract = ConnectorContract(
        version="1.0",
        upstream="local-csv",
        schema="finsre.cost_line_item.v1",
    )

    _aliases: dict[str, tuple[str, ...]] = {
        "service": ("service", "service name", "service description"),
        "sku": ("sku", "sku id", "sku_id", "resource id", "resource_id"),
        "sku_description": ("sku description", "sku_description", "description", "usage type"),
        "cost": ("cost", "unrounded cost ($)", "rounded cost ($)", "cost ($)", "amount"),
        "currency": ("currency", "currency code"),
        "project_id": ("project", "project id", "project_id", "resource id", "resource_id"),
        "account_id": ("account", "account id", "billing account", "billing_account"),
        "region": ("region", "region/zone", "location", "zone"),
        "usage_start_date": ("usage start date", "start date", "usage_start_time", "date"),
    }

    def __init__(
        self,
        path: str | Path | None = None,
        columns: CsvBillingColumnMap | None = None,
        currency: str = "USD",
    ) -> None:
        self.path = Path(path).expanduser() if path else None
        self.columns = columns or CsvBillingColumnMap()
        self.currency = currency

    def describe(self) -> ConnectorDescriptor:
        details: dict[str, Any] = {
            "currency": self.currency,
            "format": "csv",
            "path_required_for_collection": True,
        }
        if self.path:
            details["path"] = str(self.path)
        return ConnectorDescriptor(
            name=self.name,
            provider=CloudProvider.GCP,
            source_type="local_csv",
            capabilities=("cost_line_item_feed",),
            contract=self.contract,
            details=details,
        )

    def check_compatibility(self, live: bool = False) -> CompatibilityReport:
        problems = list(self._contract_problems())
        warnings: list[str] = []
        if live:
            warnings.append("Live checks do not apply to local CSV files.")
        if self.path:
            try:
                rows = self._read_rows()
                self._resolve_columns(tuple(rows[0].keys()) if rows else ())
            except Exception as exc:
                problems.append(str(exc))
        else:
            warnings.append("No CSV path configured; pass --path to validate a file.")
        return CompatibilityReport(
            connector=self.name,
            ok=not problems,
            contract=self.contract,
            checked_live=live,
            problems=tuple(problems),
            warnings=tuple(warnings),
        )

    def manifest(self) -> ComponentManifest:
        return ComponentManifest(
            name=self.name,
            kind=ComponentKind.CONNECTOR,
            version=self.contract.version,
            output_events=(EventType.SKU_USAGE_OBSERVED.value,),
            deploy_modes=(DeployMode.IN_PROCESS, DeployMode.CLI_JOB),
            dependencies=("local filesystem",),
            description="Local CSV billing feed connector.",
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

    def collect_costs(self) -> Iterable[CostLineItem]:
        rows = self._read_rows()
        resolved = self._resolve_columns(tuple(rows[0].keys()) if rows else ())
        date_columns = _date_columns(tuple(rows[0].keys()) if rows else ())
        for row in rows:
            if not _row_value(row, resolved["service"]) or not _row_value(row, resolved["sku"]):
                continue
            if "cost" in resolved:
                usage_date = _parse_date(_row_value(row, resolved.get("usage_start_date"))) or date.today()
                cost = _optional_decimal(_row_value(row, resolved["cost"]))
                if cost is None:
                    continue
                yield self._line_item(row, resolved, cost, usage_date)
                continue
            for column in date_columns:
                cost = _optional_decimal(_row_value(row, column))
                if cost is None or cost == 0:
                    continue
                yield self._line_item(row, resolved, cost, _parse_date(column) or date.today())

    def _line_item(
        self,
        row: dict[str, str],
        resolved: dict[str, str],
        cost: Decimal,
        usage_date: date,
    ) -> CostLineItem:
        service = _required_row_value(row, resolved["service"])
        sku = _required_row_value(row, resolved["sku"])
        return CostLineItem(
            provider=CloudProvider.GCP,
            account_id=_row_value(row, resolved.get("account_id")) or "local-csv",
            service=service,
            sku=sku,
            sku_description=_row_value(row, resolved.get("sku_description")),
            usage_start_date=usage_date,
            currency=_row_value(row, resolved.get("currency")) or self.currency,
            cost=cost,
            project_id=_row_value(row, resolved.get("project_id")),
            region=_row_value(row, resolved.get("region")),
            labels={"csv_source": str(self.path)},
            source=self.name,
        )

    def _read_rows(self) -> list[dict[str, str]]:
        if self.path is None:
            raise CsvBillingFormatError("CSV path is required.")
        if not self.path.exists():
            raise CsvBillingFormatError(f"CSV file does not exist: {self.path}")
        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise CsvBillingFormatError("CSV file is empty.")
        return rows

    def _resolve_columns(self, headers: tuple[str, ...]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for field in ("service", "sku"):
            column = _resolve_column(headers, getattr(self.columns, field), self._aliases[field])
            if not column:
                raise CsvBillingFormatError(f"CSV is missing required `{field}` column.")
            resolved[field] = column
        cost_column = _resolve_column(headers, self.columns.cost, self._aliases["cost"])
        if cost_column:
            resolved["cost"] = cost_column
        elif not _date_columns(headers):
            raise CsvBillingFormatError("CSV is missing required `cost` column or YYYY-MM-DD cost columns.")
        for field in set(self._aliases) - set(resolved):
            column = _resolve_column(headers, getattr(self.columns, field), self._aliases[field])
            if column:
                resolved[field] = column
        return resolved

    def _contract_problems(self) -> tuple[str, ...]:
        problems: list[str] = []
        if self.contract.upstream != "local-csv":
            problems.append(f"Unsupported upstream for local CSV connector: {self.contract.upstream}.")
        if self.contract.schema != "finsre.cost_line_item.v1":
            problems.append(f"Unsupported schema for local CSV connector: {self.contract.schema}.")
        return tuple(problems)


def _resolve_column(headers: tuple[str, ...], configured: str | None, aliases: tuple[str, ...]) -> str | None:
    exact = {header: header for header in headers}
    normalized = {_normalize(header): header for header in headers}
    if configured:
        return exact.get(configured) or normalized.get(_normalize(configured))
    for alias in aliases:
        column = normalized.get(_normalize(alias))
        if column:
            return column
    return None


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _date_columns(headers: tuple[str, ...]) -> tuple[str, ...]:
    columns: list[str] = []
    for header in headers:
        try:
            parsed = _parse_date(header)
        except CsvBillingFormatError:
            parsed = None
        if parsed:
            columns.append(header)
    return tuple(columns)


def _row_value(row: dict[str, str], column: str | None) -> str | None:
    if not column:
        return None
    value = row.get(column, "").strip()
    return value or None


def _required_row_value(row: dict[str, str], column: str) -> str:
    value = _row_value(row, column)
    if value is None:
        raise CsvBillingFormatError(f"CSV row is missing value for `{column}`.")
    return value


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise CsvBillingFormatError(f"Invalid decimal value: {value}") from exc


def _optional_decimal(value: str | None) -> Decimal | None:
    return _decimal(value) if value else None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise CsvBillingFormatError(f"Invalid usage date value: {value}")

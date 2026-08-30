"""Server-compiled BigQuery actual-spend fetch. Planning does not discover warehouses."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.control_plane.models import BigQueryWorkspaceBinding
from app.control_plane.repository import ControlPlaneRepository
from app.data_foundation.context import DataFoundationContext
from app.data_foundation.discovery.query_budget import validate_identifier
from app.data_foundation.enums import ConnectionLifecycle, LocationType
from app.data_foundation.store import DataFoundationStore
from app.integrations.google.adapters import BigQueryClient
from app.investment_planning.actuals import RawActualSpendRow
from app.investment_planning.contracts import ActualSpendQueryReceipt, ActualSpendSourceRef
from app.investment_planning.errors import (
    ActualsChannelMappingRequiredError,
    ActualsDuplicateGrainError,
    ActualsMarketMappingRequiredError,
    ActualsSchemaInvalidError,
    BqAuthorizationFailedError,
    BqLocationMismatchError,
    BqQueryFailedError,
    BqSourceNotFoundError,
    PeriodMappingRequiredError,
    ProductionActualsSourceNotReadyError,
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.identity import (
    require_canonical_channel_id,
    require_canonical_market_id,
)
from app.investment_planning.ids import new_query_receipt_id
from app.service.google_oauth import GoogleConnectionService

QUERY_TEMPLATE_VERSION = "actual_spend_bq_query/v1"
ACTUALS_QUERY_MAX_ROWS = 100_000
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|grant|revoke)\b",
    re.IGNORECASE,
)
_TIMEZONE = re.compile(r"^[A-Za-z0-9_+\-/]+$")
_LOGGER = logging.getLogger("prem3.investment_planning.bigquery_actuals")


@dataclass(frozen=True, slots=True)
class CompiledActualSpendQuery:
    sql: str
    timezone: str
    query_template_version: str
    mapping_fingerprint: str
    date_field: str
    market_field: str
    channel_field: str
    spend_field: str
    currency_field: str


def fiscal_year_date_window(fiscal_year: int, fiscal_start_month: int) -> tuple[date, date]:
    if fiscal_start_month < 1 or fiscal_start_month > 12:
        raise PeriodMappingRequiredError(
            "fiscal_start_month must be an explicit month 1-12.",
            code="PERIOD_MAPPING_REQUIRED",
        )
    start = date(fiscal_year, fiscal_start_month, 1)
    end_month = fiscal_start_month - 1 or 12
    end_year = fiscal_year if fiscal_start_month == 1 else fiscal_year + 1
    if end_month == 12:
        end = date(end_year, 12, 31)
    else:
        end = date(end_year, end_month + 1, 1) - timedelta(days=1)
    return start, end


def _safe_timezone(timezone: str) -> str:
    name = timezone.strip()
    if not name or _TIMEZONE.fullmatch(name) is None:
        raise PeriodMappingRequiredError(
            "Actual-spend timezone is required for fiscal-quarter mapping.",
            code="PERIOD_MAPPING_REQUIRED",
        )
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise PeriodMappingRequiredError(
            f"Unknown actual-spend timezone {timezone!r}.",
            code="PERIOD_MAPPING_REQUIRED",
        ) from exc
    return name


def compile_actual_spend_query(
    *,
    project_id: str,
    dataset_id: str,
    table_id: str,
    date_field: str,
    market_field: str,
    channel_field: str,
    spend_field: str,
    currency_field: str,
    timezone: str,
) -> CompiledActualSpendQuery:
    validate_identifier(project_id.replace("-", "_"), field="project_id")
    dataset = validate_identifier(dataset_id, field="dataset_id")
    table = validate_identifier(table_id, field="table_id")
    date_col = validate_identifier(date_field, field="date_field")
    market_col = validate_identifier(market_field, field="market_field")
    channel_col = validate_identifier(channel_field, field="channel_field")
    spend_col = validate_identifier(spend_field, field="spend_field")
    currency_col = validate_identifier(currency_field, field="currency_field")
    zone = _safe_timezone(timezone)
    sql = (
        f"SELECT DATE(`{date_col}`, @timezone) AS date, "
        f"`{market_col}` AS market_id, "
        f"`{channel_col}` AS channel_id, "
        f"SUM(`{spend_col}`) AS spend, "
        f"`{currency_col}` AS currency "
        f"FROM `{project_id}.{dataset}.{table}` "
        f"WHERE DATE(`{date_col}`, @timezone) BETWEEN @start_date AND @end_date "
        f"GROUP BY date, market_id, channel_id, currency"
    )
    if _FORBIDDEN.search(sql) or "select *" in sql.lower():
        raise ValueError("Compiled SQL failed the mutation/DDL denylist.")
    mapping_fingerprint = metadata_fingerprint(
        {
            "date_field": date_col,
            "market_field": market_col,
            "channel_field": channel_col,
            "spend_field": spend_col,
            "currency_field": currency_col,
            "timezone": zone,
            "template": QUERY_TEMPLATE_VERSION,
        }
    )
    return CompiledActualSpendQuery(
        sql=sql,
        timezone=zone,
        query_template_version=QUERY_TEMPLATE_VERSION,
        mapping_fingerprint=mapping_fingerprint,
        date_field=date_col,
        market_field=market_col,
        channel_field=channel_col,
        spend_field=spend_col,
        currency_field=currency_col,
    )


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        raise ActualsSchemaInvalidError(
            "Actual-spend amounts must be Decimal.",
            code="ACTUALS_SCHEMA_INVALID",
        )
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ActualsSchemaInvalidError(
            "Actual-spend amounts must be Decimal.",
            code="ACTUALS_SCHEMA_INVALID",
        ) from exc
    if not parsed.is_finite():
        raise ActualsSchemaInvalidError(
            "Actual-spend amounts must be finite.",
            code="ACTUALS_SCHEMA_INVALID",
        )
    return parsed


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ActualsSchemaInvalidError(
            "Actual-spend date is invalid.",
            code="ACTUALS_SCHEMA_INVALID",
        ) from exc


class BigQueryActualSpendAdapter:
    """Production ActualSpendRowSource. Compiles a bounded query from DF metadata."""

    def __init__(
        self,
        store: DataFoundationStore,
        *,
        bigquery: BigQueryClient,
        repo: ControlPlaneRepository | None = None,
        connections: GoogleConnectionService | None = None,
        context: DataFoundationContext | None = None,
        access_token: str | None = None,
    ) -> None:
        self._store = store
        self._bigquery = bigquery
        self._repo = repo
        self._connections = connections
        self._context = context
        self._access_token = access_token
        self.last_receipt: ActualSpendQueryReceipt | None = None
        self._compiled: CompiledActualSpendQuery | None = None

    def fetch_rows(
        self,
        source: ActualSpendSourceRef,
        *,
        fiscal_year: int | None = None,
        fiscal_start_month: int = 1,
        known_market_ids: frozenset[str] | set[str] | None = None,
    ) -> tuple[RawActualSpendRow, ...]:
        issues: list[str] = []
        status = "FAILED"
        row_count = 0
        self._compiled = None
        try:
            rows = self._fetch(
                source,
                fiscal_year=fiscal_year,
                fiscal_start_month=fiscal_start_month,
                known_market_ids=known_market_ids or frozenset(),
            )
            row_count = len(rows)
            status = "SUCCESS"
            return rows
        except Exception as exc:
            code = getattr(exc, "code", type(exc).__name__)
            issues.append(str(code))
            raise
        finally:
            self.last_receipt = self._receipt(
                source,
                fiscal_year=fiscal_year,
                compiled=self._compiled,
                row_count=row_count,
                status=status,
                issues=tuple(issues),
            )
            _LOGGER.info(
                "actual_spend_query receipt_id=%s status=%s row_count=%s issues=%s",
                self.last_receipt.query_receipt_id,
                status,
                row_count,
                ",".join(issues) or "none",
            )

    def _fetch(
        self,
        source: ActualSpendSourceRef,
        *,
        fiscal_year: int | None,
        fiscal_start_month: int,
        known_market_ids: frozenset[str] | set[str],
    ) -> tuple[RawActualSpendRow, ...]:
        if fiscal_year is None:
            raise PeriodMappingRequiredError(
                "Production actuals require an explicit fiscal year.",
                code="PERIOD_MAPPING_REQUIRED",
            )
        binding = self._store.get_binding(source.source_ref)
        if (
            binding is None
            or not binding.governance_import_ready
            or binding.location_type is not LocationType.BIGQUERY
        ):
            raise ProductionActualsSourceNotReadyError(
                "Governed actual-spend SourceBinding is not ready for production query.",
                code="PRODUCTION_ACTUALS_SOURCE_NOT_READY",
            )
        resource = binding.resource
        if not resource.project_id or not resource.dataset_id or not resource.table_id:
            raise ProductionActualsSourceNotReadyError(
                "Actual-spend SourceBinding is missing BigQuery resource identity.",
                code="PRODUCTION_ACTUALS_SOURCE_NOT_READY",
            )
        context = self._resolve_context(source)
        token = self._resolve_token(context)
        try:
            context.authorize_project(resource.project_id)
        except PermissionError as exc:
            raise BqAuthorizationFailedError(
                "Actual-spend BigQuery project is outside the bound workspace.",
                code="BQ_AUTHORIZATION_FAILED",
            ) from exc
        if context.source_dataset_ids and resource.dataset_id not in context.source_dataset_ids:
            raise BqAuthorizationFailedError(
                "Actual-spend BigQuery dataset is outside the bound workspace.",
                code="BQ_AUTHORIZATION_FAILED",
            )
        if context.bq_lifecycle is ConnectionLifecycle.NOT_CONNECTED:
            raise BqAuthorizationFailedError(
                "BigQuery connection is not authorized for actual-spend query.",
                code="BQ_AUTHORIZATION_FAILED",
            )
        table = self._bigquery.get_table(
            access_token=token,
            project_id=resource.project_id,
            dataset_id=resource.dataset_id,
            table_id=resource.table_id,
        )
        if table is None:
            raise BqSourceNotFoundError(
                "Authorized actual-spend BigQuery table was not found.",
                code="BQ_SOURCE_NOT_FOUND",
            )
        physical = self._store.get_physical(binding.source_id)
        source_location = (
            None if physical is None else physical.dataset_location
        ) or table.location
        bound_location = context.destination_location
        if not source_location or not bound_location:
            raise BqLocationMismatchError(
                "Actual-spend BigQuery location is unknown and cannot be assumed.",
                code="BQ_LOCATION_MISMATCH",
            )
        if source_location.strip().upper() != bound_location.strip().upper():
            raise BqLocationMismatchError(
                "Actual-spend BigQuery location does not match the workspace binding.",
                code="BQ_LOCATION_MISMATCH",
            )
        contract = binding.contract
        timezone = contract.timezone or source.timezone
        if not timezone:
            raise PeriodMappingRequiredError(
                "Actual-spend timezone is required for fiscal-quarter mapping.",
                code="PERIOD_MAPPING_REQUIRED",
            )
        self._compiled = compile_actual_spend_query(
            project_id=resource.project_id,
            dataset_id=resource.dataset_id,
            table_id=resource.table_id,
            date_field=contract.date_field or "date",
            market_field="market_id",
            channel_field="channel_id",
            spend_field="spend",
            currency_field="currency",
            timezone=timezone,
        )
        compiled = self._compiled
        assert compiled is not None
        start, end = fiscal_year_date_window(fiscal_year, fiscal_start_month)
        try:
            payload = self._bigquery.run_bounded_query(
                access_token=token,
                project_id=resource.project_id,
                sql=compiled.sql,
                parameters={
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "timezone": compiled.timezone,
                },
                location=source_location,
                max_rows=ACTUALS_QUERY_MAX_ROWS,
            )
        except (BqAuthorizationFailedError, BqSourceNotFoundError, BqLocationMismatchError):
            raise
        except Exception as exc:
            raise BqQueryFailedError(
                "Governed actual-spend BigQuery query failed.",
                code="BQ_QUERY_FAILED",
            ) from exc
        grain = (contract.grain or "day").strip().lower()
        if grain in {"daily"}:
            grain = "day"
        seen: set[tuple[date, str, str, str]] = set()
        rows: list[RawActualSpendRow] = []
        for item in payload:
            occurred = _as_date(item.get("date"))
            market_id = str(item.get("market_id") or "").strip()
            channel_id = str(item.get("channel_id") or "").strip()
            currency = str(item.get("currency") or "").strip().upper()
            key = (occurred, market_id, channel_id, currency)
            if key in seen:
                raise ActualsDuplicateGrainError(
                    "Production actuals returned duplicate grain keys.",
                    code="ACTUALS_DUPLICATE_GRAIN",
                )
            seen.add(key)
            try:
                canonical_market = require_canonical_market_id(
                    market_id, known_market_ids=known_market_ids
                )
            except UnresolvedMarketIdentityError as exc:
                raise ActualsMarketMappingRequiredError(
                    "Actual-spend market_id is not a canonical Identity Graph market.",
                    code="ACTUALS_MARKET_MAPPING_REQUIRED",
                ) from exc
            try:
                canonical_channel = require_canonical_channel_id(channel_id)
            except UnresolvedChannelIdentityError as exc:
                raise ActualsChannelMappingRequiredError(
                    "Actual-spend channel_id is not in the Channel Registry.",
                    code="ACTUALS_CHANNEL_MAPPING_REQUIRED",
                ) from exc
            rows.append(
                RawActualSpendRow(
                    occurred_at=occurred,
                    market_id=canonical_market,
                    channel_id=canonical_channel,
                    amount=_as_decimal(item.get("spend")),
                    currency=currency,
                    timezone=compiled.timezone,
                    grain=grain,
                )
            )
        assert compiled is not None
        return tuple(rows)

    def _resolve_context(self, source: ActualSpendSourceRef) -> DataFoundationContext:
        if self._context is not None:
            if self._context.tenant_id != source.tenant_id:
                raise BqAuthorizationFailedError(
                    "Actual-spend query refused a cross-tenant Data Foundation context.",
                    code="BQ_AUTHORIZATION_FAILED",
                )
            return self._context
        if self._repo is None:
            raise BqAuthorizationFailedError(
                "Actual-spend query has no workspace BigQuery binding.",
                code="BQ_AUTHORIZATION_FAILED",
            )
        binding: BigQueryWorkspaceBinding | None = self._repo.get_bigquery_binding(
            tenant_id=source.tenant_id, workspace_id=source.project_id
        )
        if binding is None:
            raise BqAuthorizationFailedError(
                "Workspace BigQuery binding is required for production actuals.",
                code="BQ_AUTHORIZATION_FAILED",
            )
        lifecycle = (
            ConnectionLifecycle.DISCOVERY_READY
            if binding.read_verified
            else ConnectionLifecycle.NOT_CONNECTED
        )
        return DataFoundationContext(
            tenant_id=source.tenant_id,
            workspace_id=source.project_id,
            actor_id=source.tenant_id,
            google_connection_id=binding.connection_id,
            destination_project_id=binding.destination_project_id,
            destination_location=binding.location,
            source_project_ids=binding.source_project_ids,
            source_dataset_ids=binding.source_dataset_ids,
            bq_lifecycle=lifecycle,
        )

    def _resolve_token(self, context: DataFoundationContext) -> str:
        if self._access_token:
            return self._access_token
        if self._connections is None or not context.google_connection_id:
            raise BqAuthorizationFailedError(
                "Actual-spend query is missing a Google access token.",
                code="BQ_AUTHORIZATION_FAILED",
            )
        try:
            connection = self._connections.get_connection(
                connection_id=context.google_connection_id
            )
            return self._connections.user_access_token(connection=connection)
        except BqAuthorizationFailedError:
            raise
        except Exception as exc:
            raise BqAuthorizationFailedError(
                "BigQuery authorization failed for actual-spend query.",
                code="BQ_AUTHORIZATION_FAILED",
            ) from exc

    def _receipt(
        self,
        source: ActualSpendSourceRef,
        *,
        fiscal_year: int | None,
        compiled: CompiledActualSpendQuery | None,
        row_count: int,
        status: str,
        issues: tuple[str, ...],
    ) -> ActualSpendQueryReceipt:
        now = datetime.now(UTC)
        period = "UNSPECIFIED" if fiscal_year is None else f"FY{fiscal_year}"
        mapping_fp = "" if compiled is None else compiled.mapping_fingerprint
        template = QUERY_TEMPLATE_VERSION if compiled is None else compiled.query_template_version
        fingerprint = metadata_fingerprint(
            {
                "actuals_source_id": source.actuals_source_id,
                "source_fingerprint": source.source_fingerprint,
                "period": period,
                "query_template_version": template,
                "mapping_fingerprint": mapping_fp,
                "row_count": row_count,
                "status": status,
                "issues": issues,
            }
        )
        return ActualSpendQueryReceipt(
            query_receipt_id=new_query_receipt_id(),
            tenant_id=source.tenant_id,
            project_id=source.project_id,
            workspace_id=source.workspace_id,
            actuals_source_id=source.actuals_source_id,
            source_fingerprint=source.source_fingerprint,
            period=period,
            query_template_version=template,
            mapping_fingerprint=mapping_fp,
            row_count=row_count,
            as_of_time=source.as_of,
            status=status,
            issues=issues,
            created_at=now,
            fingerprint=fingerprint,
        )

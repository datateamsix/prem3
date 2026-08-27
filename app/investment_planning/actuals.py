"""Governed actual-spend query port. Analytical rows stay transient."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal, Protocol, cast, runtime_checkable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.data_foundation.contracts import SourceAssessment, SourceBinding
from app.data_foundation.enums import LocationType, QualityStatus
from app.data_foundation.store import DataFoundationStore
from app.investment_planning.contracts import ActualSpendAllocation, ActualSpendSourceRef
from app.investment_planning.enums import (
    ActualsFreshnessState,
    ActualSpendAuthority,
    ActualSpendSourceKind,
    ActualSpendSourceStatus,
)
from app.investment_planning.errors import (
    ActualsSchemaInvalidError,
    ActualsSourceNotConfiguredError,
    ActualsSourceUnavailableError,
    CurrencyReviewRequiredError,
    PeriodMappingRequiredError,
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.identity import (
    require_canonical_channel_id,
    require_canonical_market_id,
)
from app.investment_planning.ids import new_actuals_source_id

PERIOD_AGGREGATION_RULE = "fiscal_year_x_quarter/v1"
MONEY_QUANTUM = Decimal("0.01")
PORTFOLIO_ACTUALS_FIELDS = frozenset({"date", "market_id", "channel_id", "spend", "currency"})
P6_03_PRODUCTION_ACTUALS_QUERY_PENDING = "P6_03_PRODUCTION_ACTUALS_QUERY_PENDING"


def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


def resolve_zoneinfo(timezone_name: str | None) -> ZoneInfo:
    if timezone_name is None or not str(timezone_name).strip():
        raise PeriodMappingRequiredError(
            "Actual-spend timezone is required for fiscal-quarter mapping.",
            code="PERIOD_MAPPING_REQUIRED",
        )
    try:
        return ZoneInfo(str(timezone_name).strip())
    except ZoneInfoNotFoundError as exc:
        raise PeriodMappingRequiredError(
            f"Unknown actual-spend timezone {timezone_name!r}.",
            code="PERIOD_MAPPING_REQUIRED",
        ) from exc


def fiscal_year_quarter_for_date(day: date, *, fiscal_start_month: int) -> tuple[int, int]:
    if fiscal_start_month < 1 or fiscal_start_month > 12:
        raise PeriodMappingRequiredError(
            "fiscal_start_month must be an explicit month 1-12.",
            code="PERIOD_MAPPING_REQUIRED",
        )
    if day.month >= fiscal_start_month:
        fiscal_year = day.year
        month_index = day.month - fiscal_start_month
    else:
        fiscal_year = day.year - 1
        month_index = day.month - fiscal_start_month + 12
    quarter = month_index // 3 + 1
    if quarter not in (1, 2, 3, 4):
        raise PeriodMappingRequiredError(
            "Date did not map to a fiscal quarter.",
            code="PERIOD_MAPPING_REQUIRED",
        )
    return fiscal_year, quarter


def require_period_stays_in_quarter(
    start: date, *, days: int, fiscal_start_month: int
) -> tuple[int, int]:
    fiscal_year, quarter = fiscal_year_quarter_for_date(
        start, fiscal_start_month=fiscal_start_month
    )
    end = start + timedelta(days=days - 1)
    end_year, end_quarter = fiscal_year_quarter_for_date(
        end, fiscal_start_month=fiscal_start_month
    )
    if (end_year, end_quarter) != (fiscal_year, quarter):
        raise PeriodMappingRequiredError(
            "Source period spans fiscal-quarter boundaries and cannot be "
            "rolled without double-count.",
            code="PERIOD_MAPPING_REQUIRED",
        )
    return fiscal_year, quarter


@dataclass(frozen=True, slots=True)
class RawActualSpendRow:
    occurred_at: datetime | date
    market_id: str
    channel_id: str
    amount: Decimal
    currency: str
    timezone: str
    grain: str = "day"


@dataclass(frozen=True, slots=True)
class ActualSpendQueryResult:
    source: ActualSpendSourceRef | None
    allocations: tuple[ActualSpendAllocation, ...]
    freshness: ActualsFreshnessState
    error_code: str | None = None


@runtime_checkable
class ActualSpendRowSource(Protocol):
    def fetch_rows(self, source: ActualSpendSourceRef) -> tuple[RawActualSpendRow, ...]: ...


@runtime_checkable
class ActualSpendQuery(Protocol):
    def resolve_source(self, *, tenant_id: str, project_id: str) -> ActualSpendSourceRef | None: ...

    def query_allocations(
        self,
        *,
        source: ActualSpendSourceRef,
        fiscal_year: int | None,
        fiscal_start_month: int,
        known_market_ids: frozenset[str] | set[str],
        expected_currency: str | None = None,
    ) -> tuple[ActualSpendAllocation, ...]: ...


class InMemoryActualSpendRowSource:
    """Test double. Not a customer-governed warehouse."""

    def __init__(self, rows: tuple[RawActualSpendRow, ...] = ()) -> None:
        self._rows = rows

    def fetch_rows(self, source: ActualSpendSourceRef) -> tuple[RawActualSpendRow, ...]:
        del source
        return self._rows


def binding_supports_portfolio_actuals(binding: SourceBinding) -> bool:
    if binding.lifecycle_state == "RETIRED":
        return False
    fields = {str(item) for item in binding.contract.required_fields}
    if not PORTFOLIO_ACTUALS_FIELDS.issubset(fields):
        return False
    if not binding.contract.timezone:
        return False
    return True


def freshness_from_assessment(assessment: SourceAssessment | None) -> ActualsFreshnessState:
    if assessment is None:
        return ActualsFreshnessState.UNKNOWN
    operational = assessment.operational
    if not operational.freshness_known or not operational.expected_cadence:
        return ActualsFreshnessState.UNKNOWN
    if operational.status is QualityStatus.REVIEW:
        return ActualsFreshnessState.REVIEW_REQUIRED
    if operational.status is QualityStatus.BLOCKER:
        return ActualsFreshnessState.STALE
    if operational.status is QualityStatus.PASS:
        return ActualsFreshnessState.FRESH
    return ActualsFreshnessState.UNKNOWN


def _local_date(value: datetime | date, *, timezone_name: str) -> date:
    zone = resolve_zoneinfo(timezone_name)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            localized = value.replace(tzinfo=zone)
        else:
            localized = value.astimezone(zone)
        return localized.date()
    return value


def rollup_raw_actuals(
    rows: tuple[RawActualSpendRow, ...],
    *,
    source: ActualSpendSourceRef,
    fiscal_year: int | None,
    fiscal_start_month: int,
    known_market_ids: frozenset[str] | set[str],
    expected_currency: str | None,
) -> tuple[ActualSpendAllocation, ...]:
    grouped: dict[tuple[int, int, str, str, str], Decimal] = {}
    as_of = source.as_of
    currencies = {str(row.currency).strip().upper() for row in rows}
    if expected_currency is None and len(currencies) > 1:
        raise CurrencyReviewRequiredError(
            "Multiple actual-spend currencies cannot be summed without governed FX conversion.",
            code="CURRENCY_REVIEW_REQUIRED",
        )
    for row in rows:
        if not isinstance(row.amount, Decimal):
            raise ActualsSchemaInvalidError(
                "Actual-spend amounts must be Decimal.",
                code="ACTUALS_SCHEMA_INVALID",
            )
        market_id = require_canonical_market_id(row.market_id, known_market_ids=known_market_ids)
        channel_id = require_canonical_channel_id(row.channel_id)
        currency = str(row.currency).strip().upper()
        if expected_currency is not None and currency != expected_currency.strip().upper():
            raise CurrencyReviewRequiredError(
                "Actual-spend currency does not match the Investment Plan currency.",
                code="CURRENCY_REVIEW_REQUIRED",
            )
        local_day = _local_date(row.occurred_at, timezone_name=row.timezone)
        grain = (row.grain or "day").strip().lower()
        if grain in {"day", "daily"}:
            year, quarter = fiscal_year_quarter_for_date(
                local_day, fiscal_start_month=fiscal_start_month
            )
        elif grain in {"week", "weekly"}:
            year, quarter = require_period_stays_in_quarter(
                local_day, days=7, fiscal_start_month=fiscal_start_month
            )
        elif grain in {"month", "monthly"}:
            year, quarter = fiscal_year_quarter_for_date(
                local_day.replace(day=1), fiscal_start_month=fiscal_start_month
            )
            month_end = (local_day.replace(day=28) + timedelta(days=8)).replace(day=1) - timedelta(
                days=1
            )
            end_year, end_quarter = fiscal_year_quarter_for_date(
                month_end, fiscal_start_month=fiscal_start_month
            )
            if (end_year, end_quarter) != (year, quarter):
                raise PeriodMappingRequiredError(
                    "Monthly actuals span fiscal-quarter boundaries.",
                    code="PERIOD_MAPPING_REQUIRED",
                )
        else:
            raise PeriodMappingRequiredError(
                f"Unsupported actual-spend grain {row.grain!r} without an explicit mapping.",
                code="PERIOD_MAPPING_REQUIRED",
            )
        if fiscal_year is not None and year != fiscal_year:
            continue
        key = (year, quarter, market_id, channel_id, currency)
        grouped[key] = grouped.get(key, Decimal("0")) + row.amount
    allocations: list[ActualSpendAllocation] = []
    for (year, quarter, market_id, channel_id, currency), total in sorted(grouped.items()):
        allocations.append(
            ActualSpendAllocation(
                fiscal_year=year,
                quarter=cast(Literal[1, 2, 3, 4], quarter),
                market_id=market_id,
                channel_id=channel_id,
                amount=round_money(total),
                currency=currency,
                source_ref=source.actuals_source_id,
                as_of=as_of,
                missing=False,
            )
        )
    return tuple(allocations)


class TestOnlyActualSpendAdapter:
    """Synthetic fixture adapter. Never labeled customer-governed."""

    __test__ = False

    def __init__(
        self,
        *,
        source: ActualSpendSourceRef | None = None,
        rows: tuple[RawActualSpendRow, ...] = (),
        error_code: str | None = None,
        freshness: ActualsFreshnessState = ActualsFreshnessState.UNKNOWN,
    ) -> None:
        if source is not None and source.authority is not ActualSpendAuthority.TEST_ONLY:
            raise ValueError("TestOnlyActualSpendAdapter cannot carry customer-governed authority.")
        self._source = source
        self._rows = rows
        self._error_code = error_code
        self.freshness = freshness

    def resolve_source(self, *, tenant_id: str, project_id: str) -> ActualSpendSourceRef | None:
        if self._error_code == "ACTUALS_SOURCE_NOT_CONFIGURED":
            return None
        if self._source is None:
            return None
        if self._source.tenant_id != tenant_id or self._source.project_id != project_id:
            return None
        return self._source

    def query_allocations(
        self,
        *,
        source: ActualSpendSourceRef,
        fiscal_year: int | None,
        fiscal_start_month: int,
        known_market_ids: frozenset[str] | set[str],
        expected_currency: str | None = None,
    ) -> tuple[ActualSpendAllocation, ...]:
        if source.authority is not ActualSpendAuthority.TEST_ONLY:
            raise ActualsSourceUnavailableError(
                "TEST_ONLY adapter refused a non-synthetic actuals source.",
                code="ACTUALS_SOURCE_UNAVAILABLE",
            )
        if self._error_code == "ACTUALS_SOURCE_UNAVAILABLE":
            raise ActualsSourceUnavailableError(
                "Synthetic actuals source is unavailable.",
                code="ACTUALS_SOURCE_UNAVAILABLE",
            )
        return rollup_raw_actuals(
            self._rows,
            source=source,
            fiscal_year=fiscal_year,
            fiscal_start_month=fiscal_start_month,
            known_market_ids=known_market_ids,
            expected_currency=expected_currency,
        )


class DataFoundationActualSpendAdapter:
    """Reads an existing Data Foundation SourceBinding. Does not discover new warehouses."""

    def __init__(
        self,
        store: DataFoundationStore,
        *,
        rows: ActualSpendRowSource | None = None,
    ) -> None:
        self._store = store
        self._rows = rows

    def resolve_source(self, *, tenant_id: str, project_id: str) -> ActualSpendSourceRef | None:
        candidates = [
            binding
            for binding in self._store.list_bindings(tenant_id=tenant_id, workspace_id=project_id)
            if binding_supports_portfolio_actuals(binding)
        ]
        if not candidates:
            return None
        governed = [item for item in candidates if item.governance_import_ready]
        if not governed:
            return None
        binding = next((item for item in governed if item.canonical), governed[0])
        assessment = self._store.get_assessment(binding.source_id)
        freshness = freshness_from_assessment(assessment)
        status = ActualSpendSourceStatus.CONFIGURED
        if freshness is ActualsFreshnessState.STALE:
            status = ActualSpendSourceStatus.STALE
        elif freshness is ActualsFreshnessState.FRESH:
            status = ActualSpendSourceStatus.FRESH
        elif freshness is ActualsFreshnessState.UNKNOWN:
            status = ActualSpendSourceStatus.UNKNOWN
        now = datetime.now(UTC)
        resource = binding.resource
        return ActualSpendSourceRef(
            actuals_source_id=new_actuals_source_id(),
            tenant_id=binding.tenant_id,
            project_id=binding.workspace_id,
            workspace_id=binding.workspace_id,
            source_kind=ActualSpendSourceKind.DATA_FOUNDATION,
            source_ref=binding.source_id,
            bq_project_id=resource.project_id,
            bq_dataset_id=resource.dataset_id,
            bq_table_or_view_id=resource.table_id,
            as_of=None if assessment is None else assessment.assessed_at,
            currency=binding.contract.currency,
            timezone=binding.contract.timezone,
            channel_registry_version=1,
            authority=ActualSpendAuthority.DATA_FOUNDATION_VERIFIED,
            status=status,
            source_fingerprint=metadata_fingerprint(
                {
                    "source_id": binding.source_id,
                    "schema_fingerprint": binding.contract.schema_fingerprint,
                    "timezone": binding.contract.timezone,
                    "currency": binding.contract.currency,
                    "period_rule": PERIOD_AGGREGATION_RULE,
                    "as_of": None if assessment is None else assessment.assessed_at.isoformat(),
                }
            ),
            created_at=now,
            updated_at=now,
        )

    def query_allocations(
        self,
        *,
        source: ActualSpendSourceRef,
        fiscal_year: int | None,
        fiscal_start_month: int,
        known_market_ids: frozenset[str] | set[str],
        expected_currency: str | None = None,
    ) -> tuple[ActualSpendAllocation, ...]:
        if source.authority is ActualSpendAuthority.TEST_ONLY:
            raise ActualsSourceUnavailableError(
                "Data Foundation adapter does not serve TEST_ONLY actuals.",
                code="ACTUALS_SOURCE_UNAVAILABLE",
            )
        binding = self._store.get_binding(source.source_ref)
        if binding is None or not binding_supports_portfolio_actuals(binding):
            raise ActualsSourceNotConfiguredError(
                "No governed actual-spend SourceBinding is configured.",
                code="ACTUALS_SOURCE_NOT_CONFIGURED",
            )
        if binding.location_type is not LocationType.BIGQUERY and self._rows is None:
            raise ActualsSchemaInvalidError(
                "Portfolio actuals require a BigQuery SourceBinding with "
                "date/market/channel/spend.",
                code="ACTUALS_SCHEMA_INVALID",
            )
        if self._rows is None:
            raise ActualsSourceUnavailableError(
                "Governed actual-spend source could not be queried. "
                f"{P6_03_PRODUCTION_ACTUALS_QUERY_PENDING}.",
                code="ACTUALS_SOURCE_UNAVAILABLE",
            )
        try:
            raw = self._rows.fetch_rows(source)
        except Exception as exc:
            raise ActualsSourceUnavailableError(
                "Governed actual-spend source could not be queried.",
                code="ACTUALS_SOURCE_UNAVAILABLE",
            ) from exc
        return rollup_raw_actuals(
            raw,
            source=source,
            fiscal_year=fiscal_year,
            fiscal_start_month=fiscal_start_month,
            known_market_ids=known_market_ids,
            expected_currency=expected_currency,
        )


def query_actuals(
    adapter: ActualSpendQuery | None,
    *,
    tenant_id: str,
    project_id: str,
    fiscal_year: int | None,
    fiscal_start_month: int,
    known_market_ids: frozenset[str] | set[str],
    expected_currency: str | None,
) -> ActualSpendQueryResult:
    if adapter is None:
        return ActualSpendQueryResult(
            source=None,
            allocations=(),
            freshness=ActualsFreshnessState.UNKNOWN,
            error_code="ACTUALS_SOURCE_NOT_CONFIGURED",
        )
    source = adapter.resolve_source(tenant_id=tenant_id, project_id=project_id)
    if source is None:
        return ActualSpendQueryResult(
            source=None,
            allocations=(),
            freshness=ActualsFreshnessState.UNKNOWN,
            error_code="ACTUALS_SOURCE_NOT_CONFIGURED",
        )
    freshness = ActualsFreshnessState.UNKNOWN
    if isinstance(adapter, TestOnlyActualSpendAdapter):
        freshness = adapter.freshness
    if source.status is ActualSpendSourceStatus.STALE:
        freshness = ActualsFreshnessState.STALE
    elif source.status is ActualSpendSourceStatus.FRESH:
        freshness = ActualsFreshnessState.FRESH
    try:
        allocations = adapter.query_allocations(
            source=source,
            fiscal_year=fiscal_year,
            fiscal_start_month=fiscal_start_month,
            known_market_ids=known_market_ids,
            expected_currency=expected_currency,
        )
    except ActualsSourceUnavailableError:
        return ActualSpendQueryResult(
            source=source,
            allocations=(),
            freshness=freshness,
            error_code="ACTUALS_SOURCE_UNAVAILABLE",
        )
    except (
        PeriodMappingRequiredError,
        CurrencyReviewRequiredError,
        UnresolvedMarketIdentityError,
        UnresolvedChannelIdentityError,
        ActualsSchemaInvalidError,
        ActualsSourceNotConfiguredError,
    ):
        raise
    return ActualSpendQueryResult(
        source=source,
        allocations=allocations,
        freshness=freshness,
        error_code=None,
    )

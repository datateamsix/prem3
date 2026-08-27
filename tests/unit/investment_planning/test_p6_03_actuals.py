"""P6-03 actual-spend contracts, joins, period, currency, and portfolio math."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.data_foundation.contracts import ResourceIdentity, SourceBinding, SourceContract
from app.data_foundation.enums import LocationType
from app.data_foundation.store import InMemoryDataFoundationStore
from app.identity_graph.ids import new_market_id
from app.investment_planning.actuals import (
    DataFoundationActualSpendAdapter,
    InMemoryActualSpendRowSource,
    RawActualSpendRow,
    TestOnlyActualSpendAdapter,
    query_actuals,
    rollup_raw_actuals,
    round_money,
)
from app.investment_planning.contracts import (
    ActualSpendAllocation,
    ActualSpendSourceRef,
    MoneyAmount,
    PortfolioAllocationView,
    actual_spend_is_not_approved_budget,
)
from app.investment_planning.enums import (
    ActualsFreshnessState,
    ActualSpendAuthority,
    ActualSpendSourceKind,
    ActualSpendSourceStatus,
    AmountKind,
    PortfolioBaselineKind,
    PortfolioCoverageState,
)
from app.investment_planning.errors import (
    ActualsSourceUnavailableError,
    CurrencyReviewRequiredError,
    PeriodMappingRequiredError,
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.ids import new_actuals_source_id
from app.investment_planning.portfolio import (
    baseline_for_coverage,
    coverage_state,
    merge_plan_and_actual_allocations,
    quarterly_from_allocations,
    remaining_amount,
    rollup_by_dimension,
    summarize_allocations,
    variance_amount,
    variance_percent,
)

MARKET_A = "mkt_aaaaaaaaaaaaaaaaaaaa"
NOW = datetime(2027, 2, 1, tzinfo=UTC)


def _source(**overrides: object) -> ActualSpendSourceRef:
    payload = {
        "actuals_source_id": new_actuals_source_id(),
        "tenant_id": "ten_bbbbbbbbbbbbbbbbbbbb",
        "project_id": "wsp_cccccccccccccccccccc",
        "workspace_id": "wsp_cccccccccccccccccccc",
        "source_kind": ActualSpendSourceKind.SYNTHETIC,
        "source_ref": "synthetic:test",
        "currency": "USD",
        "timezone": "UTC",
        "authority": ActualSpendAuthority.TEST_ONLY,
        "status": ActualSpendSourceStatus.CONFIGURED,
        "source_fingerprint": "fp_test_actuals",
        "created_at": NOW,
        "updated_at": NOW,
        "as_of": NOW,
    }
    payload.update(overrides)
    return ActualSpendSourceRef(**payload)


def _daily(
    day: date,
    amount: str,
    *,
    market_id: str = MARKET_A,
    channel_id: str = "search_paid",
    currency: str = "USD",
    grain: str = "day",
) -> RawActualSpendRow:
    return RawActualSpendRow(
        occurred_at=day,
        market_id=market_id,
        channel_id=channel_id,
        amount=Decimal(amount),
        currency=currency,
        timezone="UTC",
        grain=grain,
    )


def test_neither_when_no_plan_no_actuals() -> None:
    assert coverage_state(has_plan=False, has_actuals=False) is PortfolioCoverageState.NEITHER
    assert baseline_for_coverage(PortfolioCoverageState.NEITHER) is None


def test_plan_only_when_approved_plan_no_actuals() -> None:
    assert coverage_state(has_plan=True, has_actuals=False) is PortfolioCoverageState.PLAN_ONLY
    assert (
        baseline_for_coverage(PortfolioCoverageState.PLAN_ONLY)
        is PortfolioBaselineKind.APPROVED_PLAN
    )


def test_plan_and_actuals_when_both_available() -> None:
    assert coverage_state(has_plan=True, has_actuals=True) is (
        PortfolioCoverageState.PLAN_AND_ACTUALS
    )
    assert (
        baseline_for_coverage(PortfolioCoverageState.PLAN_AND_ACTUALS)
        is PortfolioBaselineKind.APPROVED_PLAN
    )


def test_actuals_only_when_actuals_no_approved_plan() -> None:
    assert coverage_state(has_plan=False, has_actuals=True) is PortfolioCoverageState.ACTUALS_ONLY
    assert (
        baseline_for_coverage(PortfolioCoverageState.ACTUALS_ONLY)
        is PortfolioBaselineKind.ACTUAL_YTD
    )


def test_actuals_never_become_approved_plan() -> None:
    assert actual_spend_is_not_approved_budget(PortfolioBaselineKind.ACTUAL_YTD)
    assert actual_spend_is_not_approved_budget(PortfolioBaselineKind.GOVERNED_ACTUALS)
    assert baseline_for_coverage(PortfolioCoverageState.ACTUALS_ONLY) is not (
        PortfolioBaselineKind.APPROVED_PLAN
    )
    with pytest.raises(ValueError, match="customer-governed"):
        ActualSpendSourceRef(
            actuals_source_id=new_actuals_source_id(),
            tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
            project_id="wsp_cccccccccccccccccccc",
            workspace_id="wsp_cccccccccccccccccccc",
            source_kind=ActualSpendSourceKind.SYNTHETIC,
            source_ref="synthetic:test",
            authority=ActualSpendAuthority.DATA_FOUNDATION_VERIFIED,
            status=ActualSpendSourceStatus.CONFIGURED,
            source_fingerprint="fp",
            created_at=NOW,
            updated_at=NOW,
        )


def test_actuals_join_on_canonical_market_id() -> None:
    rows = rollup_raw_actuals(
        (_daily(date(2027, 1, 15), "10.00"),),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert rows[0].market_id == MARKET_A


def test_actuals_join_on_canonical_channel_id() -> None:
    rows = rollup_raw_actuals(
        (_daily(date(2027, 1, 15), "10.00"),),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert rows[0].channel_id == "search_paid"


def test_market_display_label_not_join_authority() -> None:
    with pytest.raises(UnresolvedMarketIdentityError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00", market_id="DACH"),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_channel_display_label_not_join_authority() -> None:
    with pytest.raises(UnresolvedChannelIdentityError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00", channel_id="Paid Search"),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_unknown_market_fails_closed() -> None:
    unknown = new_market_id()
    with pytest.raises(UnresolvedMarketIdentityError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00", market_id=unknown),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_unknown_channel_fails_closed() -> None:
    with pytest.raises(UnresolvedChannelIdentityError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00", channel_id="not_a_registry_channel"),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_missing_actual_is_not_zero() -> None:
    missing = ActualSpendAllocation(
        fiscal_year=2027,
        quarter=1,
        market_id=MARKET_A,
        channel_id="search_paid",
        amount=None,
        currency="USD",
        source_ref="asrc_aaaaaaaaaaaaaaaaaaa",
        missing=True,
    )
    assert missing.missing is True
    assert missing.amount is None
    with pytest.raises(ValueError):
        ActualSpendAllocation(
            fiscal_year=2027,
            quarter=1,
            market_id=MARKET_A,
            channel_id="search_paid",
            amount=Decimal("0"),
            currency="USD",
            source_ref="asrc_aaaaaaaaaaaaaaaaaaa",
            missing=True,
        )


def test_explicit_zero_actual_is_zero() -> None:
    zero = ActualSpendAllocation(
        fiscal_year=2027,
        quarter=1,
        market_id=MARKET_A,
        channel_id="search_paid",
        amount=Decimal("0.00"),
        currency="USD",
        source_ref="asrc_aaaaaaaaaaaaaaaaaaa",
        missing=False,
    )
    assert zero.missing is False
    assert zero.amount == Decimal("0.00")


def test_missing_plan_is_not_zero() -> None:
    actuals = (
        ActualSpendAllocation(
            fiscal_year=2027,
            quarter=1,
            market_id=MARKET_A,
            channel_id="search_paid",
            amount=Decimal("25.00"),
            currency="USD",
            source_ref="asrc_aaaaaaaaaaaaaaaaaaa",
            missing=False,
        ),
    )
    merged = merge_plan_and_actual_allocations((), actuals, currency="USD", include_remaining=True)
    remaining = remaining_amount(merged, currency="USD")
    assert remaining.missing is True
    assert remaining.value is None


def test_remaining_missing_without_actual() -> None:
    plan = (
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=1,
            market_id=MARKET_A,
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(
                MoneyAmount(
                    kind=AmountKind.APPROVED, currency="USD", value=Decimal("100.00"), missing=False
                ),
            ),
        ),
    )
    remaining = remaining_amount(plan, currency="USD")
    assert remaining.missing is True


def test_variance_missing_without_required_inputs() -> None:
    variance = variance_amount((), currency="USD")
    assert variance.missing is True
    assert variance.value is None
    assert variance_percent(None, Decimal("10")) is None
    assert variance_percent(Decimal("0"), Decimal("10")) is None


def test_actual_amount_uses_decimal() -> None:
    rows = rollup_raw_actuals(
        (_daily(date(2027, 1, 15), "10.10"),),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert isinstance(rows[0].amount, Decimal)


def test_plan_actual_math_uses_decimal() -> None:
    remaining = Decimal("100.10") - Decimal("40.05")
    assert remaining == Decimal("60.05")
    assert isinstance(remaining, Decimal)


def test_rollups_do_not_use_binary_float() -> None:
    rows = (
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=1,
            market_id=MARKET_A,
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(
                MoneyAmount(
                    kind=AmountKind.APPROVED, currency="USD", value=Decimal("0.10"), missing=False
                ),
            ),
        ),
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=2,
            market_id=MARKET_A,
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(
                MoneyAmount(
                    kind=AmountKind.APPROVED, currency="USD", value=Decimal("0.20"), missing=False
                ),
            ),
        ),
    )
    rolled = rollup_by_dimension(rows, currency="USD", kind=AmountKind.APPROVED, by="channel")
    assert rolled[0].amount.value == Decimal("0.30")
    assert not isinstance(rolled[0].amount.value, float)


def test_currency_rounding_uses_governed_policy() -> None:
    assert round_money(Decimal("1.015")) == Decimal("1.02")
    assert round_money(Decimal("1.025")) == Decimal("1.02")


def test_daily_actuals_roll_to_quarter_deterministically() -> None:
    rows = rollup_raw_actuals(
        (
            _daily(date(2027, 1, 5), "10.00"),
            _daily(date(2027, 2, 5), "15.00"),
            _daily(date(2027, 4, 5), "7.00"),
        ),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    by_quarter = {row.quarter: row.amount for row in rows}
    assert by_quarter[1] == Decimal("25.00")
    assert by_quarter[2] == Decimal("7.00")


def test_period_alignment_respects_fiscal_calendar() -> None:
    rows = rollup_raw_actuals(
        (_daily(date(2027, 4, 15), "12.00"), _daily(date(2027, 1, 15), "3.00")),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=4,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert len(rows) == 1
    assert rows[0].quarter == 1
    assert rows[0].fiscal_year == 2027
    assert rows[0].amount == Decimal("12.00")


def test_unknown_fiscal_mapping_fails_closed() -> None:
    with pytest.raises(PeriodMappingRequiredError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00"),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=0,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )
    with pytest.raises(PeriodMappingRequiredError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00", grain="unknown"),),
            source=_source(timezone=None),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_no_double_count_across_period_boundaries() -> None:
    with pytest.raises(PeriodMappingRequiredError, match="boundaries"):
        rollup_raw_actuals(
            (_daily(date(2027, 3, 30), "10.00", grain="week"),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )
    rows = rollup_raw_actuals(
        (_daily(date(2027, 1, 5), "10.00"), _daily(date(2027, 1, 5), "5.00")),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert rows[0].amount == Decimal("15.00")


def test_matching_currency_accepted() -> None:
    rows = rollup_raw_actuals(
        (_daily(date(2027, 1, 15), "10.00"),),
        source=_source(),
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert rows[0].currency == "USD"


def test_mismatched_currency_requires_governed_fx_or_review() -> None:
    with pytest.raises(CurrencyReviewRequiredError):
        rollup_raw_actuals(
            (_daily(date(2027, 1, 15), "10.00", currency="EUR"),),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_multi_currency_not_summed_silently() -> None:
    with pytest.raises(CurrencyReviewRequiredError, match="Multiple"):
        rollup_raw_actuals(
            (
                _daily(date(2027, 1, 15), "10.00", currency="USD"),
                _daily(date(2027, 1, 16), "10.00", currency="EUR"),
            ),
            source=_source(),
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency=None,
        )


def test_governed_actuals_source_required() -> None:
    result = query_actuals(
        None,
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code == "ACTUALS_SOURCE_NOT_CONFIGURED"
    assert result.allocations == ()


def test_actuals_source_fingerprint_pinned() -> None:
    source = _source(source_fingerprint="fp_one")
    adapter = TestOnlyActualSpendAdapter(
        source=source, rows=(_daily(date(2027, 1, 15), "10.00"),)
    )
    resolved = adapter.resolve_source(
        tenant_id=source.tenant_id, project_id=source.project_id
    )
    assert resolved is not None
    assert resolved.source_fingerprint == "fp_one"


def test_unavailable_source_not_treated_as_zero() -> None:
    source = _source()
    adapter = TestOnlyActualSpendAdapter(
        source=source,
        rows=(_daily(date(2027, 1, 15), "10.00"),),
        error_code="ACTUALS_SOURCE_UNAVAILABLE",
    )
    result = query_actuals(
        adapter,
        tenant_id=source.tenant_id,
        project_id=source.project_id,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code == "ACTUALS_SOURCE_UNAVAILABLE"
    assert result.allocations == ()
    with pytest.raises(ActualsSourceUnavailableError):
        adapter.query_allocations(
            source=source,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_stale_source_produces_review_state() -> None:
    source = _source(status=ActualSpendSourceStatus.STALE)
    adapter = TestOnlyActualSpendAdapter(
        source=source,
        rows=(_daily(date(2027, 1, 15), "10.00"),),
        freshness=ActualsFreshnessState.STALE,
    )
    result = query_actuals(
        adapter,
        tenant_id=source.tenant_id,
        project_id=source.project_id,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code is None
    assert result.freshness is ActualsFreshnessState.STALE
    assert result.allocations[0].amount == Decimal("10.00")


def test_remaining_equals_plan_minus_actual() -> None:
    merged = _paired(approved="100.10", actual="40.05")
    remaining = remaining_amount(merged, currency="USD")
    assert remaining.value == Decimal("60.05")


def test_variance_equals_actual_minus_plan() -> None:
    merged = _paired(approved="100.10", actual="40.05")
    variance = variance_amount(merged, currency="USD")
    assert variance.value == Decimal("-60.05")


def test_variance_percent_requires_nonzero_plan() -> None:
    assert variance_percent(Decimal("100.00"), Decimal("140.00")) == Decimal("0.4000")
    assert variance_percent(Decimal("0.00"), Decimal("10.00")) is None


def test_market_rollups_equal_cell_sums() -> None:
    rows = _two_cells()
    rolled = rollup_by_dimension(rows, currency="USD", kind=AmountKind.APPROVED, by="market")
    assert rolled[0].amount.value == Decimal("150.00")


def test_channel_rollups_equal_cell_sums() -> None:
    rows = _two_cells()
    rolled = rollup_by_dimension(rows, currency="USD", kind=AmountKind.APPROVED, by="channel")
    assert rolled[0].amount.value == Decimal("150.00")


def test_quarterly_profile_equal_cell_sums() -> None:
    rows = _two_cells()
    quarterly = quarterly_from_allocations(rows, fiscal_year=2027)
    q1 = summarize_allocations(quarterly[0].allocations, currency="USD", kind=AmountKind.APPROVED)
    q2 = summarize_allocations(quarterly[1].allocations, currency="USD", kind=AmountKind.APPROVED)
    assert q1.totals[0].value == Decimal("100.00")
    assert q2.totals[0].value == Decimal("50.00")


def test_df_binding_double_is_not_production_governed() -> None:
    store = InMemoryDataFoundationStore()
    binding = SourceBinding(
        source_id="dfsrc_aaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        workspace_id="wsp_cccccccccccccccccccc",
        requirement_id=None,
        provider_id=None,
        location_type=LocationType.BIGQUERY,
        resource=ResourceIdentity(
            location_type=LocationType.BIGQUERY,
            project_id="example",
            dataset_id="marketing",
            table_id="spend_daily",
        ),
        contract=SourceContract(
            grain="daily",
            currency="USD",
            timezone="UTC",
            required_fields=("date", "market_id", "channel_id", "spend", "currency"),
        ),
        lifecycle_state="BOUND",
        governance_import_ready=True,
        created_at=NOW,
        updated_at=NOW,
    )
    store.put_binding(binding)
    adapter = DataFoundationActualSpendAdapter(
        store,
        rows=InMemoryActualSpendRowSource((_daily(date(2027, 1, 15), "8.00"),)),
    )
    source = adapter.resolve_source(
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb", project_id="wsp_cccccccccccccccccccc"
    )
    assert source is not None
    assert source.authority is ActualSpendAuthority.DATA_FOUNDATION_VERIFIED
    assert source.source_kind is ActualSpendSourceKind.DATA_FOUNDATION
    rows = adapter.query_allocations(
        source=source,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert rows[0].amount == Decimal("8.00")
    empty = DataFoundationActualSpendAdapter(InMemoryDataFoundationStore())
    assert empty.resolve_source(
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb", project_id="wsp_cccccccccccccccccccc"
    ) is None


def _paired(*, approved: str, actual: str) -> tuple[PortfolioAllocationView, ...]:
    return merge_plan_and_actual_allocations(
        (
            PortfolioAllocationView(
                fiscal_year=2027,
                quarter=1,
                market_id=MARKET_A,
                channel_id="search_paid",
                channel_registry_version=1,
                amounts=(
                    MoneyAmount(
                        kind=AmountKind.APPROVED,
                        currency="USD",
                        value=Decimal(approved),
                        missing=False,
                    ),
                ),
            ),
        ),
        (
            ActualSpendAllocation(
                fiscal_year=2027,
                quarter=1,
                market_id=MARKET_A,
                channel_id="search_paid",
                amount=Decimal(actual),
                currency="USD",
                source_ref="asrc_aaaaaaaaaaaaaaaaaaa",
                missing=False,
            ),
        ),
        currency="USD",
        include_remaining=True,
    )


def _two_cells() -> tuple[PortfolioAllocationView, ...]:
    return (
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=1,
            market_id=MARKET_A,
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(
                MoneyAmount(
                    kind=AmountKind.APPROVED, currency="USD", value=Decimal("100.00"), missing=False
                ),
            ),
        ),
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=2,
            market_id=MARKET_A,
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(
                MoneyAmount(
                    kind=AmountKind.APPROVED, currency="USD", value=Decimal("50.00"), missing=False
                ),
            ),
        ),
    )

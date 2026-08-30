"""Transient PortfolioView assembly. Drive owns amounts; Firestore stores refs only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.investment_planning.actuals import round_money
from app.investment_planning.contracts import (
    ActualSpendAllocation,
    BudgetColumnMapping,
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioEvidenceCoverage,
    PortfolioObservation,
    PortfolioSourceFreshness,
    PortfolioSummary,
    PortfolioView,
    QuarterlyPortfolioView,
    actual_spend_is_not_approved_budget,
)
from app.investment_planning.enums import AmountKind, PortfolioBaselineKind, PortfolioCoverageState
from app.investment_planning.parser import ParsedBudgetTable, parse_decimal_cell

CHANNEL_REGISTRY_VERSION = 1
QUARTER_INDEX = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


@dataclass(frozen=True, slots=True)
class DimensionTotal:
    market_id: str | None
    channel_id: str | None
    amount: MoneyAmount


def coverage_state(*, has_plan: bool, has_actuals: bool) -> PortfolioCoverageState:
    if has_plan and has_actuals:
        return PortfolioCoverageState.PLAN_AND_ACTUALS
    if has_plan:
        return PortfolioCoverageState.PLAN_ONLY
    if has_actuals:
        return PortfolioCoverageState.ACTUALS_ONLY
    return PortfolioCoverageState.NEITHER


def baseline_for_coverage(state: PortfolioCoverageState) -> PortfolioBaselineKind | None:
    if state is PortfolioCoverageState.PLAN_AND_ACTUALS:
        return PortfolioBaselineKind.APPROVED_PLAN
    if state is PortfolioCoverageState.PLAN_ONLY:
        return PortfolioBaselineKind.APPROVED_PLAN
    if state is PortfolioCoverageState.ACTUALS_ONLY:
        return PortfolioBaselineKind.ACTUAL_YTD
    return None


def allocations_from_plan_table(
    *,
    table: ParsedBudgetTable,
    mapping: BudgetColumnMapping,
    fiscal_year: int,
    amount_kind: AmountKind,
) -> tuple[PortfolioAllocationView, ...]:
    if mapping.market_column is None or mapping.channel_column is None:
        return ()
    rows: list[PortfolioAllocationView] = []
    for row in table.rows:
        market_id = row.cells.get(mapping.market_column, "").strip()
        channel_id = row.cells.get(mapping.channel_column, "").strip()
        if not market_id or not channel_id:
            continue
        for header in mapping.quarter_columns:
            quarter = QUARTER_INDEX.get(header.strip().upper())
            if quarter is None:
                continue
            parsed = parse_decimal_cell(row.cells.get(header, ""))
            amount = MoneyAmount(
                kind=amount_kind,
                currency="USD",
                value=parsed.value,
                missing=parsed.missing,
            )
            if quarter not in (1, 2, 3, 4):
                continue
            rows.append(
                PortfolioAllocationView(
                    fiscal_year=fiscal_year,
                    quarter=quarter,
                    market_id=market_id,
                    channel_id=channel_id,
                    channel_registry_version=CHANNEL_REGISTRY_VERSION,
                    amounts=(amount,),
                )
            )
    return tuple(rows)


def summarize_allocations(
    allocations: tuple[PortfolioAllocationView, ...], *, currency: str, kind: AmountKind
) -> PortfolioSummary:
    total = Decimal("0")
    any_present = False
    for allocation in allocations:
        for amount in allocation.amounts:
            if amount.kind is kind and not amount.missing and amount.value is not None:
                total += amount.value
                any_present = True
    if not any_present:
        return PortfolioSummary(
            currency=currency,
            totals=(MoneyAmount(kind=kind, currency=currency, value=None, missing=True),),
        )
    return PortfolioSummary(
        currency=currency,
        totals=(
            MoneyAmount(
                kind=kind, currency=currency, value=round_money(total), missing=False
            ),
        ),
    )


def _amount_for_kind(allocation: PortfolioAllocationView, kind: AmountKind) -> MoneyAmount | None:
    for amount in allocation.amounts:
        if amount.kind is kind:
            return amount
    return None


def remaining_amount(
    allocations: tuple[PortfolioAllocationView, ...], *, currency: str
) -> MoneyAmount:
    """Plan minus actual when both exist. Missing actuals stay missing, not zero."""
    remaining = Decimal("0")
    any_pair = False
    for allocation in allocations:
        approved = _amount_for_kind(allocation, AmountKind.APPROVED)
        actual = _amount_for_kind(allocation, AmountKind.ACTUAL)
        if (
            approved is None
            or actual is None
            or approved.missing
            or actual.missing
            or approved.value is None
            or actual.value is None
        ):
            continue
        remaining += approved.value - actual.value
        any_pair = True
    if not any_pair:
        return MoneyAmount(kind=AmountKind.REMAINING, currency=currency, value=None, missing=True)
    return MoneyAmount(
        kind=AmountKind.REMAINING, currency=currency, value=round_money(remaining), missing=False
    )


def variance_amount(
    allocations: tuple[PortfolioAllocationView, ...], *, currency: str
) -> MoneyAmount:
    """Actual minus plan when both exist. Missing inputs stay missing, not zero."""
    total = Decimal("0")
    any_pair = False
    for allocation in allocations:
        approved = _amount_for_kind(allocation, AmountKind.APPROVED)
        actual = _amount_for_kind(allocation, AmountKind.ACTUAL)
        if (
            approved is None
            or actual is None
            or approved.missing
            or actual.missing
            or approved.value is None
            or actual.value is None
        ):
            continue
        total += actual.value - approved.value
        any_pair = True
    if not any_pair:
        return MoneyAmount(kind=AmountKind.ACTUAL, currency=currency, value=None, missing=True)
    return MoneyAmount(
        kind=AmountKind.ACTUAL,
        currency=currency,
        value=round_money(total),
        missing=False,
    )


def variance_percent(approved: Decimal | None, actual: Decimal | None) -> Decimal | None:
    if approved is None or actual is None or approved == 0:
        return None
    return ((actual - approved) / approved).quantize(Decimal("0.0001"))


def cell_remaining(
    approved: MoneyAmount | None, actual: MoneyAmount | None, *, currency: str
) -> MoneyAmount:
    if (
        approved is None
        or actual is None
        or approved.missing
        or actual.missing
        or approved.value is None
        or actual.value is None
    ):
        return MoneyAmount(kind=AmountKind.REMAINING, currency=currency, value=None, missing=True)
    return MoneyAmount(
        kind=AmountKind.REMAINING,
        currency=currency,
        value=round_money(approved.value - actual.value),
        missing=False,
    )


def merge_plan_and_actual_allocations(
    plan_rows: tuple[PortfolioAllocationView, ...],
    actual_rows: tuple[ActualSpendAllocation, ...],
    *,
    currency: str,
    include_remaining: bool,
) -> tuple[PortfolioAllocationView, ...]:
    grouped: dict[tuple[int, int, str, str], list[MoneyAmount]] = {}
    registry_version = CHANNEL_REGISTRY_VERSION
    for row in plan_rows:
        key = (row.fiscal_year, row.quarter, row.market_id, row.channel_id)
        grouped.setdefault(key, [])
        grouped[key].extend(row.amounts)
        registry_version = row.channel_registry_version
    for row in actual_rows:
        key = (row.fiscal_year, row.quarter, row.market_id, row.channel_id)
        grouped.setdefault(key, [])
        grouped[key].append(
            MoneyAmount(
                kind=AmountKind.ACTUAL,
                currency=row.currency,
                value=row.amount,
                missing=row.missing,
            )
        )
    merged: list[PortfolioAllocationView] = []
    for (fiscal_year, quarter, market_id, channel_id), amounts in sorted(grouped.items()):
        approved = next((item for item in amounts if item.kind is AmountKind.APPROVED), None)
        actual = next((item for item in amounts if item.kind is AmountKind.ACTUAL), None)
        combined = list(amounts)
        if include_remaining:
            combined.append(cell_remaining(approved, actual, currency=currency))
        merged.append(
            PortfolioAllocationView(
                fiscal_year=fiscal_year,
                quarter=cast_quarter(quarter),
                market_id=market_id,
                channel_id=channel_id,
                channel_registry_version=registry_version,
                amounts=tuple(combined),
            )
        )
    return tuple(merged)


def cast_quarter(quarter: int) -> Literal[1, 2, 3, 4]:
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1-4.")
    mapping: dict[int, Literal[1, 2, 3, 4]] = {1: 1, 2: 2, 3: 3, 4: 4}
    return mapping[quarter]


def rollup_by_dimension(
    allocations: tuple[PortfolioAllocationView, ...],
    *,
    currency: str,
    kind: AmountKind,
    by: str,
) -> tuple[DimensionTotal, ...]:
    grouped: dict[tuple[str | None, str | None], Decimal | None] = {}
    present: dict[tuple[str | None, str | None], bool] = {}
    for allocation in allocations:
        if by == "market":
            key: tuple[str | None, str | None] = (allocation.market_id, None)
        elif by == "channel":
            key = (None, allocation.channel_id)
        else:
            key = (allocation.market_id, allocation.channel_id)
        current = grouped.get(key)
        saw_value = present.get(key, False)
        for amount in allocation.amounts:
            if amount.kind is not kind or amount.missing or amount.value is None:
                continue
            saw_value = True
            current = amount.value if current is None else current + amount.value
        grouped[key] = current
        present[key] = saw_value
    rows: list[DimensionTotal] = []
    for (market_id, channel_id), total in sorted(
        grouped.items(), key=lambda item: (item[0][0] or "", item[0][1] or "")
    ):
        missing = not present[(market_id, channel_id)]
        rows.append(
            DimensionTotal(
                market_id=market_id,
                channel_id=channel_id,
                amount=MoneyAmount(
                    kind=kind,
                    currency=currency,
                    value=None if missing else round_money(total),
                    missing=missing,
                ),
            )
        )
    return tuple(rows)


def quarterly_from_allocations(
    allocations: tuple[PortfolioAllocationView, ...], *, fiscal_year: int
) -> tuple[QuarterlyPortfolioView, ...]:
    by_quarter: dict[int, list[PortfolioAllocationView]] = {1: [], 2: [], 3: [], 4: []}
    for allocation in allocations:
        by_quarter[allocation.quarter].append(allocation)
    return tuple(
        QuarterlyPortfolioView(
            fiscal_year=fiscal_year,
            quarter=quarter,
            allocations=tuple(by_quarter[quarter]),
        )
        for quarter in (1, 2, 3, 4)
    )


def assemble_portfolio_view(
    *,
    snapshot_id: str,
    tenant_id: str,
    project_id: str,
    fiscal_year: int,
    currency: str,
    baseline_kind: PortfolioBaselineKind,
    allocations: tuple[PortfolioAllocationView, ...],
    coverage: PortfolioEvidenceCoverage,
    freshness: PortfolioSourceFreshness,
    coverage_state: PortfolioCoverageState | None = None,
    observations: tuple[PortfolioObservation, ...] = (),
) -> PortfolioView:
    if coverage_state is PortfolioCoverageState.PLAN_AND_ACTUALS:
        totals = (
            *summarize_allocations(allocations, currency=currency, kind=AmountKind.APPROVED).totals,
            *summarize_allocations(allocations, currency=currency, kind=AmountKind.ACTUAL).totals,
            remaining_amount(allocations, currency=currency),
        )
        summary = PortfolioSummary(currency=currency, totals=totals)
    elif actual_spend_is_not_approved_budget(baseline_kind) or (
        coverage_state is PortfolioCoverageState.ACTUALS_ONLY
    ):
        summary = summarize_allocations(allocations, currency=currency, kind=AmountKind.ACTUAL)
    else:
        summary = summarize_allocations(allocations, currency=currency, kind=AmountKind.APPROVED)
    return PortfolioView(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        project_id=project_id,
        fiscal_year=fiscal_year,
        currency=currency,
        baseline_kind=baseline_kind,
        summary=summary,
        allocations=allocations,
        quarterly=quarterly_from_allocations(allocations, fiscal_year=fiscal_year),
        coverage=coverage,
        freshness=freshness,
        observations=observations,
    )

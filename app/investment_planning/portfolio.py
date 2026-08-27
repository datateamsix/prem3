"""Transient PortfolioView assembly. Drive owns amounts; Firestore stores refs only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.investment_planning.contracts import (
    BudgetColumnMapping,
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioEvidenceCoverage,
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
        return PortfolioBaselineKind.GOVERNED_ACTUALS
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
        totals=(MoneyAmount(kind=kind, currency=currency, value=total, missing=False),),
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
    return MoneyAmount(kind=AmountKind.REMAINING, currency=currency, value=remaining, missing=False)


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
                    value=None if missing else total,
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
) -> PortfolioView:
    kind = (
        AmountKind.ACTUAL
        if actual_spend_is_not_approved_budget(baseline_kind)
        else AmountKind.APPROVED
    )
    return PortfolioView(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        project_id=project_id,
        fiscal_year=fiscal_year,
        currency=currency,
        baseline_kind=baseline_kind,
        summary=summarize_allocations(allocations, currency=currency, kind=kind),
        allocations=allocations,
        quarterly=quarterly_from_allocations(allocations, fiscal_year=fiscal_year),
        coverage=coverage,
        freshness=freshness,
    )

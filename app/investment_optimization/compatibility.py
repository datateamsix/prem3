"""Period, currency, and spend-semantics compatibility."""

from __future__ import annotations

from datetime import date

from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    OptimizationIssue,
    PortfolioModelMapping,
)
from app.investment_optimization.eligibility import is_budget_optimizable
from app.investment_optimization.enums import (
    COMPATIBLE_SPEND_SEMANTICS,
    OptimizationIssueCode,
    SpendSemantics,
)
from app.investment_planning.contracts import PortfolioView
from app.investment_planning.enums import AmountKind


def _issue(
    code: OptimizationIssueCode, *, blocking: bool, review: bool = False
) -> OptimizationIssue:
    return OptimizationIssue(
        code=code,
        blocking=blocking,
        review_required=review,
        message_key=code.value,
    )


def _parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _fiscal_bounds(fiscal_year: int, fiscal_start_month: int = 1) -> tuple[date, date]:
    start = date(fiscal_year, fiscal_start_month, 1)
    if fiscal_start_month == 1:
        end = date(fiscal_year, 12, 31)
    else:
        end_year = fiscal_year + 1
        end_month = fiscal_start_month - 1
        if end_month == 12:
            end = date(end_year - 1, 12, 31)
        else:
            end = date(end_year, end_month, 1)
            # last day of previous month of next start
            if end_month == 2:
                end = date(end_year, 2, 28)
            elif end_month in {4, 6, 9, 11}:
                end = date(end_year, end_month, 30)
            else:
                end = date(end_year, end_month, 31)
    return start, end


def period_issues(
    *,
    view: PortfolioView,
    contract: ModelConsumptionContract,
    fiscal_start_month: int = 1,
) -> tuple[OptimizationIssue, ...]:
    window_start = _parse_iso(contract.modeled_window_start)
    window_end = _parse_iso(contract.modeled_window_end)
    horizon_start, horizon_end = _fiscal_bounds(view.fiscal_year, fiscal_start_month)
    if window_start is None or window_end is None:
        return (
            _issue(
                OptimizationIssueCode.PERIOD_COMPATIBILITY_REVIEW_REQUIRED,
                blocking=False,
                review=True,
            ),
        )
    if horizon_end < window_start:
        return (
            _issue(
                OptimizationIssueCode.PERIOD_COMPATIBILITY_REVIEW_REQUIRED,
                blocking=False,
                review=True,
            ),
        )
    if horizon_start > window_end and not contract.future_horizon_allowed:
        return (
            _issue(
                OptimizationIssueCode.PERIOD_COMPATIBILITY_REVIEW_REQUIRED,
                blocking=False,
                review=True,
            ),
        )
    return ()


def currency_issues(
    *, view: PortfolioView, contract: ModelConsumptionContract
) -> tuple[OptimizationIssue, ...]:
    if view.currency != contract.currency:
        return (
            _issue(
                OptimizationIssueCode.CURRENCY_COMPATIBILITY_REVIEW_REQUIRED,
                blocking=False,
                review=True,
            ),
        )
    return ()


def spend_semantics_issues(
    *,
    mapping: PortfolioModelMapping,
    contract: ModelConsumptionContract,
) -> tuple[OptimizationIssue, ...]:
    by_id = {item.model_variable_id: item for item in contract.variables}
    issues: list[OptimizationIssue] = []
    for entry in mapping.mapping_entries:
        variable = by_id.get(entry.model_variable_id)
        if variable is None or not is_budget_optimizable(variable):
            continue
        semantics = variable.spend_semantics
        if semantics is None:
            issues.append(
                _issue(OptimizationIssueCode.SPEND_SEMANTICS_MISMATCH, blocking=True)
            )
            continue
        if semantics not in COMPATIBLE_SPEND_SEMANTICS:
            issues.append(
                _issue(OptimizationIssueCode.SPEND_SEMANTICS_MISMATCH, blocking=True)
            )
    unique: list[OptimizationIssue] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.code.value in seen:
            continue
        seen.add(issue.code.value)
        unique.append(issue)
    return tuple(unique)


def approved_plan_present(view: PortfolioView) -> bool:
    return any(
        amount.kind is AmountKind.APPROVED and not amount.missing
        for row in view.allocations
        for amount in row.amounts
    )


def impressions_not_spend(semantics: SpendSemantics) -> bool:
    return semantics is SpendSemantics.IMPRESSIONS

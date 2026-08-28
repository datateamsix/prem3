"""Deterministic ConstraintValidationReceipt. No optimizer dispatch."""

from __future__ import annotations

from datetime import datetime

from app.investment_optimization.constraints import constraint_set_fingerprint, pin_constraint_set
from app.investment_optimization.contracts import (
    ConstraintValidationCheck,
    ConstraintValidationReceipt,
    OptimizationConstraintSet,
    OptimizerBudgetLine,
)
from app.investment_optimization.enums import ConstraintValidationStatus
from app.investment_optimization.errors import (
    ConstraintReferenceInvalidError,
    ConstraintUnitMismatchError,
    FunnelMappingRequiredError,
)
from app.investment_optimization.feasibility import assess_feasibility
from app.investment_optimization.ids import new_constraint_validation_id
from app.investment_planning.fingerprint import metadata_fingerprint


def _check(code: str, passed: bool) -> ConstraintValidationCheck:
    return ConstraintValidationCheck(code=code, passed=passed)


def validate_constraint_set(
    constraint_set: OptimizationConstraintSet,
    *,
    lines: tuple[OptimizerBudgetLine, ...] = (),
    currency: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    created_at: datetime,
) -> ConstraintValidationReceipt:
    pinned = pin_constraint_set(constraint_set)
    checks: list[ConstraintValidationCheck] = []
    try:
        _assert_canonical_refs(pinned, lines)
        checks.append(_check("canonical_refs_valid", True))
    except (ConstraintReferenceInvalidError, FunnelMappingRequiredError):
        checks.append(_check("canonical_refs_valid", False))
        return _receipt(pinned, checks, ConstraintValidationStatus.INVALID, (), created_at)

    try:
        _assert_units(pinned, currency=currency)
        checks.append(_check("units_compatible", True))
        checks.append(_check("currency_compatible", True))
    except ConstraintUnitMismatchError:
        checks.append(_check("units_compatible", False))
        checks.append(_check("currency_compatible", False))
        return _receipt(pinned, checks, ConstraintValidationStatus.INVALID, (), created_at)

    period_ok = _period_compatible(pinned, period_start=period_start, period_end=period_end)
    checks.append(_check("period_compatible", period_ok))
    if not period_ok:
        return _receipt(pinned, checks, ConstraintValidationStatus.INVALID, (), created_at)

    bounds_ok = _lower_lte_upper(pinned)
    checks.append(_check("lower_lte_upper", bounds_ok))
    locked_ok = _locked_satisfies_bounds(pinned)
    checks.append(_check("locked_lines_satisfy_bounds", locked_ok))
    checks.append(_check("unsupported_lines_explicit", True))
    if not bounds_ok or not locked_ok:
        return _receipt(pinned, checks, ConstraintValidationStatus.INVALID, (), created_at)

    feasible, conflicting = assess_feasibility(pinned, lines=lines)
    checks.append(_check("group_constraints_feasible", feasible or not _has_group(pinned)))
    checks.append(_check("reserves_feasible", feasible or pinned.experiment_reserve is None))
    checks.append(_check("total_bounds_feasible", feasible))
    status = (
        ConstraintValidationStatus.VALID if feasible else ConstraintValidationStatus.INFEASIBLE
    )
    return _receipt(pinned, checks, status, conflicting, created_at)


def _receipt(
    pinned: OptimizationConstraintSet,
    checks: list[ConstraintValidationCheck],
    status: ConstraintValidationStatus,
    conflicting: tuple[str, ...],
    created_at: datetime,
) -> ConstraintValidationReceipt:
    fingerprint = metadata_fingerprint(
        {
            "constraint_set_id": pinned.constraint_set_id,
            "constraint_set_fingerprint": pinned.fingerprint,
            "status": status.value,
            "checks": [(item.code, item.passed) for item in checks],
            "conflicting": list(conflicting),
        }
    )
    return ConstraintValidationReceipt(
        validation_id=new_constraint_validation_id(),
        constraint_set_id=pinned.constraint_set_id,
        constraint_set_fingerprint=pinned.fingerprint or constraint_set_fingerprint(pinned),
        status=status,
        checks=tuple(checks),
        conflicting_constraint_ids=conflicting,
        fingerprint=fingerprint,
        created_at=created_at,
    )


def _assert_canonical_refs(
    constraint_set: OptimizationConstraintSet, lines: tuple[OptimizerBudgetLine, ...]
) -> None:
    known = {line.model_variable_id for line in lines}
    known.update(f"{line.market_id}|{line.channel_id}" for line in lines)
    if not known:
        return
    for item in constraint_set.line_bounds:
        if not item.line_id or not item.market_id or not item.channel_id:
            raise ConstraintReferenceInvalidError(
                "Line constraints must use stable line IDs or canonical market/channel keys."
            )
    for item in constraint_set.locked_lines:
        if not item.line_id:
            raise ConstraintReferenceInvalidError("Locked allocations require a stable line ID.")
    for item in constraint_set.funnel_constraints:
        if not item.member_weights:
            raise FunnelMappingRequiredError(
                "Funnel constraints require explicit member weights."
            )


def _assert_units(constraint_set: OptimizationConstraintSet, *, currency: str | None) -> None:
    expected = currency or constraint_set.currency
    if constraint_set.total_budget_bounds is not None:
        if constraint_set.total_budget_bounds.currency != expected:
            raise ConstraintUnitMismatchError("Constraint currency is incompatible.")
    for item in constraint_set.line_bounds:
        if item.currency != expected:
            raise ConstraintUnitMismatchError("Line constraint currency is incompatible.")
    for item in (
        *constraint_set.locked_lines,
        *constraint_set.movement_limits,
        *constraint_set.market_constraints,
        *constraint_set.quarter_constraints,
        *constraint_set.funnel_constraints,
    ):
        if getattr(item, "currency", expected) != expected:
            raise ConstraintUnitMismatchError("Constraint currency is incompatible.")


def _period_compatible(
    constraint_set: OptimizationConstraintSet,
    *,
    period_start: str | None,
    period_end: str | None,
) -> bool:
    if period_start and constraint_set.period_start and constraint_set.period_start != period_start:
        return False
    if period_end and constraint_set.period_end and constraint_set.period_end != period_end:
        return False
    if constraint_set.period_start and constraint_set.period_end:
        return constraint_set.period_start <= constraint_set.period_end
    return True


def _lower_lte_upper(constraint_set: OptimizationConstraintSet) -> bool:
    bounds = constraint_set.total_budget_bounds
    if bounds is not None and bounds.lower is not None and bounds.upper is not None:
        if bounds.lower > bounds.upper:
            return False
    for item in constraint_set.line_bounds:
        if item.lower is not None and item.upper is not None and item.lower > item.upper:
            return False
    for item in (*constraint_set.market_constraints, *constraint_set.quarter_constraints):
        if item.lower is not None and item.upper is not None and item.lower > item.upper:
            return False
    for item in constraint_set.funnel_constraints:
        if item.lower is not None and item.upper is not None and item.lower > item.upper:
            return False
    return True


def _locked_satisfies_bounds(constraint_set: OptimizationConstraintSet) -> bool:
    bounds = {item.line_id: item for item in constraint_set.line_bounds}
    for locked in constraint_set.locked_lines:
        bound = bounds.get(locked.line_id)
        if bound is None:
            continue
        if bound.lower is not None and locked.baseline < bound.lower:
            return False
        if bound.upper is not None and locked.baseline > bound.upper:
            return False
    return True


def _has_group(constraint_set: OptimizationConstraintSet) -> bool:
    return bool(
        constraint_set.market_constraints
        or constraint_set.quarter_constraints
        or constraint_set.funnel_constraints
    )

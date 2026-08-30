"""Prove a constraint set admits at least one feasible allocation."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.contracts import OptimizationConstraintSet, OptimizerBudgetLine
from app.investment_optimization.enums import ConstraintFamily, ModelVariableOptimizationEligibility
from app.investment_optimization.errors import (
    ConstraintSetInfeasibleError,
    FunnelMappingRequiredError,
)
from app.investment_planning.actuals import round_money


def assess_feasibility(
    constraint_set: OptimizationConstraintSet,
    *,
    lines: tuple[OptimizerBudgetLine, ...] = (),
) -> tuple[bool, tuple[str, ...]]:
    """Return (feasible, conflicting constraint ids)."""
    intervals = _line_intervals(constraint_set, lines)
    if not intervals:
        return True, ()
    conflicting: list[str] = []
    for line_id, (lower, upper) in intervals.items():
        if lower > upper:
            conflicting.extend(_line_constraint_ids(constraint_set, line_id))
    if conflicting:
        return False, tuple(dict.fromkeys(conflicting))

    total_lo = sum((lo for lo, _hi in intervals.values()), Decimal("0"))
    total_hi = sum((hi for _lo, hi in intervals.values()), Decimal("0"))
    bounds = constraint_set.total_budget_bounds
    if bounds is not None:
        if bounds.lower is not None and total_hi < bounds.lower:
            conflicting.append("total_budget_bounds")
        if bounds.upper is not None and total_lo > bounds.upper:
            conflicting.append("total_budget_bounds")
    if constraint_set.total_budget is not None:
        if total_lo > constraint_set.total_budget or total_hi < constraint_set.total_budget:
            conflicting.append("total_budget")

    reserve = Decimal("0")
    if constraint_set.experiment_reserve is not None:
        reserve += constraint_set.experiment_reserve.amount
    if constraint_set.contingency_reserve is not None:
        reserve += constraint_set.contingency_reserve.amount
    max_total = bounds.upper if bounds is not None and bounds.upper is not None else total_hi
    if reserve > max_total:
        if constraint_set.experiment_reserve is not None:
            conflicting.append(constraint_set.experiment_reserve.constraint_id)
        if constraint_set.contingency_reserve is not None:
            conflicting.append(constraint_set.contingency_reserve.constraint_id)

    _check_groups(constraint_set.market_constraints, intervals, conflicting)
    _check_groups(constraint_set.quarter_constraints, intervals, conflicting)
    _check_funnels(constraint_set, intervals, conflicting)

    unique = tuple(dict.fromkeys(conflicting))
    return (not unique), unique


def prove_feasible(
    constraint_set: OptimizationConstraintSet,
    *,
    lines: tuple[OptimizerBudgetLine, ...] = (),
) -> None:
    feasible, conflicting = assess_feasibility(constraint_set, lines=lines)
    if not feasible:
        raise ConstraintSetInfeasibleError(
            "Constraint set does not admit a feasible allocation.",
            conflicting_constraint_ids=conflicting,
        )


def _line_intervals(
    constraint_set: OptimizationConstraintSet,
    lines: tuple[OptimizerBudgetLine, ...],
) -> dict[str, tuple[Decimal, Decimal]]:
    intervals: dict[str, tuple[Decimal, Decimal]] = {}
    baseline = {line.model_variable_id: line.baseline for line in lines}
    for line in lines:
        if line.eligibility is ModelVariableOptimizationEligibility.UNSUPPORTED:
            continue
        intervals[line.model_variable_id] = (Decimal("0"), Decimal("Infinity"))
    locked_ids = set(constraint_set.locked_line_ids)
    for locked in constraint_set.locked_lines:
        locked_ids.add(locked.line_id)
        intervals[locked.line_id] = (locked.baseline, locked.baseline)
    for line_id in locked_ids:
        if (
            line_id in baseline
            and line_id not in {item.line_id for item in constraint_set.locked_lines}
        ):
            intervals[line_id] = (baseline[line_id], baseline[line_id])
    for bound in constraint_set.line_bounds:
        lo, hi = intervals.get(bound.line_id, (Decimal("0"), Decimal("Infinity")))
        if bound.lower is not None:
            lo = max(lo, bound.lower)
        if bound.upper is not None:
            hi = min(hi, bound.upper)
        intervals[bound.line_id] = (lo, hi)
    for move in constraint_set.movement_limits:
        base = baseline.get(move.line_id)
        if base is None:
            continue
        lo, hi = intervals.get(move.line_id, (Decimal("0"), Decimal("Infinity")))
        if move.max_absolute_move is not None:
            lo = max(lo, base - move.max_absolute_move)
            hi = min(hi, base + move.max_absolute_move)
        if move.max_percent_move is not None:
            if base == 0:
                if not move.percent_unavailable:
                    continue
            else:
                delta = round_money(base * move.max_percent_move / Decimal("100"))
                lo = max(lo, base - delta)
                hi = min(hi, base + delta)
        intervals[move.line_id] = (max(lo, Decimal("0")), hi)
    return intervals


def _line_constraint_ids(constraint_set: OptimizationConstraintSet, line_id: str) -> list[str]:
    ids: list[str] = []
    ids.extend(
        item.constraint_id for item in constraint_set.line_bounds if item.line_id == line_id
    )
    ids.extend(
        item.constraint_id for item in constraint_set.locked_lines if item.line_id == line_id
    )
    ids.extend(
        item.constraint_id for item in constraint_set.movement_limits if item.line_id == line_id
    )
    return ids or [line_id]


def _check_groups(
    groups, intervals: dict[str, tuple[Decimal, Decimal]], conflicting: list[str]
) -> None:
    for group in groups:
        members = [intervals[line_id] for line_id in group.member_line_ids if line_id in intervals]
        if not members:
            continue
        hi = sum((item[1] for item in members), Decimal("0"))
        lo = sum((item[0] for item in members), Decimal("0"))
        if group.lower is not None and hi < group.lower:
            conflicting.append(group.constraint_id)
        if group.upper is not None and lo > group.upper:
            conflicting.append(group.constraint_id)


def _check_funnels(
    constraint_set: OptimizationConstraintSet,
    intervals: dict[str, tuple[Decimal, Decimal]],
    conflicting: list[str],
) -> None:
    for funnel in constraint_set.funnel_constraints:
        if not funnel.member_weights:
            raise FunnelMappingRequiredError("Funnel constraints require explicit member weights.")
        lo = Decimal("0")
        hi = Decimal("0")
        unbounded_hi = False
        for line_id, weight in funnel.member_weights:
            if weight < 0:
                raise FunnelMappingRequiredError("Funnel weights cannot be negative.")
            if line_id not in intervals:
                continue
            line_lo, line_hi = intervals[line_id]
            lo += line_lo * weight
            if line_hi == Decimal("Infinity"):
                unbounded_hi = True
            elif not unbounded_hi:
                hi += line_hi * weight
        if funnel.lower is not None and (not unbounded_hi) and hi < funnel.lower:
            conflicting.append(funnel.constraint_id)
        if funnel.upper is not None and lo > funnel.upper:
            conflicting.append(funnel.constraint_id)


def family_for_total(constraint_set: OptimizationConstraintSet) -> ConstraintFamily:
    if constraint_set.total_budget_bounds is not None:
        return ConstraintFamily.TOTAL_FLEXIBLE_BUDGET
    return ConstraintFamily.TOTAL_FIXED_BUDGET

"""P6-07 constraint construction, validation, and feasibility."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.investment_optimization.constraint_validate import validate_constraint_set
from app.investment_optimization.contracts import MoneyBounds
from app.investment_optimization.enums import (
    ConstraintFamily,
    ConstraintValidationStatus,
    ModelVariableOptimizationEligibility,
)
from app.investment_optimization.errors import ConstraintSetInfeasibleError
from app.investment_optimization.feasibility import assess_feasibility, prove_feasible
from tests.unit.investment_optimization.p6_04_support import now
from tests.unit.investment_optimization.p6_07_support import (
    budget_line,
    constraint_set,
    funnel,
    group,
    line_bound,
    locked_line,
    movement,
    reserve,
)


def _lines() -> tuple:
    return (budget_line(),)


def test_floor_and_ceiling() -> None:
    payload = constraint_set(
        line_bounds=(
            line_bound(family=ConstraintFamily.LINE_MIN, lower="40.00", upper="150.00"),
        )
    )
    receipt = validate_constraint_set(payload, lines=_lines(), created_at=now())
    assert receipt.status is ConstraintValidationStatus.VALID
    feasible, _ids = assess_feasibility(payload, lines=_lines())
    assert feasible is True


def test_locked() -> None:
    payload = constraint_set(locked_lines=(locked_line(baseline="100.00"),))
    prove_feasible(payload, lines=_lines())
    receipt = validate_constraint_set(payload, lines=_lines(), created_at=now())
    assert receipt.status is ConstraintValidationStatus.VALID


def test_abs_and_percent_move() -> None:
    abs_set = constraint_set(
        movement_limits=(
            movement(family=ConstraintFamily.MAX_ABSOLUTE_MOVE, abs_move="10.00"),
        )
    )
    prove_feasible(abs_set, lines=_lines())
    pct_set = constraint_set(
        movement_limits=(
            movement(family=ConstraintFamily.MAX_PERCENT_MOVE, pct_move="20.00"),
        )
    )
    prove_feasible(pct_set, lines=_lines())
    zero = constraint_set(
        movement_limits=(
            movement(
                family=ConstraintFamily.MAX_PERCENT_MOVE,
                pct_move="20.00",
                percent_unavailable=True,
            ),
        )
    )
    prove_feasible(
        zero,
        lines=(
            budget_line(
                baseline="0.00",
                eligibility=ModelVariableOptimizationEligibility.OPTIMIZABLE,
            ),
        ),
    )


def test_market() -> None:
    payload = constraint_set(
        market_constraints=(
            group(
                family=ConstraintFamily.MARKET_FLOOR,
                group_id="mkt_us",
                members=("search_spend",),
                lower="50.00",
            ),
        )
    )
    prove_feasible(payload, lines=_lines())


def test_quarter() -> None:
    payload = constraint_set(
        quarter_constraints=(
            group(
                family=ConstraintFamily.QUARTER_CEILING,
                group_id="2027-Q1",
                members=("search_spend",),
                upper="200.00",
            ),
        )
    )
    prove_feasible(payload, lines=_lines())


def test_funnel_weighted() -> None:
    payload = constraint_set(funnel_constraints=(funnel(lower="40.00"),))
    prove_feasible(payload, lines=_lines())
    empty = constraint_set(
        funnel_constraints=(funnel(members=(), lower="40.00"),),
    )
    receipt = validate_constraint_set(empty, lines=_lines(), created_at=now())
    assert receipt.status is ConstraintValidationStatus.INVALID


def test_experiment_reserve() -> None:
    payload = constraint_set(
        experiment_reserve=reserve(amount="10.00"),
        total_budget=Decimal("100.00"),
        line_bounds=(line_bound(family=ConstraintFamily.LINE_MIN, lower="0.00"),),
    )
    prove_feasible(payload, lines=_lines())


def test_infeasible_rejected() -> None:
    lines = (
        budget_line(),
        budget_line("other_spend", channel_id="other", baseline="100.00"),
    )
    payload = constraint_set(
        line_bounds=(
            line_bound(lower="80.00"),
            line_bound(line_id="other_spend", lower="80.00"),
        ),
        total_budget_bounds=MoneyBounds(upper=Decimal("100.00")),
    )
    with pytest.raises(ConstraintSetInfeasibleError) as exc:
        prove_feasible(payload, lines=lines)
    assert exc.value.conflicting_constraint_ids
    receipt = validate_constraint_set(payload, lines=lines, created_at=now())
    assert receipt.status is ConstraintValidationStatus.INFEASIBLE

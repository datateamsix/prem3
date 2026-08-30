"""Validate native optimizer output before persistence. Fail closed."""

from __future__ import annotations

import math
from decimal import Decimal

from app.investment_optimization.contracts import (
    BindingConstraint,
    NativeOptimizerRawResult,
    OptimizationConstraintSet,
    OptimizationInputContract,
    OptimizationResultRow,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import (
    ConstraintFamily,
    ModelVariableOptimizationEligibility,
    OptimizerConstraintStatus,
)
from app.investment_optimization.errors import (
    OptimizerResultInvalidError,
    ResultConstraintViolationError,
)
from app.investment_planning.actuals import round_money


def _finite(value: float, *, field: str) -> None:
    if math.isnan(value):
        raise OptimizerResultInvalidError(f"Native optimizer returned NaN for {field}.")
    if math.isinf(value):
        raise OptimizerResultInvalidError(f"Native optimizer returned infinity for {field}.")


def validate_raw_result(
    *,
    vector: OptimizerBudgetVector,
    input_contract: OptimizationInputContract,
    raw: NativeOptimizerRawResult,
) -> None:
    expected = set(input_contract.optimizable_variable_ids)
    if not expected:
        expected = {
            line.model_variable_id
            for line in vector.lines
            if line.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
        }
    returned = {item.model_variable_id for item in raw.channels}
    unknown = returned - expected - set(input_contract.fixed_variable_ids)
    if unknown:
        raise OptimizerResultInvalidError(
            "Native optimizer returned an unknown model variable."
        )
    missing = expected - returned
    if missing:
        raise OptimizerResultInvalidError(
            "Native optimizer omitted an expected optimizable model variable."
        )
    excluded = set(input_contract.excluded_variable_ids)
    if returned & excluded:
        raise OptimizerResultInvalidError(
            "Excluded model variables cannot be reallocated by the optimizer."
        )
    for item in raw.channels:
        _finite(item.recommended_spend, field=item.model_variable_id)
        if item.recommended_spend < 0:
            raise OptimizerResultInvalidError(
                "Negative recommended spend is rejected in V1."
            )


def validate_reconciled_rows(
    *,
    vector: OptimizerBudgetVector,
    input_contract: OptimizationInputContract,
    rows: tuple[OptimizationResultRow, ...],
    fixed_budget: Decimal,
    min_total: Decimal | None = None,
    max_total: Decimal | None = None,
    require_fixed_total: bool = True,
) -> None:
    by_id = {row.model_variable_id: row for row in rows}
    expected = {
        line.model_variable_id
        for line in vector.lines
        if line.eligibility
        in {
            ModelVariableOptimizationEligibility.OPTIMIZABLE,
            ModelVariableOptimizationEligibility.FIXED,
        }
    }
    if set(by_id) != expected:
        if expected - set(by_id):
            raise OptimizerResultInvalidError(
                "Result is missing an expected mapped variable. Zero is distinct from missing."
            )
        raise OptimizerResultInvalidError("Result contains an unexpected model variable.")
    for line in vector.lines:
        if line.eligibility is ModelVariableOptimizationEligibility.FIXED:
            row = by_id[line.model_variable_id]
            if row.recommended != round_money(line.baseline):
                raise OptimizerResultInvalidError("Fixed model variables must remain unchanged.")
        if line.model_variable_id in input_contract.excluded_variable_ids:
            if line.model_variable_id in by_id:
                raise OptimizerResultInvalidError(
                    "Excluded model variables cannot be reallocated."
                )
    for row in rows:
        if row.recommended < Decimal("0"):
            raise OptimizerResultInvalidError("Negative recommended spend is rejected in V1.")
    optimizable_total = round_money(
        sum(
            (
                row.recommended
                for row in rows
                if row.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
            ),
            Decimal("0"),
        )
    )
    if require_fixed_total:
        if optimizable_total != round_money(fixed_budget):
            raise OptimizerResultInvalidError(
                "Recommended optimizable total must equal the fixed approved-plan budget."
            )
        return
    if min_total is not None and optimizable_total < round_money(min_total):
        raise ResultConstraintViolationError("Recommended total is below B_min.")
    if max_total is not None and optimizable_total > round_money(max_total):
        raise ResultConstraintViolationError("Recommended total exceeds B_max.")


def validate_constraint_result(
    *,
    constraint_set: OptimizationConstraintSet,
    rows: tuple[OptimizationResultRow, ...],
) -> tuple[BindingConstraint, ...]:
    by_id = {row.model_variable_id: row for row in rows}
    bindings: list[BindingConstraint] = []
    quantum = Decimal("0.01")
    for bound in constraint_set.line_bounds:
        row = by_id.get(bound.line_id)
        if row is None:
            continue
        if bound.lower is not None and row.recommended < bound.lower:
            raise ResultConstraintViolationError("LINE_MIN was violated.")
        if bound.upper is not None and row.recommended > bound.upper:
            raise ResultConstraintViolationError("LINE_MAX was violated.")
        status = OptimizerConstraintStatus.WITHIN_BOUNDS
        if bound.lower is not None and abs(row.recommended - bound.lower) <= quantum:
            status = OptimizerConstraintStatus.AT_LOWER
        elif bound.upper is not None and abs(row.recommended - bound.upper) <= quantum:
            status = OptimizerConstraintStatus.AT_UPPER
        if status is not OptimizerConstraintStatus.WITHIN_BOUNDS:
            bindings.append(
                BindingConstraint(
                    constraint_id=bound.constraint_id,
                    family=bound.family,
                    status=status,
                    subject_line_id=bound.line_id,
                )
            )
    for locked in constraint_set.locked_lines:
        row = by_id.get(locked.line_id)
        if row is None:
            continue
        if row.recommended != round_money(locked.baseline):
            raise ResultConstraintViolationError("LOCKED_ALLOCATION was violated.")
        bindings.append(
            BindingConstraint(
                constraint_id=locked.constraint_id,
                family=ConstraintFamily.LOCKED_ALLOCATION,
                status=OptimizerConstraintStatus.AT_LOWER,
                subject_line_id=locked.line_id,
            )
        )
    totals = {
        market_id: Decimal("0")
        for market_id in {row.market_id for row in rows}
    }
    for row in rows:
        totals[row.market_id] = totals.get(row.market_id, Decimal("0")) + row.recommended
    for group in constraint_set.market_constraints:
        amount = sum(
            (by_id[line_id].recommended for line_id in group.member_line_ids if line_id in by_id),
            Decimal("0"),
        )
        if group.lower is not None and amount < group.lower:
            raise ResultConstraintViolationError("MARKET_FLOOR was violated.")
        if group.upper is not None and amount > group.upper:
            raise ResultConstraintViolationError("MARKET_CEILING was violated.")
    for group in constraint_set.quarter_constraints:
        amount = sum(
            (by_id[line_id].recommended for line_id in group.member_line_ids if line_id in by_id),
            Decimal("0"),
        )
        if group.lower is not None and amount < group.lower:
            raise ResultConstraintViolationError("QUARTER_FLOOR was violated.")
        if group.upper is not None and amount > group.upper:
            raise ResultConstraintViolationError("QUARTER_CEILING was violated.")
    for funnel in constraint_set.funnel_constraints:
        amount = Decimal("0")
        for line_id, weight in funnel.member_weights:
            if line_id not in by_id:
                continue
            amount += by_id[line_id].recommended * weight
        if funnel.lower is not None and amount < funnel.lower:
            raise ResultConstraintViolationError("FUNNEL_FLOOR was violated.")
        if funnel.upper is not None and amount > funnel.upper:
            raise ResultConstraintViolationError("FUNNEL_CEILING was violated.")
    return tuple(bindings)

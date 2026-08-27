"""Validate native optimizer output before persistence. Fail closed."""

from __future__ import annotations

import math
from decimal import Decimal

from app.investment_optimization.contracts import (
    NativeOptimizerRawResult,
    OptimizationInputContract,
    OptimizationResultRow,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import ModelVariableOptimizationEligibility
from app.investment_optimization.errors import OptimizerResultInvalidError
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
    if optimizable_total != round_money(fixed_budget):
        raise OptimizerResultInvalidError(
            "Recommended optimizable total must equal the fixed approved-plan budget."
        )

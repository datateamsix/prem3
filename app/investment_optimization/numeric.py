"""Decimal/float policy for native Meridian spend. Binary float is not amount authority."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.contracts import (
    NativeOptimizerRawResult,
    OptimizationResultRow,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import (
    PINNED_OPTIMIZER_GTOL,
    ModelVariableOptimizationEligibility,
    OptimizationAmountKind,
    OptimizerConstraintStatus,
)
from app.investment_optimization.errors import OptimizerBudgetInvariantFailedError
from app.investment_planning.actuals import round_money

_MIN_ABS_DRIFT = Decimal("0.01")


def decimal_from_float(value: float) -> Decimal:
    return Decimal(str(value))


def float_from_decimal(value: Decimal) -> float:
    return float(value)


def budget_drift_tolerance(*, budget: Decimal, gtol: float = PINNED_OPTIMIZER_GTOL) -> Decimal:
    scaled = round_money(budget * Decimal(str(gtol)))
    return max(_MIN_ABS_DRIFT, scaled)


def pct_of_spend(vector: OptimizerBudgetVector) -> tuple[float, ...]:
    optimizable = [
        line
        for line in vector.lines
        if line.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
    ]
    total = sum((line.baseline for line in optimizable), Decimal("0"))
    if total <= 0:
        raise OptimizerBudgetInvariantFailedError(
            "Approved-plan optimizable baseline must be positive to form pct_of_spend."
        )
    return tuple(float_from_decimal(line.baseline / total) for line in optimizable)


def reconcile_recommended_spends(
    *,
    vector: OptimizerBudgetVector,
    raw: NativeOptimizerRawResult,
    constraint_status: OptimizerConstraintStatus = OptimizerConstraintStatus.WITHIN_BOUNDS,
) -> tuple[OptimizationResultRow, ...]:
    """Quantize Meridian floats and force |sum(rec) - fixed| == 0 after residual cents."""
    raw_by_id = {item.model_variable_id: item for item in raw.channels}
    pre_round_total = Decimal("0")
    quantized: list[tuple[str, Decimal]] = []
    for line in vector.lines:
        if line.eligibility is not ModelVariableOptimizationEligibility.OPTIMIZABLE:
            continue
        raw_item = raw_by_id.get(line.model_variable_id)
        if raw_item is None:
            continue
        native = decimal_from_float(raw_item.recommended_spend)
        pre_round_total += native
        quantized.append((line.model_variable_id, round_money(native)))

    fixed = round_money(vector.fixed_budget)
    drift = abs(pre_round_total - fixed)
    if drift > budget_drift_tolerance(budget=fixed):
        raise OptimizerBudgetInvariantFailedError(
            "Native optimizer total drifted beyond gtol tolerance before rounding."
        )

    recommended_total = sum((amount for _vid, amount in quantized), Decimal("0"))
    residual = fixed - recommended_total
    if residual != Decimal("0") and quantized:
        ranked = sorted(
            quantized,
            key=lambda item: (-item[1], item[0]),
        )
        target_id = ranked[0][0]
        quantized = [
            (vid, amount + residual if vid == target_id else amount) for vid, amount in quantized
        ]
        quantized = [(vid, round_money(amount)) for vid, amount in quantized]

    reconciled_total = sum((amount for _vid, amount in quantized), Decimal("0"))
    if reconciled_total != fixed:
        raise OptimizerBudgetInvariantFailedError(
            "Recommended total does not equal the fixed approved-plan budget after reconcile."
        )

    amounts = dict(quantized)
    rows: list[OptimizationResultRow] = []
    for line in vector.lines:
        if line.eligibility is ModelVariableOptimizationEligibility.FIXED:
            recommended = round_money(line.baseline)
        elif line.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE:
            if line.model_variable_id not in amounts:
                continue
            recommended = amounts[line.model_variable_id]
        else:
            continue
        change = round_money(recommended - line.baseline)
        baseline_zero = line.baseline == Decimal("0.00")
        percent = None if baseline_zero else round_money((change / line.baseline) * Decimal("100"))
        raw_item = raw_by_id.get(line.model_variable_id)
        rows.append(
            OptimizationResultRow(
                model_variable_id=line.model_variable_id,
                market_id=line.market_id,
                channel_id=line.channel_id,
                eligibility=line.eligibility,
                baseline=round_money(line.baseline),
                recommended=recommended,
                absolute_change=change,
                percent_change=percent,
                percent_change_unavailable=baseline_zero,
                constraint_status=constraint_status,
                amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
                outcome_estimates=() if raw_item is None else raw_item.outcome_estimates,
            )
        )
    return tuple(rows)


def recommended_total(rows: tuple[OptimizationResultRow, ...]) -> Decimal:
    optimizable = [
        row.recommended
        for row in rows
        if row.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
    ]
    return round_money(sum(optimizable, Decimal("0")))


def reconcile_flexible_spends(
    *,
    vector: OptimizerBudgetVector,
    raw: NativeOptimizerRawResult,
) -> tuple[OptimizationResultRow, ...]:
    """Quantize native floats. Total follows the native recommendation, not a fixed budget."""
    raw_by_id = {item.model_variable_id: item for item in raw.channels}
    quantized: list[tuple[str, Decimal]] = []
    pre_round_total = Decimal("0")
    for line in vector.lines:
        if line.eligibility is not ModelVariableOptimizationEligibility.OPTIMIZABLE:
            continue
        raw_item = raw_by_id.get(line.model_variable_id)
        if raw_item is None:
            continue
        native = decimal_from_float(raw_item.recommended_spend)
        pre_round_total += native
        quantized.append((line.model_variable_id, round_money(native)))
    target = round_money(pre_round_total)
    recommended_sum = sum((amount for _vid, amount in quantized), Decimal("0"))
    residual = target - recommended_sum
    if residual != Decimal("0") and quantized:
        ranked = sorted(quantized, key=lambda item: (-item[1], item[0]))
        target_id = ranked[0][0]
        quantized = [
            (vid, amount + residual if vid == target_id else amount) for vid, amount in quantized
        ]
        quantized = [(vid, round_money(amount)) for vid, amount in quantized]
    amounts = dict(quantized)
    rows: list[OptimizationResultRow] = []
    for line in vector.lines:
        if line.eligibility is ModelVariableOptimizationEligibility.FIXED:
            recommended = round_money(line.baseline)
        elif line.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE:
            if line.model_variable_id not in amounts:
                continue
            recommended = amounts[line.model_variable_id]
        else:
            continue
        change = round_money(recommended - line.baseline)
        baseline_zero = line.baseline == Decimal("0.00")
        percent = None if baseline_zero else round_money((change / line.baseline) * Decimal("100"))
        raw_item = raw_by_id.get(line.model_variable_id)
        rows.append(
            OptimizationResultRow(
                model_variable_id=line.model_variable_id,
                market_id=line.market_id,
                channel_id=line.channel_id,
                eligibility=line.eligibility,
                baseline=round_money(line.baseline),
                recommended=recommended,
                absolute_change=change,
                percent_change=percent,
                percent_change_unavailable=baseline_zero,
                constraint_status=OptimizerConstraintStatus.WITHIN_BOUNDS,
                amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
                outcome_estimates=() if raw_item is None else raw_item.outcome_estimates,
            )
        )
    return tuple(rows)

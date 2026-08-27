"""Deterministic baseline vs MODEL_RECOMMENDED comparison."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.contracts import (
    OptimizationResultPayload,
    ProposalChangeSummary,
    ScenarioComparison,
    ScenarioComparisonRow,
)
from app.investment_optimization.enums import (
    DEFAULT_PROPOSAL_LIMITATIONS,
    MATERIAL_CHANGE_POLICY_VERSION,
    MATERIAL_CHANNEL_SHARE_THRESHOLD,
    MATERIAL_MARKET_SHARE_THRESHOLD,
    MaterialChangeFlag,
    ModelVariableOptimizationEligibility,
    OptimizationAmountKind,
    ProposalLimitationCode,
)
from app.investment_planning.actuals import round_money
from app.investment_planning.fingerprint import metadata_fingerprint


def _share(amount: Decimal, total: Decimal) -> Decimal | None:
    if total == 0:
        return None
    return round_money(amount / total)


def build_comparison(
    *,
    scenario_id: str,
    payload: OptimizationResultPayload,
) -> ScenarioComparison:
    total = payload.fixed_budget
    rows: list[ScenarioComparisonRow] = []
    for row in payload.rows:
        rec_share = _share(row.recommended, total)
        base_share = _share(row.baseline, total)
        share_change = None
        if rec_share is not None and base_share is not None:
            share_change = round_money(rec_share - base_share)
        rows.append(
            ScenarioComparisonRow(
                market_id=row.market_id,
                channel_id=row.channel_id,
                model_variable_id=row.model_variable_id,
                baseline_amount=row.baseline,
                recommended_amount=row.recommended,
                delta=row.absolute_change,
                share_change=share_change,
                percent_change=row.percent_change,
                percent_change_unavailable=row.percent_change_unavailable,
                amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
            )
        )
    body = {
        "scenario_id": scenario_id,
        "row_ids": tuple(item.model_variable_id for item in rows),
        "deltas": tuple(format(item.delta, "f") for item in rows),
    }
    return ScenarioComparison(
        scenario_id=scenario_id,
        currency=payload.currency,
        amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
        rows=tuple(rows),
        fingerprint=metadata_fingerprint(body),
    )


def _material_flags(
    *,
    payload: OptimizationResultPayload,
    rows: tuple[ScenarioComparisonRow, ...],
) -> tuple[MaterialChangeFlag, ...]:
    flags: list[MaterialChangeFlag] = []
    channel_threshold = Decimal(MATERIAL_CHANNEL_SHARE_THRESHOLD)
    market_threshold = Decimal(MATERIAL_MARKET_SHARE_THRESHOLD)
    total = payload.fixed_budget
    market_delta: dict[str, Decimal] = {}
    for row in rows:
        if total > 0 and abs(row.delta) / total >= channel_threshold:
            flags.append(MaterialChangeFlag.LARGE_CHANNEL_REALLOCATION)
        if row.baseline == 0 and row.recommended_amount > 0:
            flags.append(MaterialChangeFlag.ZERO_TO_NONZERO)
        if row.baseline > 0 and row.recommended_amount == 0:
            flags.append(MaterialChangeFlag.NONZERO_TO_ZERO)
        market_delta[row.market_id] = market_delta.get(row.market_id, Decimal("0")) + row.delta
    if total > 0:
        for delta in market_delta.values():
            if abs(delta) / total >= market_threshold:
                flags.append(MaterialChangeFlag.LARGE_MARKET_REALLOCATION)
                break
    unique: list[MaterialChangeFlag] = []
    for flag in flags:
        if flag not in unique:
            unique.append(flag)
    return tuple(unique)


def build_change_summary(
    *,
    proposal_id: str,
    payload: OptimizationResultPayload,
    comparison: ScenarioComparison,
) -> ProposalChangeSummary:
    increases = [row for row in comparison.rows if row.delta > 0]
    decreases = [row for row in comparison.rows if row.delta < 0]
    unchanged = [row for row in comparison.rows if row.delta == 0]
    largest_up = tuple(
        sorted(increases, key=lambda item: (-item.delta, item.model_variable_id))[:3]
    )
    largest_down = tuple(
        sorted(decreases, key=lambda item: (item.delta, item.model_variable_id))[:3]
    )
    limitations = list(DEFAULT_PROPOSAL_LIMITATIONS)
    if any(
        row.eligibility is not ModelVariableOptimizationEligibility.OPTIMIZABLE
        for row in payload.rows
    ):
        limitations.append(ProposalLimitationCode.UNMODELED_BUDGET_FIXED)
    body = {
        "proposal_id": proposal_id,
        "changed": len(increases) + len(decreases),
        "increases": len(increases),
        "decreases": len(decreases),
        "material_policy": MATERIAL_CHANGE_POLICY_VERSION,
    }
    return ProposalChangeSummary(
        proposal_id=proposal_id,
        total_budget=payload.fixed_budget,
        changed_cell_count=len(increases) + len(decreases),
        increase_count=len(increases),
        decrease_count=len(decreases),
        unchanged_count=len(unchanged),
        largest_increases=largest_up,
        largest_decreases=largest_down,
        material_change_flags=_material_flags(payload=payload, rows=comparison.rows),
        limitation_codes=tuple(limitations),
        fingerprint=metadata_fingerprint(body),
    )

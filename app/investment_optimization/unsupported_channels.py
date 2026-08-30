"""Explicit policies for channels without accepted optimizer evidence."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.contracts import OptimizationConstraintSet, OptimizerBudgetLine
from app.investment_optimization.enums import (
    ModelVariableOptimizationEligibility,
    UnsupportedChannelPolicy,
)
from app.investment_optimization.errors import ProxyApprovalRequiredError
from app.investment_planning.actuals import round_money


def policy_for_channel(
    constraint_set: OptimizationConstraintSet | None, channel_id: str
) -> UnsupportedChannelPolicy | None:
    if constraint_set is None:
        return None
    for key, policy in constraint_set.unsupported_channel_policies:
        if key == channel_id:
            return policy
    return None


def apply_unsupported_policies(
    *,
    lines: tuple[OptimizerBudgetLine, ...],
    constraint_set: OptimizationConstraintSet | None,
    approved_proxy_channel_ids: frozenset[str] = frozenset(),
) -> tuple[OptimizerBudgetLine, ...]:
    """Keep unmodeled channels on the portfolio. Missing evidence is never zero value."""
    updated: list[OptimizerBudgetLine] = []
    for line in lines:
        policy = policy_for_channel(constraint_set, line.channel_id)
        unmodeled = line.eligibility in {
            ModelVariableOptimizationEligibility.UNSUPPORTED,
            ModelVariableOptimizationEligibility.CONTEXT_ONLY,
        }
        if policy is None and not unmodeled:
            updated.append(line)
            continue
        chosen = policy or UnsupportedChannelPolicy.HOLD_BASELINE
        if chosen is UnsupportedChannelPolicy.APPROVED_PROXY_WITH_REVIEW:
            if line.channel_id not in approved_proxy_channel_ids:
                raise ProxyApprovalRequiredError(
                    "Approved-proxy unsupported channels require explicit review approval."
                )
            updated.append(line)
            continue
        if chosen is UnsupportedChannelPolicy.EXCLUDE_FROM_OPTIMIZER_BUT_KEEP_PORTFOLIO:
            updated.append(
                line.model_copy(update={"eligibility": ModelVariableOptimizationEligibility.FIXED})
            )
            continue
        if chosen is UnsupportedChannelPolicy.RESERVE_EXPERIMENT_AMOUNT:
            updated.append(
                line.model_copy(update={"eligibility": ModelVariableOptimizationEligibility.FIXED})
            )
            continue
        # HOLD_BASELINE
        baseline = round_money(line.baseline)
        if baseline < Decimal("0"):
            baseline = Decimal("0.00")
        updated.append(
            line.model_copy(
                update={
                    "eligibility": ModelVariableOptimizationEligibility.FIXED,
                    "baseline": baseline,
                }
            )
        )
    return tuple(updated)


def experiment_reserve_amount(constraint_set: OptimizationConstraintSet | None) -> Decimal:
    if constraint_set is None or constraint_set.experiment_reserve is None:
        return Decimal("0.00")
    return round_money(constraint_set.experiment_reserve.amount)

"""Non-dominated frontier from a fingerprinted dominance policy."""

from __future__ import annotations

from app.investment_optimization.enums import DominanceMetric, DominanceSense
from app.investment_optimization.errors import FrontierDominancePolicyInvalidError
from app.investment_optimization.risk.models import (
    DominanceDimension,
    DominatedRecord,
    PortfolioRiskEvaluation,
)


def _metric_value(evaluation: PortfolioRiskEvaluation, metric: DominanceMetric) -> float | None:
    if metric is DominanceMetric.EXPECTED_OUTCOME:
        return evaluation.expected_outcome
    if metric is DominanceMetric.DOWNSIDE_TAIL:
        return evaluation.lower_tail_metric
    if metric is DominanceMetric.CONCENTRATION_HHI:
        if not evaluation.concentration_metrics:
            return None
        return evaluation.concentration_metrics[0].hhi
    if metric is DominanceMetric.STABILITY_L1:
        if not evaluation.stability_metrics:
            return None
        return evaluation.stability_metrics[0].l1_share_distance
    raise FrontierDominancePolicyInvalidError(f"Unknown dominance metric {metric}.")


def _no_worse(
    left: float,
    right: float,
    *,
    sense: DominanceSense,
) -> bool:
    if sense is DominanceSense.MAXIMIZE:
        return left >= right
    return left <= right


def _strictly_better(
    left: float,
    right: float,
    *,
    sense: DominanceSense,
) -> bool:
    if sense is DominanceSense.MAXIMIZE:
        return left > right
    return left < right


def dominates(
    left: PortfolioRiskEvaluation,
    right: PortfolioRiskEvaluation,
    *,
    policy: tuple[DominanceDimension, ...],
) -> tuple[bool, tuple[DominanceMetric, ...]]:
    if not policy:
        raise FrontierDominancePolicyInvalidError("dominance_policy must declare dimensions.")
    better_dims: list[DominanceMetric] = []
    for dimension in policy:
        left_value = _metric_value(left, dimension.metric)
        right_value = _metric_value(right, dimension.metric)
        if left_value is None or right_value is None:
            return False, ()
        if not _no_worse(left_value, right_value, sense=dimension.sense):
            return False, ()
        if _strictly_better(left_value, right_value, sense=dimension.sense):
            better_dims.append(dimension.metric)
    return bool(better_dims), tuple(better_dims)


def classify_frontier(
    evaluations: tuple[PortfolioRiskEvaluation, ...],
    *,
    policy: tuple[DominanceDimension, ...],
) -> tuple[tuple[str, ...], tuple[DominatedRecord, ...]]:
    non_dominated: list[str] = []
    dominated: list[DominatedRecord] = []
    for candidate in evaluations:
        beat_by: list[str] = []
        dims: list[DominanceMetric] = []
        for other in evaluations:
            if other.candidate_portfolio_id == candidate.candidate_portfolio_id:
                continue
            wins, used = dominates(other, candidate, policy=policy)
            if wins:
                beat_by.append(other.candidate_portfolio_id)
                dims.extend(used)
        if beat_by:
            dominated.append(
                DominatedRecord(
                    candidate_portfolio_id=candidate.candidate_portfolio_id,
                    dominated_by=tuple(sorted(set(beat_by))),
                    dominance_dimensions=tuple(dict.fromkeys(dims)),
                )
            )
        else:
            non_dominated.append(candidate.candidate_portfolio_id)
    return tuple(sorted(non_dominated)), tuple(dominated)

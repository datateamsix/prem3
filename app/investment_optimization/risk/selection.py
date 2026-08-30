"""Risk-posture selection over a fixed frontier. MODEL_RECOMMENDED only."""

from __future__ import annotations

from app.investment_optimization.enums import DominanceMetric, DominanceSense, RiskPosture
from app.investment_optimization.errors import FrontierSelectionNotAllowedError
from app.investment_optimization.risk.frontier import _metric_value
from app.investment_optimization.risk.models import (
    MarketingInvestmentFrontier,
    PortfolioRiskEvaluation,
)


def _value(evaluation: PortfolioRiskEvaluation, metric: DominanceMetric) -> float:
    value = _metric_value(evaluation, metric)
    if value is None:
        raise FrontierSelectionNotAllowedError(f"{metric} is unavailable for selection.")
    return value


def _sense(metric: DominanceMetric) -> DominanceSense:
    if metric is DominanceMetric.EXPECTED_OUTCOME:
        return DominanceSense.MAXIMIZE
    return DominanceSense.MINIMIZE


def _pick(
    evaluations: tuple[PortfolioRiskEvaluation, ...],
    *,
    keys: tuple[DominanceMetric, ...],
) -> PortfolioRiskEvaluation:
    def sort_key(item: PortfolioRiskEvaluation) -> tuple[object, ...]:
        parts: list[object] = []
        for metric in keys:
            value = _value(item, metric)
            parts.append(-value if _sense(metric) is DominanceSense.MAXIMIZE else value)
        parts.append(item.candidate_portfolio_id)
        return tuple(parts)

    return sorted(evaluations, key=sort_key)[0]


def select_candidate(
    *,
    frontier: MarketingInvestmentFrontier,
    evaluations: tuple[PortfolioRiskEvaluation, ...],
    posture: RiskPosture,
    conservative_expected_floor_ratio: float,
    balanced_keys: tuple[DominanceMetric, ...],
) -> PortfolioRiskEvaluation:
    members = {
        item
        for item in evaluations
        if item.candidate_portfolio_id in frontier.non_dominated_candidate_ids
    }
    if not members:
        raise FrontierSelectionNotAllowedError("Frontier has no non-dominated candidates.")
    pool = tuple(members)
    if posture is RiskPosture.EXPECTED_OUTCOME:
        return _pick(pool, keys=(DominanceMetric.EXPECTED_OUTCOME,))
    if posture is RiskPosture.CONSERVATIVE:
        best_expected = max(_value(item, DominanceMetric.EXPECTED_OUTCOME) for item in pool)
        floor = best_expected * conservative_expected_floor_ratio
        eligible = tuple(
            item
            for item in pool
            if _value(item, DominanceMetric.EXPECTED_OUTCOME) >= floor
        )
        if not eligible:
            raise FrontierSelectionNotAllowedError("No conservative candidate meets the floor.")
        return _pick(eligible, keys=(DominanceMetric.DOWNSIDE_TAIL,))
    if posture is RiskPosture.BALANCED:
        keys = balanced_keys or (
            DominanceMetric.EXPECTED_OUTCOME,
            DominanceMetric.DOWNSIDE_TAIL,
            DominanceMetric.CONCENTRATION_HHI,
            DominanceMetric.STABILITY_L1,
        )
        return _pick(pool, keys=keys)
    raise FrontierSelectionNotAllowedError(f"Unsupported risk posture {posture}.")

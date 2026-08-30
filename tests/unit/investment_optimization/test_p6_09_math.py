"""Deterministic CVaR, concentration, stability, and dominance math."""

from __future__ import annotations

from app.investment_optimization.enums import (
    ConcentrationDimension,
    DominanceMetric,
    DominanceSense,
    RiskBaselineKind,
)
from app.investment_optimization.risk.concentration import (
    concentration_from_shares,
    herfindahl_hirschman_index,
    top_k_share,
)
from app.investment_optimization.risk.downside import (
    conditional_value_at_risk,
    outcome_losses,
    value_at_risk,
)
from app.investment_optimization.risk.frontier import classify_frontier, dominates
from app.investment_optimization.risk.models import (
    CandidateShare,
    DominanceDimension,
    PortfolioRiskEvaluation,
)
from app.investment_optimization.risk.posterior import probability_improvement
from app.investment_optimization.risk.stability import l1_share_distance, stability_from_shares
from tests.unit.investment_optimization.p6_09_support import BASELINE_SHARES, NATIVE_SHARES


def test_cvar_is_tail_expectation() -> None:
    losses = (1.0, 2.0, 3.0, 4.0, 10.0)
    assert value_at_risk(losses, tail_probability=0.2) == 10.0
    assert conditional_value_at_risk(losses, tail_probability=0.2) == 10.0
    assert conditional_value_at_risk(losses, tail_probability=0.4) == (4.0 + 10.0) / 2


def test_loss_is_baseline_minus_candidate() -> None:
    assert outcome_losses(baseline_outcomes=(10.0, 10.0), candidate_outcomes=(8.0, 12.0)) == (
        2.0,
        -2.0,
    )


def test_probability_improvement() -> None:
    assert (
        probability_improvement(
            candidate_outcomes=(11.0, 9.0, 12.0),
            baseline_outcomes=(10.0, 10.0, 10.0),
        )
        == 2 / 3
    )


def test_hhi_and_topk() -> None:
    shares = (0.5, 0.3, 0.2)
    assert herfindahl_hirschman_index(shares) == 0.38
    assert top_k_share(shares, k=1) == 0.5
    assert top_k_share(shares, k=3) == 1.0
    metric = concentration_from_shares(NATIVE_SHARES, dimension=ConcentrationDimension.CHANNEL)
    assert metric.dimension is ConcentrationDimension.CHANNEL
    assert metric.hhi == 0.38


def test_l1_and_line_movement() -> None:
    assert l1_share_distance(candidate=NATIVE_SHARES, baseline=BASELINE_SHARES) == 0.2
    metric = stability_from_shares(
        candidate=NATIVE_SHARES,
        baseline=BASELINE_SHARES,
        baseline_kind=RiskBaselineKind.APPROVED_PLAN,
    )
    assert metric.l1_share_distance == 0.2
    assert metric.max_absolute_line_movement == 0.1
    assert metric.baseline_kind is RiskBaselineKind.APPROVED_PLAN


def _eval(candidate_id: str, expected: float, tail: float, hhi: float, l1: float):
    from datetime import UTC, datetime

    return PortfolioRiskEvaluation(
        portfolio_risk_evaluation_id=f"oreval_{candidate_id}",
        candidate_portfolio_id=candidate_id,
        baseline_portfolio_ref="plan",
        risk_evaluation_policy_ref="orpol",
        expected_outcome=expected,
        lower_tail_metric=tail,
        concentration_metrics=(
            concentration_from_shares(
                (CandidateShare(channel_id="search", share=hhi**0.5),),
                dimension=ConcentrationDimension.CHANNEL,
            ),
        ),
        stability_metrics=(
            stability_from_shares(
                candidate=NATIVE_SHARES,
                baseline=BASELINE_SHARES,
                baseline_kind=RiskBaselineKind.APPROVED_PLAN,
            ),
        ),
        evaluation_fingerprint=candidate_id,
        created_at=datetime.now(UTC),
    )


def test_dominance_and_frontier() -> None:
    policy = (
        DominanceDimension(metric=DominanceMetric.EXPECTED_OUTCOME, sense=DominanceSense.MAXIMIZE),
        DominanceDimension(metric=DominanceMetric.DOWNSIDE_TAIL, sense=DominanceSense.MINIMIZE),
    )
    high = _eval("a", 12.0, 5.0, 0.5, 0.2)
    mid = _eval("b", 11.0, 2.0, 0.4, 0.1)
    low = _eval("c", 10.0, 6.0, 0.6, 0.3)
    wins, dims = dominates(high, low, policy=policy)
    assert wins
    assert DominanceMetric.EXPECTED_OUTCOME in dims
    non_dom, dominated = classify_frontier((high, mid, low), policy=policy)
    assert "c" in {item.candidate_portfolio_id for item in dominated}
    assert "a" in non_dom
    assert "b" in non_dom

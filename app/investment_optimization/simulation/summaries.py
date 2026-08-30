"""Distribution summaries. CVaR authority stays in P6-09 downside.py."""

from __future__ import annotations

import math

from app.investment_optimization.errors import SimulationInsufficientDrawsForTailError
from app.investment_optimization.risk.downside import (
    conditional_value_at_risk,
    outcome_losses,
)
from app.investment_optimization.risk.posterior import (
    expected_outcome,
    median_outcome,
    probability_improvement,
)


def require_tail_draws(*, draw_count: int, tail_probability: float) -> None:
    needed = max(1, math.ceil(tail_probability * draw_count))
    if draw_count < 2 or needed < 1:
        raise SimulationInsufficientDrawsForTailError(
            "Draw count is too small for the requested tail metric."
        )
    if tail_probability * draw_count < 1.0:
        raise SimulationInsufficientDrawsForTailError(
            "Draw count is too small for the requested tail metric."
        )


def summarize_outcomes(
    *,
    candidate_outcomes: tuple[float, ...],
    baseline_outcomes: tuple[float, ...],
    tail_probability: float,
) -> dict[str, float | dict[str, float] | None]:
    require_tail_draws(draw_count=len(candidate_outcomes), tail_probability=tail_probability)
    losses = outcome_losses(
        baseline_outcomes=baseline_outcomes, candidate_outcomes=candidate_outcomes
    )
    ordered = tuple(sorted(candidate_outcomes))
    count = len(ordered)

    def _quantile(probability: float) -> float:
        index = min(count - 1, max(0, math.ceil(probability * count) - 1))
        return ordered[index]

    return {
        "mean": expected_outcome(candidate_outcomes),
        "median": median_outcome(candidate_outcomes),
        "quantiles": {
            "p10": _quantile(0.10),
            "p50": _quantile(0.50),
            "p90": _quantile(0.90),
        },
        "probability_vs_baseline": probability_improvement(
            candidate_outcomes=candidate_outcomes, baseline_outcomes=baseline_outcomes
        ),
        "lower_tail_metric": conditional_value_at_risk(
            losses, tail_probability=tail_probability
        ),
    }

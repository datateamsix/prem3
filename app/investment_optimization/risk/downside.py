"""Discrete CVaR / expected shortfall. Not a universal risk score."""

from __future__ import annotations

import math


def value_at_risk(losses: tuple[float, ...], *, tail_probability: float) -> float:
    if not losses:
        raise ValueError("CVaR requires at least one loss draw.")
    if not 0.0 < tail_probability < 1.0:
        raise ValueError("tail_probability must be in (0, 1).")
    # Worst-first so VaR at ceil(alpha * n) - 1 is the start of the upper tail.
    ordered = tuple(sorted(losses, reverse=True))
    index = max(0, math.ceil(tail_probability * len(ordered)) - 1)
    return ordered[index]


def conditional_value_at_risk(losses: tuple[float, ...], *, tail_probability: float) -> float:
    """CVaR_alpha = E[L | L >= VaR_alpha(L)] on a discrete sample."""
    var = value_at_risk(losses, tail_probability=tail_probability)
    tail = tuple(loss for loss in losses if loss >= var)
    return sum(tail) / len(tail)


def outcome_losses(
    *,
    baseline_outcomes: tuple[float, ...],
    candidate_outcomes: tuple[float, ...],
) -> tuple[float, ...]:
    if len(baseline_outcomes) != len(candidate_outcomes):
        raise ValueError("Baseline and candidate draws must align.")
    return tuple(
        baseline - candidate
        for baseline, candidate in zip(baseline_outcomes, candidate_outcomes, strict=True)
    )

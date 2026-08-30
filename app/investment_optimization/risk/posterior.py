"""Posterior outcome metrics from governed draws. Missing is not zero."""

from __future__ import annotations

from statistics import median


def expected_outcome(draws: tuple[float, ...]) -> float:
    if not draws:
        raise ValueError("Expected outcome requires draws.")
    return sum(draws) / len(draws)


def median_outcome(draws: tuple[float, ...]) -> float:
    if not draws:
        raise ValueError("Median outcome requires draws.")
    return float(median(draws))


def probability_improvement(
    *,
    candidate_outcomes: tuple[float, ...],
    baseline_outcomes: tuple[float, ...],
) -> float:
    if len(candidate_outcomes) != len(baseline_outcomes) or not candidate_outcomes:
        raise ValueError("Aligned non-empty draws are required.")
    wins = sum(
        1
        for candidate, baseline in zip(candidate_outcomes, baseline_outcomes, strict=True)
        if candidate > baseline
    )
    return wins / len(candidate_outcomes)

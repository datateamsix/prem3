"""Transparent concentration metrics. Concentration is not universally bad."""

from __future__ import annotations

from app.investment_optimization.enums import ConcentrationDimension
from app.investment_optimization.risk.models import CandidateShare, ConcentrationMetric


def herfindahl_hirschman_index(shares: tuple[float, ...]) -> float:
    return sum(share * share for share in shares)


def top_k_share(shares: tuple[float, ...], *, k: int) -> float:
    if k < 1:
        raise ValueError("k must be at least 1.")
    ordered = tuple(sorted(shares, reverse=True))
    return sum(ordered[:k])


def concentration_from_shares(
    lines: tuple[CandidateShare, ...],
    *,
    dimension: ConcentrationDimension,
) -> ConcentrationMetric:
    shares = tuple(line.share for line in lines)
    return ConcentrationMetric(
        dimension=dimension,
        hhi=herfindahl_hirschman_index(shares),
        top_1_share=top_k_share(shares, k=1) if shares else 0.0,
        top_3_share=top_k_share(shares, k=3) if shares else 0.0,
    )

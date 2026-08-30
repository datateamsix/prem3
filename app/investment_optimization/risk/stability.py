"""Allocation stability vs a pinned baseline. Not a confidence score."""

from __future__ import annotations

from app.investment_optimization.enums import RiskBaselineKind
from app.investment_optimization.risk.models import CandidateShare, StabilityMetric


def _round_share(value: float) -> float:
    return round(value, 12)


def _share_map(lines: tuple[CandidateShare, ...]) -> dict[str, float]:
    return {line.channel_id: line.share for line in lines}


def l1_share_distance(
    *,
    candidate: tuple[CandidateShare, ...],
    baseline: tuple[CandidateShare, ...],
) -> float:
    keys = set(_share_map(candidate)) | set(_share_map(baseline))
    cand = _share_map(candidate)
    base = _share_map(baseline)
    return _round_share(sum(abs(cand.get(key, 0.0) - base.get(key, 0.0)) for key in keys))


def max_absolute_line_movement(
    *,
    candidate: tuple[CandidateShare, ...],
    baseline: tuple[CandidateShare, ...],
) -> float:
    keys = set(_share_map(candidate)) | set(_share_map(baseline))
    cand = _share_map(candidate)
    base = _share_map(baseline)
    if not keys:
        return 0.0
    return _round_share(max(abs(cand.get(key, 0.0) - base.get(key, 0.0)) for key in keys))


def max_percent_line_movement(
    *,
    candidate: tuple[CandidateShare, ...],
    baseline: tuple[CandidateShare, ...],
) -> float | None:
    cand = _share_map(candidate)
    base = _share_map(baseline)
    ratios: list[float] = []
    for key, base_share in base.items():
        if base_share <= 0.0:
            continue
        ratios.append(abs(cand.get(key, 0.0) - base_share) / base_share)
    if not ratios:
        return None
    return _round_share(max(ratios))


def stability_from_shares(
    *,
    candidate: tuple[CandidateShare, ...],
    baseline: tuple[CandidateShare, ...],
    baseline_kind: RiskBaselineKind,
) -> StabilityMetric:
    return StabilityMetric(
        baseline_kind=baseline_kind,
        l1_share_distance=l1_share_distance(candidate=candidate, baseline=baseline),
        max_absolute_line_movement=max_absolute_line_movement(
            candidate=candidate, baseline=baseline
        ),
        max_percent_line_movement=max_percent_line_movement(
            candidate=candidate, baseline=baseline
        ),
    )

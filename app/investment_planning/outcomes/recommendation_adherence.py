"""Recommendation adherence. Not an opaque score."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import AdherenceClass
from app.investment_optimization.errors import RecommendationAdherenceNotComputableError
from app.investment_optimization.ids import new_recommendation_adherence_id
from app.investment_optimization.risk.models import CandidateShare
from app.investment_optimization.risk.stability import (
    l1_share_distance,
    max_absolute_line_movement,
)
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import RecommendationAdherence


def _share_map(shares: tuple[CandidateShare, ...]) -> dict[str, float]:
    return {line.channel_id: line.share for line in shares}


def channel_set_changes(
    *,
    recommended: tuple[CandidateShare, ...],
    decided: tuple[CandidateShare, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    rec = {key for key, value in _share_map(recommended).items() if value > 0.0}
    dec = {key for key, value in _share_map(decided).items() if value > 0.0}
    added = tuple(sorted(dec - rec))
    removed = tuple(sorted(rec - dec))
    return added, removed


def max_percentage_line_deviation(
    *,
    recommended: tuple[CandidateShare, ...],
    decided: tuple[CandidateShare, ...],
) -> float | None:
    rec = _share_map(recommended)
    dec = _share_map(decided)
    percents: list[float] = []
    for key in set(rec) | set(dec):
        base = rec.get(key, 0.0)
        if base == 0.0:
            continue
        percents.append(abs(dec.get(key, 0.0) - base) / base)
    if not percents:
        return None
    return round(max(percents), 12)


def compute_recommendation_adherence(
    *,
    tenant_id: str,
    project_id: str,
    investment_decision_ref: str,
    recommended_portfolio_ref: str,
    decided_portfolio_ref: str,
    recommended: tuple[CandidateShare, ...],
    decided: tuple[CandidateShare, ...],
) -> RecommendationAdherence:
    if not recommended or not decided:
        raise RecommendationAdherenceNotComputableError(
            "Recommendation adherence requires both recommended and decided shares."
        )
    l1 = l1_share_distance(candidate=decided, baseline=recommended)
    max_abs = max_absolute_line_movement(candidate=decided, baseline=recommended)
    added, removed = channel_set_changes(recommended=recommended, decided=decided)
    percent = max_percentage_line_deviation(recommended=recommended, decided=decided)
    adherence = (
        AdherenceClass.MATCH
        if l1 == 0.0 and not added and not removed
        else AdherenceClass.MODIFIED
    )
    created = datetime.now(UTC)
    payload = {
        "decision": investment_decision_ref,
        "l1": l1,
        "max_abs": max_abs,
        "added": list(added),
        "removed": list(removed),
    }
    return RecommendationAdherence(
        recommendation_adherence_id=new_recommendation_adherence_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        investment_decision_ref=investment_decision_ref,
        recommended_portfolio_ref=recommended_portfolio_ref,
        decided_portfolio_ref=decided_portfolio_ref,
        l1_distance=l1,
        max_absolute_line_deviation=max_abs,
        max_percentage_deviation=percent,
        channels_added=added,
        channels_removed=removed,
        adherence_class=adherence,
        fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )

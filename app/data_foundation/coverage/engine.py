"""Deterministic monthly coverage. Missing is never treated as zero."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Iterable

import pandas as pd

from app.data_foundation.contracts import (
    CoverageAssessment,
    CoverageBucket,
    CoverageGap,
    CoverageSeries,
    CoverageSummary,
    EvidenceRequirement,
    MeasurementCycle,
    SourceBinding,
    SourceContinuityPlan,
)
from app.data_foundation.enums import (
    CoverageBucketState,
    CoverageGapCategory,
    CoverageView,
    EvidenceRequirementType,
)
from app.data_foundation.ids import new_gap_id, new_requirement_id


def month_range(start: str, end: str) -> list[str]:
    begin = date.fromisoformat(start[:10]).replace(day=1)
    finish = date.fromisoformat(end[:10]).replace(day=1)
    months: list[str] = []
    cursor = begin
    while cursor <= finish:
        months.append(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def _channel_expected(active_from: str | None, active_to: str | None, period: str) -> bool:
    if active_from and period < active_from[:7]:
        return False
    if active_to and period > active_to[:7]:
        return False
    return True


def _observed_months(frame: pd.DataFrame, date_field: str | None) -> dict[str, dict[str, float]]:
    if frame.empty or not date_field or date_field not in frame.columns:
        return {}
    parsed = frame.copy()
    parsed["_period"] = pd.to_datetime(parsed[date_field], errors="coerce").dt.strftime("%Y-%m")
    parsed = parsed.dropna(subset=["_period"])
    spend_col = next((name for name in ("spend", "revenue", "value") if name in parsed.columns), None)
    out: dict[str, dict[str, float]] = {}
    for period, group in parsed.groupby("_period"):
        spend = float(group[spend_col].sum()) if spend_col else float(len(group))
        out[str(period)] = {"rows": float(len(group)), "spend": spend}
    return out


def _span(periods: list[str]) -> str | None:
    if not periods:
        return None
    return f"{periods[0]}/{periods[-1]}"


def _longest_run(periods: Iterable[str], universe: list[str]) -> list[str]:
    wanted = set(periods)
    best: list[str] = []
    current: list[str] = []
    for month in universe:
        if month in wanted:
            current.append(month)
            if len(current) > len(best):
                best = list(current)
        else:
            current = []
    return best


def _longest_gap(expected: list[str], present: set[str]) -> str | None:
    gap: list[str] = []
    best: list[str] = []
    for month in expected:
        if month not in present:
            gap.append(month)
            if len(gap) > len(best):
                best = list(gap)
        else:
            gap = []
    return _span(best)


def assess_coverage(
    *,
    tenant_id: str,
    workspace_id: str,
    cycle: MeasurementCycle,
    requirements: tuple[EvidenceRequirement, ...],
    bindings: list[SourceBinding],
    frames: dict[str, pd.DataFrame],
    channel_dates: dict[str, tuple[str | None, str | None]],
    view: CoverageView,
    transitions: list[SourceContinuityPlan] | None = None,
) -> CoverageAssessment:
    start = cycle.target_window_start or cycle.data_cutoff or "2026-01-01"
    end = cycle.target_window_end or cycle.data_cutoff or start
    universe = month_range(start, end)
    binding_by_req = {item.requirement_id: item for item in bindings if item.requirement_id}
    series_rows: list[CoverageSeries] = []
    gaps: list[CoverageGap] = []
    continuous_sets: list[set[str]] = []
    limiting: str | None = None
    limiting_len = None
    meeting = 0
    issues = 0

    selected = requirements
    if view is CoverageView.ALL_SOURCES:
        known = {row.requirement_id for row in requirements}
        extra = [
            EvidenceRequirement(
                requirement_id=item.source_id,
                requirement_type=EvidenceRequirementType.OTHER_CUSTOM,
                concept=item.source_id,
                business_role="source",
                expected_category="source",
                downstream_use=(),
            )
            for item in bindings
            if item.requirement_id not in known
        ]
        selected = requirements + tuple(extra)

    for requirement in selected:
        binding = binding_by_req.get(requirement.requirement_id)
        dates = channel_dates.get(requirement.channel_id or requirement.concept, (None, None))
        observed = _observed_months(frames.get(binding.source_id, pd.DataFrame()), binding.contract.date_field) if binding else {}
        buckets: list[CoverageBucket] = []
        present_expected: list[str] = []
        for period in universe:
            expected = _channel_expected(dates[0], dates[1], period)
            seen = period in observed
            spend = observed.get(period, {}).get("spend", 0.0)
            valid_zero = seen and spend == 0.0
            overlap = _overlap_unreconciled(binding, period, transitions or [])
            if overlap:
                state = CoverageBucketState.OVERLAP_UNDER_RECONCILIATION
            elif not expected:
                state = CoverageBucketState.NOT_EXPECTED
            elif binding is None:
                state = CoverageBucketState.SOURCE_NOT_FOUND
            elif valid_zero:
                state = CoverageBucketState.VALID_ZERO
            elif seen:
                state = CoverageBucketState.VERIFIED_PRESENT
            else:
                state = CoverageBucketState.EXPECTED_BUT_MISSING
                issues += 1
                gaps.append(
                    CoverageGap(
                        gap_id=new_gap_id(),
                        category=CoverageGapCategory.COVERAGE_GAP,
                        period=period,
                        requirement_id=requirement.requirement_id,
                        expected_business_state="ACTIVE",
                        observed_data_state="MISSING",
                        source_health="EXPECTED_BUT_MISSING",
                        evidence_refs=(requirement.requirement_id,),
                        recommended_next_action="clarify_or_locate_source",
                    )
                )
            if expected and seen:
                present_expected.append(period)
            buckets.append(
                CoverageBucket(
                    period=period,
                    state=state,
                    expected=expected,
                    observed=seen,
                    valid_zero=valid_zero,
                    source_ids=(binding.source_id,) if binding else (),
                )
            )
        expected_months = [item.period for item in buckets if item.expected]
        present = {item.period for item in buckets if item.observed and item.expected}
        run = _longest_run(present, expected_months or universe)
        continuous_sets.append(set(run))
        if expected_months and set(expected_months) <= present:
            meeting += 1
        if limiting_len is None or len(run) < limiting_len:
            limiting_len = len(run)
            limiting = requirement.concept
        series_rows.append(
            CoverageSeries(
                series_id=requirement.requirement_id or new_requirement_id(),
                requirement_id=requirement.requirement_id,
                source_id=binding.source_id if binding else None,
                concept=requirement.concept,
                buckets=tuple(buckets),
                observed_span=_span(sorted(present)),
                continuous_span=_span(run),
                most_recent_continuous_span=_span(run),
                longest_gap=_longest_gap(expected_months, present),
                latest_observed_period=sorted(present)[-1] if present else None,
            )
        )
        del present_expected

    shared = set(universe)
    for item in continuous_sets:
        shared &= item
    shared_sorted = sorted(shared)
    summary = CoverageSummary(
        required_sources_meeting_target=meeting,
        continuity_issue_count=issues,
        shared_continuous_window=_span(shared_sorted),
        shared_continuous_window_start=shared_sorted[0] if shared_sorted else None,
        shared_continuous_window_end=shared_sorted[-1] if shared_sorted else None,
        most_limiting_requirement=limiting,
        target_window_coverage=_span(universe),
    )
    return CoverageAssessment(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        cycle_id=cycle.cycle_id,
        view=view,
        series=tuple(series_rows),
        gaps=tuple(gaps),
        summary=summary,
        assessed_at=datetime.now(UTC),
    )


def _overlap_unreconciled(
    binding: SourceBinding | None,
    period: str,
    transitions: list[SourceContinuityPlan],
) -> bool:
    if binding is None:
        return False
    for plan in transitions:
        if not plan.reconciliation_required:
            continue
        if binding.source_id in {plan.historical_source_id, plan.ongoing_source_id}:
            if plan.cutoff and period[:7] == plan.cutoff[:7]:
                return True
    return False

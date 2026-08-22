"""Temporal integrity. UNKNOWN/MISSING is never synthesized as zero."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from app.data_foundation.contracts import QualityCheckResult
from app.data_foundation.enums import ConsequenceClass, PeriodStatus, QualityFamily, QualityStatus
from app.data_foundation.quality.checks import _result


def check_missing_periods(
    frame: pd.DataFrame,
    *,
    source_id: str,
    date_field: str,
    expected_start: str,
    expected_end: str,
    freq: str = "D",
) -> QualityCheckResult:
    if date_field not in frame.columns:
        return _result(
            check_id="DF-Q-TEMPORAL-GAP",
            family=QualityFamily.TEMPORAL,
            status=QualityStatus.UNKNOWN,
            consequence=ConsequenceClass.SOURCE_BLOCKER,
            source_id=source_id,
            field_ids=(date_field,),
        )
    observed = pd.to_datetime(frame[date_field], errors="coerce").dropna().dt.strftime("%Y-%m-%d")
    expected = pd.date_range(expected_start, expected_end, freq=freq).strftime("%Y-%m-%d")
    missing = sorted(set(expected) - set(observed))
    return _result(
        check_id="DF-Q-TEMPORAL-GAP",
        family=QualityFamily.TEMPORAL,
        status=QualityStatus.BLOCKER if missing else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if missing else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(date_field,),
        observed_count=len(missing),
        evidence={
            "missing_periods": missing,
            "period_status": PeriodStatus.UNKNOWN_MISSING.value,
            "synthesized_zero": False,
        },
    )


def check_overlapping_periods(
    periods: list[tuple[str, str]], *, source_id: str
) -> QualityCheckResult:
    overlaps = 0
    ordered = sorted(periods)
    for index in range(1, len(ordered)):
        prev_end = ordered[index - 1][1]
        start = ordered[index][0]
        if start <= prev_end:
            overlaps += 1
    return _result(
        check_id="DF-Q-TEMPORAL-OVERLAP",
        family=QualityFamily.TEMPORAL,
        status=QualityStatus.REVIEW if overlaps else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if overlaps else ConsequenceClass.ADVISORY,
        source_id=source_id,
        observed_count=overlaps,
    )


def check_future_dates(
    frame: pd.DataFrame, *, source_id: str, date_field: str, as_of: datetime | None = None
) -> QualityCheckResult:
    now = as_of or datetime.now(UTC)
    parsed = pd.to_datetime(frame[date_field], errors="coerce")
    future = int((parsed > pd.Timestamp(now.date())).sum())
    return _result(
        check_id="DF-Q-TEMPORAL-FUTURE",
        family=QualityFamily.TEMPORAL,
        status=QualityStatus.REVIEW if future else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if future else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(date_field,),
        observed_count=future,
    )


def check_stale_source(
    *,
    source_id: str,
    latest_expected: str,
    latest_observed: str | None,
    max_lag_days: int = 2,
    as_of: datetime | None = None,
) -> QualityCheckResult:
    now = as_of or datetime.now(UTC)
    expected = datetime.strptime(latest_expected, "%Y-%m-%d").date()
    if latest_observed is None:
        return _result(
            check_id="DF-Q-TEMPORAL-STALE",
            family=QualityFamily.TEMPORAL,
            status=QualityStatus.BLOCKER,
            consequence=ConsequenceClass.SOURCE_BLOCKER,
            source_id=source_id,
            evidence={
                "freshness_unknown": True,
                "missing_is_not_zero": True,
                "latest_expected": latest_expected,
            },
        )
    observed = datetime.strptime(latest_observed, "%Y-%m-%d").date()
    stale = (now.date() - observed) > timedelta(days=max_lag_days) or observed < expected
    return _result(
        check_id="DF-Q-TEMPORAL-STALE",
        family=QualityFamily.TEMPORAL,
        status=QualityStatus.BLOCKER if stale else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if stale else ConsequenceClass.ADVISORY,
        source_id=source_id,
        evidence={
            "latest_expected": latest_expected,
            "latest_observed": latest_observed,
            "missing_is_not_zero": True,
            "synthesized_zero": False,
        },
    )


def refuse_zero_fill_missing(missing_periods: list[str]) -> None:
    if missing_periods:
        raise ValueError("MISSING != ZERO: unknown periods cannot be filled with zero media.")

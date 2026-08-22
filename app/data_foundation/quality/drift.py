"""Drift against a persisted baseline. Ongoing operational evidence."""

from __future__ import annotations

from app.data_foundation.contracts import QualityCheckResult
from app.data_foundation.enums import ConsequenceClass, QualityFamily, QualityStatus
from app.data_foundation.quality.checks import _result


def check_schema_drift(
    *,
    source_id: str,
    baseline_fingerprint: str,
    current_fingerprint: str,
) -> QualityCheckResult:
    changed = baseline_fingerprint != current_fingerprint
    return _result(
        check_id="DF-Q-DRIFT-SCHEMA",
        family=QualityFamily.DRIFT,
        status=QualityStatus.REVIEW if changed else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if changed else ConsequenceClass.ADVISORY,
        source_id=source_id,
        evidence={"baseline": baseline_fingerprint, "current": current_fingerprint},
    )


def check_null_rate_drift(
    *,
    source_id: str,
    field: str,
    baseline_rate: float,
    current_rate: float,
    threshold: float = 0.1,
) -> QualityCheckResult:
    delta = abs(current_rate - baseline_rate)
    drifted = delta > threshold
    return _result(
        check_id="DF-Q-DRIFT-NULL-RATE",
        family=QualityFamily.DRIFT,
        status=QualityStatus.REVIEW if drifted else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if drifted else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_rate=delta,
        evidence={"baseline_rate": baseline_rate, "current_rate": current_rate},
    )


def check_row_volume_drift(
    *,
    source_id: str,
    baseline_rows: int,
    current_rows: int,
    collapse_ratio: float = 0.5,
    spike_ratio: float = 2.0,
) -> QualityCheckResult:
    if baseline_rows <= 0:
        return _result(
            check_id="DF-Q-DRIFT-VOLUME",
            family=QualityFamily.DRIFT,
            status=QualityStatus.UNKNOWN,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
        )
    ratio = current_rows / baseline_rows
    drifted = ratio < collapse_ratio or ratio > spike_ratio
    return _result(
        check_id="DF-Q-DRIFT-VOLUME",
        family=QualityFamily.DRIFT,
        status=QualityStatus.BLOCKER
        if ratio < collapse_ratio
        else (QualityStatus.REVIEW if drifted else QualityStatus.PASS),
        consequence=ConsequenceClass.SOURCE_BLOCKER
        if ratio < collapse_ratio
        else ConsequenceClass.PREMODEL_REVIEW
        if drifted
        else ConsequenceClass.ADVISORY,
        source_id=source_id,
        observed_count=current_rows,
        evidence={"baseline_rows": baseline_rows, "ratio": ratio},
    )


def check_category_drift(
    *,
    source_id: str,
    field: str,
    baseline: set[str],
    current: set[str],
) -> QualityCheckResult:
    added = sorted(current - baseline)
    removed = sorted(baseline - current)
    drifted = bool(added or removed)
    return _result(
        check_id="DF-Q-DRIFT-CATEGORY",
        family=QualityFamily.DRIFT,
        status=QualityStatus.REVIEW if drifted else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if drifted else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        evidence={"added": added, "removed": removed},
    )

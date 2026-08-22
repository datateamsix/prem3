"""Reconciliation only when an explicit control exists."""

from __future__ import annotations

from app.data_foundation.contracts import QualityCheckResult
from app.data_foundation.enums import ConsequenceClass, QualityFamily, QualityStatus
from app.data_foundation.quality.checks import _result


def check_control_total(
    *,
    source_id: str,
    source_total: float,
    control_total: float | None,
    tolerance: float,
    control_name: str,
) -> QualityCheckResult:
    if control_total is None:
        return _result(
            check_id="DF-Q-RECON-CONTROL",
            family=QualityFamily.RECONCILIATION,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            evidence={"reason": "no_control", "control_name": control_name},
        )
    delta = abs(source_total - control_total)
    ok = delta <= tolerance
    return _result(
        check_id="DF-Q-RECON-CONTROL",
        family=QualityFamily.RECONCILIATION,
        status=QualityStatus.PASS if ok else QualityStatus.BLOCKER,
        consequence=ConsequenceClass.ADVISORY if ok else ConsequenceClass.SOURCE_BLOCKER,
        source_id=source_id,
        observed_count=int(delta),
        evidence={
            "source_total": source_total,
            "control_total": control_total,
            "tolerance": tolerance,
            "control_name": control_name,
        },
    )


def check_referential_orphans(
    *,
    source_id: str,
    child_keys: list[str],
    parent_keys: list[str],
) -> QualityCheckResult:
    parents = set(parent_keys)
    orphans = [key for key in child_keys if key not in parents]
    return _result(
        check_id="DF-Q-REFERENTIAL-ORPHAN",
        family=QualityFamily.REFERENTIAL,
        status=QualityStatus.REVIEW if orphans else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if orphans else ConsequenceClass.ADVISORY,
        source_id=source_id,
        observed_count=len(orphans),
        evidence={"orphan_count": len(orphans)},
    )

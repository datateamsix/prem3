"""Compose quality families into a source assessment."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from app.data_foundation.contracts import (
    ContractStructureAssessment,
    DataQualityAssessment,
    MeasurementCoverageAssessment,
    OperationalHealthAssessment,
    QualityFinding,
    QualityOverview,
    SourceAssessment,
    SourceContract,
)
from app.data_foundation.enums import (
    ConnectionLifecycle,
    ConsequenceClass,
    PeriodStatus,
    QualityStatus,
)
from app.data_foundation.ids import new_finding_id
from app.data_foundation.quality import checks, temporal
from app.tools.fingerprints import schema_signature


def _worst(statuses: list[QualityStatus]) -> QualityStatus:
    order = {
        QualityStatus.BLOCKER: 4,
        QualityStatus.UNKNOWN: 3,
        QualityStatus.REVIEW: 2,
        QualityStatus.PASS: 1,
        QualityStatus.SKIPPED_NOT_APPLICABLE: 0,
    }
    return max(statuses, key=lambda item: order[item], default=QualityStatus.UNKNOWN)


def assess_frame(
    frame: pd.DataFrame,
    *,
    source_id: str,
    contract: SourceContract,
    access_works: bool,
    authorization: ConnectionLifecycle,
    freshness_known: bool,
    latest_expected: str | None = None,
    latest_observed: str | None = None,
    expected_start: str | None = None,
    expected_end: str | None = None,
    registry_version: str,
) -> SourceAssessment:
    quality_rows = [
        checks.check_exact_duplicates(frame, source_id=source_id),
        checks.check_empty_columns(frame, source_id=source_id),
    ]
    if contract.unique_keys:
        quality_rows.append(
            checks.check_key_duplicates(frame, source_id=source_id, keys=list(contract.unique_keys))
        )
    for field in contract.required_fields:
        quality_rows.append(
            checks.check_nulls(frame, source_id=source_id, field=field, required=True)
        )
        quality_rows.append(checks.check_blanks(frame, source_id=source_id, field=field))
    if contract.date_field and contract.date_format:
        quality_rows.append(
            checks.check_date_parse(
                frame,
                source_id=source_id,
                field=contract.date_field,
                expected_format=contract.date_format,
            )
        )
        quality_rows.append(
            checks.check_mixed_dates(frame, source_id=source_id, field=contract.date_field)
        )
        quality_rows.append(
            temporal.check_future_dates(frame, source_id=source_id, date_field=contract.date_field)
        )
    spend_fields = [name for name in ("spend", "cost", "revenue") if name in frame.columns]
    for field in spend_fields:
        quality_rows.append(checks.check_numeric_parse(frame, source_id=source_id, field=field))
        quality_rows.append(checks.check_negative_spend(frame, source_id=source_id, field=field))
        quality_rows.append(
            checks.check_zero_is_not_missing(frame, source_id=source_id, field=field)
        )
    if expected_start and expected_end and contract.date_field:
        quality_rows.append(
            temporal.check_missing_periods(
                frame,
                source_id=source_id,
                date_field=contract.date_field,
                expected_start=expected_start,
                expected_end=expected_end,
            )
        )
    if latest_expected is not None:
        quality_rows.append(
            temporal.check_stale_source(
                source_id=source_id,
                latest_expected=latest_expected,
                latest_observed=latest_observed,
            )
        )

    present = set(map(str, frame.columns))
    missing = tuple(field for field in contract.required_fields if field not in present)
    schema_fp = str(schema_signature(frame))
    observed_grain = contract.grain
    contract_status = QualityStatus.BLOCKER if missing else QualityStatus.PASS
    op = OperationalHealthAssessment(
        access_works=access_works,
        authorization_state=authorization,
        freshness_known=freshness_known,
        last_successful_load=latest_observed,
        status=QualityStatus.PASS
        if access_works and freshness_known
        else QualityStatus.BLOCKER
        if not access_works or not freshness_known
        else QualityStatus.REVIEW,
    )
    structure = ContractStructureAssessment(
        required_fields_present=not missing,
        missing_fields=missing,
        expected_grain=contract.grain,
        observed_grain=observed_grain,
        schema_fingerprint=schema_fp,
        currency_known=bool(contract.currency),
        timezone_known=bool(contract.timezone),
        status=contract_status
        if contract.currency and contract.timezone
        else (QualityStatus.BLOCKER if missing else QualityStatus.REVIEW),
    )
    missing_periods: tuple[str, ...] = ()
    for item in quality_rows:
        if item.check_id == "DF-Q-TEMPORAL-GAP":
            missing_periods = tuple(item.evidence.get("missing_periods", []))
    coverage = MeasurementCoverageAssessment(
        history_periods=int(len(frame)),
        missing_periods=missing_periods,
        period_statuses=tuple((period, PeriodStatus.UNKNOWN_MISSING) for period in missing_periods),
        status=QualityStatus.BLOCKER if missing_periods else QualityStatus.PASS,
    )
    quality_status = _worst([item.status for item in quality_rows])
    overall = _worst([op.status, structure.status, quality_status, coverage.status])
    return SourceAssessment(
        source_id=source_id,
        registry_version=registry_version,
        operational=op,
        contract=structure,
        quality=DataQualityAssessment(checks=tuple(quality_rows), status=quality_status),
        coverage=coverage,
        overall_status=overall,
        assessed_at=datetime.now(UTC),
    )


def overview_from_assessment(assessment: SourceAssessment) -> QualityOverview:
    findings: list[QualityFinding] = []
    blockers = reviews = advisories = passes = 0
    for check in assessment.quality.checks:
        if check.status is QualityStatus.BLOCKER:
            blockers += 1
        elif check.status is QualityStatus.REVIEW:
            reviews += 1
        elif check.status is QualityStatus.PASS:
            passes += 1
        else:
            advisories += 1
        if check.status in {QualityStatus.BLOCKER, QualityStatus.REVIEW, QualityStatus.UNKNOWN}:
            findings.append(
                QualityFinding(
                    finding_id=new_finding_id(),
                    source_id=assessment.source_id,
                    check_id=check.check_id,
                    status=check.status,
                    consequence=check.consequence,
                    observed_fact=(
                        f"{check.check_id} status={check.status.value} count={check.observed_count}"
                    ),
                    agent_interpretation=None,
                    field_ids=check.field_ids,
                )
            )
    return QualityOverview(
        source_id=assessment.source_id,
        blocker_count=blockers,
        review_count=reviews,
        advisory_count=advisories,
        pass_count=passes,
        findings=tuple(findings),
    )


def has_source_blocker(assessment: SourceAssessment) -> bool:
    if assessment.overall_status is QualityStatus.BLOCKER:
        return True
    return any(
        item.consequence is ConsequenceClass.SOURCE_BLOCKER and item.status is QualityStatus.BLOCKER
        for item in assessment.quality.checks
    )

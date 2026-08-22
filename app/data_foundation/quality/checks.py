"""P0 quality families. Results are structured evidence, never prose-only."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from app.data_foundation.contracts import QualityCheckResult
from app.data_foundation.enums import ConsequenceClass, QualityFamily, QualityStatus
from app.tools.profiling import detect_duplicates, profile_dataframe


def _now() -> datetime:
    return datetime.now(UTC)


def _result(
    *,
    check_id: str,
    family: QualityFamily,
    status: QualityStatus,
    consequence: ConsequenceClass,
    source_id: str,
    field_ids: tuple[str, ...] = (),
    observed_count: int | None = None,
    observed_rate: float | None = None,
    evidence: dict | None = None,
) -> QualityCheckResult:
    return QualityCheckResult(
        check_id=check_id,
        check_family=family,
        status=status,
        severity=consequence,
        consequence=consequence,
        source_id=source_id,
        field_ids=field_ids,
        observed_count=observed_count,
        observed_rate=observed_rate,
        evidence=evidence or {},
        executed_at=_now(),
    )


def check_exact_duplicates(frame: pd.DataFrame, *, source_id: str) -> QualityCheckResult:
    profile = profile_dataframe(frame)
    excess = int(profile["excess_rows"])
    return _result(
        check_id="DF-Q-UNIQUENESS-EXACT",
        family=QualityFamily.UNIQUENESS,
        status=QualityStatus.BLOCKER if excess else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if excess else ConsequenceClass.ADVISORY,
        source_id=source_id,
        observed_count=excess,
        evidence={"duplicate_groups": profile["duplicate_groups"]},
    )


def check_key_duplicates(
    frame: pd.DataFrame, *, source_id: str, keys: list[str]
) -> QualityCheckResult:
    missing = [column for column in keys if column not in frame.columns]
    if missing:
        return _result(
            check_id="DF-Q-UNIQUENESS-KEY",
            family=QualityFamily.UNIQUENESS,
            status=QualityStatus.UNKNOWN,
            consequence=ConsequenceClass.SOURCE_BLOCKER,
            source_id=source_id,
            field_ids=tuple(keys),
            evidence={"missing_keys": missing},
        )
    detected = detect_duplicates(frame, keys)
    excess = int(detected["excess_rows"])
    return _result(
        check_id="DF-Q-UNIQUENESS-KEY",
        family=QualityFamily.UNIQUENESS,
        status=QualityStatus.BLOCKER if excess else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if excess else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=tuple(keys),
        observed_count=excess,
        evidence={"duplicate_groups": detected["duplicate_groups"]},
    )


def check_file_fingerprint_duplicates(
    fingerprints: list[str], *, source_id: str
) -> QualityCheckResult:
    unique = set(fingerprints)
    dupes = len(fingerprints) - len(unique)
    return _result(
        check_id="DF-Q-UNIQUENESS-FILE",
        family=QualityFamily.UNIQUENESS,
        status=QualityStatus.BLOCKER if dupes else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if dupes else ConsequenceClass.ADVISORY,
        source_id=source_id,
        observed_count=dupes,
    )


def check_nulls(
    frame: pd.DataFrame, *, source_id: str, field: str, required: bool = False
) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-COMPLETENESS-NULL",
            family=QualityFamily.COMPLETENESS,
            status=QualityStatus.UNKNOWN,
            consequence=ConsequenceClass.SOURCE_BLOCKER if required else ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    nulls = int(frame[field].isna().sum())
    rate = float(nulls / len(frame)) if len(frame) else 0.0
    status = QualityStatus.PASS
    consequence = ConsequenceClass.ADVISORY
    if required and nulls:
        status = QualityStatus.BLOCKER
        consequence = ConsequenceClass.SOURCE_BLOCKER
    elif nulls:
        status = QualityStatus.REVIEW
        consequence = ConsequenceClass.PREMODEL_REVIEW
    return _result(
        check_id="DF-Q-COMPLETENESS-NULL",
        family=QualityFamily.COMPLETENESS,
        status=status,
        consequence=consequence,
        source_id=source_id,
        field_ids=(field,),
        observed_count=nulls,
        observed_rate=rate,
    )


def check_blanks(frame: pd.DataFrame, *, source_id: str, field: str) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-COMPLETENESS-BLANK",
            family=QualityFamily.COMPLETENESS,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    series = frame[field].astype("string")
    blanks = int((series.str.strip() == "").sum())
    return _result(
        check_id="DF-Q-COMPLETENESS-BLANK",
        family=QualityFamily.COMPLETENESS,
        status=QualityStatus.REVIEW if blanks else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if blanks else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=blanks,
        evidence={"blank_is_not_null": True, "blank_is_not_zero": True},
    )


def check_empty_columns(frame: pd.DataFrame, *, source_id: str) -> QualityCheckResult:
    empty = [str(column) for column in frame.columns if frame[column].isna().all()]
    return _result(
        check_id="DF-Q-COMPLETENESS-EMPTY-COLUMN",
        family=QualityFamily.COMPLETENESS,
        status=QualityStatus.REVIEW if empty else QualityStatus.PASS,
        consequence=ConsequenceClass.PREMODEL_REVIEW if empty else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=tuple(empty),
        observed_count=len(empty),
    )


def check_date_parse(
    frame: pd.DataFrame, *, source_id: str, field: str, expected_format: str
) -> QualityCheckResult:
    from app.tools.safety import resolve_date_format

    if field not in frame.columns:
        return _result(
            check_id="DF-Q-TYPE-DATE",
            family=QualityFamily.TYPE_PARSE,
            status=QualityStatus.UNKNOWN,
            consequence=ConsequenceClass.SOURCE_BLOCKER,
            source_id=source_id,
            field_ids=(field,),
        )
    fmt = resolve_date_format(expected_format)
    parsed = pd.to_datetime(frame[field], format=fmt, errors="coerce")
    invalid = int(parsed.isna().sum())
    return _result(
        check_id="DF-Q-TYPE-DATE",
        family=QualityFamily.TYPE_PARSE,
        status=QualityStatus.BLOCKER if invalid else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if invalid else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=invalid,
        evidence={"expected_format": expected_format},
    )


def check_mixed_dates(frame: pd.DataFrame, *, source_id: str, field: str) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-TYPE-MIXED-DATE",
            family=QualityFamily.TYPE_PARSE,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    values = frame[field].astype("string").dropna()
    iso = int(values.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False).sum())
    us = int(values.str.match(r"^\d{1,2}/\d{1,2}/\d{4}$", na=False).sum())
    mixed = iso > 0 and us > 0
    return _result(
        check_id="DF-Q-TYPE-MIXED-DATE",
        family=QualityFamily.TYPE_PARSE,
        status=QualityStatus.BLOCKER if mixed else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if mixed else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        evidence={"iso_count": iso, "us_count": us},
    )


def check_numeric_parse(frame: pd.DataFrame, *, source_id: str, field: str) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-TYPE-NUMERIC",
            family=QualityFamily.TYPE_PARSE,
            status=QualityStatus.UNKNOWN,
            consequence=ConsequenceClass.SOURCE_BLOCKER,
            source_id=source_id,
            field_ids=(field,),
        )
    cleaned = frame[field].astype("string").str.replace(r"[$,%]", "", regex=True).str.strip()
    parsed = pd.to_numeric(cleaned, errors="coerce")
    invalid = int(parsed.isna().sum() - frame[field].isna().sum())
    return _result(
        check_id="DF-Q-TYPE-NUMERIC",
        family=QualityFamily.TYPE_PARSE,
        status=QualityStatus.BLOCKER if invalid else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if invalid else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=max(invalid, 0),
    )


def check_whitespace(frame: pd.DataFrame, *, source_id: str, field: str) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-FORMAT-WHITESPACE",
            family=QualityFamily.FORMATTING,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    series = frame[field].astype("string")
    dirty = int((series != series.str.strip()).sum())
    return _result(
        check_id="DF-Q-FORMAT-WHITESPACE",
        family=QualityFamily.FORMATTING,
        status=QualityStatus.REVIEW if dirty else QualityStatus.PASS,
        consequence=ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=dirty,
    )


def check_case_variants(frame: pd.DataFrame, *, source_id: str, field: str) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-FORMAT-CASE",
            family=QualityFamily.FORMATTING,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    values = frame[field].astype("string").dropna()
    variants = int(values.nunique() - values.str.lower().nunique())
    return _result(
        check_id="DF-Q-FORMAT-CASE",
        family=QualityFamily.FORMATTING,
        status=QualityStatus.REVIEW if variants else QualityStatus.PASS,
        consequence=ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=max(variants, 0),
    )


def check_negative_spend(frame: pd.DataFrame, *, source_id: str, field: str) -> QualityCheckResult:
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-DOMAIN-NEG-SPEND",
            family=QualityFamily.DOMAIN,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    numeric = pd.to_numeric(frame[field], errors="coerce")
    negatives = int((numeric < 0).sum())
    return _result(
        check_id="DF-Q-DOMAIN-NEG-SPEND",
        family=QualityFamily.DOMAIN,
        status=QualityStatus.BLOCKER if negatives else QualityStatus.PASS,
        consequence=ConsequenceClass.SOURCE_BLOCKER if negatives else ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=negatives,
    )


def check_zero_is_not_missing(
    frame: pd.DataFrame, *, source_id: str, field: str
) -> QualityCheckResult:
    """Zeros are observed zeros. They must not be invented for absent periods."""
    if field not in frame.columns:
        return _result(
            check_id="DF-Q-DOMAIN-ZERO-SEMANTICS",
            family=QualityFamily.DOMAIN,
            status=QualityStatus.SKIPPED_NOT_APPLICABLE,
            consequence=ConsequenceClass.ADVISORY,
            source_id=source_id,
            field_ids=(field,),
        )
    numeric = pd.to_numeric(frame[field], errors="coerce")
    zeros = int((numeric == 0).sum())
    return _result(
        check_id="DF-Q-DOMAIN-ZERO-SEMANTICS",
        family=QualityFamily.DOMAIN,
        status=QualityStatus.PASS,
        consequence=ConsequenceClass.ADVISORY,
        source_id=source_id,
        field_ids=(field,),
        observed_count=zeros,
        evidence={"zero_is_not_missing": True, "missing_is_not_zero": True},
    )

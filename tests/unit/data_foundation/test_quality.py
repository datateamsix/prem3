import pandas as pd

from app.data_foundation.enums import QualityStatus
from app.data_foundation.quality import checks, drift, reconciliation
from app.data_foundation.quality.temporal import check_missing_periods, refuse_zero_fill_missing


def test_exact_duplicates_pass_fail_boundary() -> None:
    clean = pd.DataFrame({"date": ["2026-01-01"], "spend": [1]})
    duped = pd.DataFrame({"date": ["2026-01-01", "2026-01-01"], "spend": [1, 1]})
    assert checks.check_exact_duplicates(clean, source_id="s").status is QualityStatus.PASS
    assert checks.check_exact_duplicates(duped, source_id="s").status is QualityStatus.BLOCKER


def test_key_duplicates() -> None:
    frame = pd.DataFrame(
        {"date": ["2026-01-01", "2026-01-01"], "channel": ["A", "A"], "spend": [1, 2]}
    )
    result = checks.check_key_duplicates(frame, source_id="s", keys=["date", "channel"])
    assert result.status is QualityStatus.BLOCKER


def test_nulls_blanks_empty_distinct() -> None:
    frame = pd.DataFrame({"kpi": [1.0, None], "label": ["a", ""], "empty": [None, None]})
    required = checks.check_nulls(frame, source_id="s", field="kpi", required=True)
    blank = checks.check_blanks(frame, source_id="s", field="label")
    empty = checks.check_empty_columns(frame, source_id="s")
    assert required.status is QualityStatus.BLOCKER
    assert blank.status is QualityStatus.REVIEW
    assert blank.evidence["blank_is_not_null"] is True
    assert empty.status is QualityStatus.REVIEW


def test_date_and_numeric_parse() -> None:
    good = pd.DataFrame({"date": ["2026-01-01"], "spend": ["$10.00"]})
    bad_date = pd.DataFrame({"date": ["01/01/2026"]})
    mixed = pd.DataFrame({"date": ["2026-01-01", "01/02/2026"]})
    bad_num = pd.DataFrame({"spend": ["n/a"]})
    assert (
        checks.check_date_parse(
            good, source_id="s", field="date", expected_format="YYYY-MM-DD"
        ).status
        is QualityStatus.PASS
    )
    assert (
        checks.check_date_parse(
            bad_date, source_id="s", field="date", expected_format="YYYY-MM-DD"
        ).status
        is QualityStatus.BLOCKER
    )
    assert (
        checks.check_mixed_dates(mixed, source_id="s", field="date").status is QualityStatus.BLOCKER
    )
    assert (
        checks.check_numeric_parse(good, source_id="s", field="spend").status is QualityStatus.PASS
    )
    assert (
        checks.check_numeric_parse(bad_num, source_id="s", field="spend").status
        is QualityStatus.BLOCKER
    )


def test_formatting_and_domain() -> None:
    frame = pd.DataFrame(
        {
            "channel": [" Search", "Search", "search"],
            "spend": [1.0, -2.0, 3.0],
            "impressions": [0, 1, 2],
        }
    )
    assert (
        checks.check_whitespace(frame, source_id="s", field="channel").status
        is QualityStatus.REVIEW
    )
    assert (
        checks.check_case_variants(frame, source_id="s", field="channel").status
        is QualityStatus.REVIEW
    )
    assert (
        checks.check_negative_spend(frame, source_id="s", field="spend").status
        is QualityStatus.BLOCKER
    )
    zero = checks.check_zero_is_not_missing(frame, source_id="s", field="impressions")
    assert zero.evidence["missing_is_not_zero"] is True


def test_temporal_gap_is_not_zero() -> None:
    frame = pd.DataFrame({"date": ["2026-01-01", "2026-01-03"], "spend": [10.0, 12.0]})
    result = check_missing_periods(
        frame,
        source_id="s",
        date_field="date",
        expected_start="2026-01-01",
        expected_end="2026-01-03",
    )
    assert result.status is QualityStatus.BLOCKER
    assert result.evidence["synthesized_zero"] is False
    assert "2026-01-02" in result.evidence["missing_periods"]
    try:
        refuse_zero_fill_missing(["2026-01-02"])
    except ValueError as exc:
        assert "MISSING != ZERO" in str(exc)
    else:
        raise AssertionError("expected refuse")


def test_drift_and_reconciliation() -> None:
    schema = drift.check_schema_drift(
        source_id="s", baseline_fingerprint="a", current_fingerprint="b"
    )
    volume = drift.check_row_volume_drift(source_id="s", baseline_rows=100, current_rows=10)
    cats = drift.check_category_drift(
        source_id="s", field="channel", baseline={"a"}, current={"a", "b"}
    )
    nulls = drift.check_null_rate_drift(
        source_id="s", field="spend", baseline_rate=0.0, current_rate=0.4
    )
    recon = reconciliation.check_control_total(
        source_id="s",
        source_total=100.0,
        control_total=100.2,
        tolerance=0.5,
        control_name="finance",
    )
    none = reconciliation.check_control_total(
        source_id="s",
        source_total=100.0,
        control_total=None,
        tolerance=0.5,
        control_name="missing",
    )
    orphans = reconciliation.check_referential_orphans(
        source_id="s", child_keys=["c1", "orphan"], parent_keys=["c1"]
    )
    assert schema.status is QualityStatus.REVIEW
    assert volume.status is QualityStatus.BLOCKER
    assert cats.status is QualityStatus.REVIEW
    assert nulls.status is QualityStatus.REVIEW
    assert recon.status is QualityStatus.PASS
    assert none.status is QualityStatus.SKIPPED_NOT_APPLICABLE
    assert orphans.observed_count == 1

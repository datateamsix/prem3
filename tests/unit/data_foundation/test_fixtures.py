from pathlib import Path

import pandas as pd

from app.data_foundation.enums import QualityStatus
from app.data_foundation.quality.checks import check_key_duplicates
from app.data_foundation.quality.temporal import check_overlapping_periods

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "data_foundation"


def test_fixture2_meta_reissue_has_duplicate_business_keys() -> None:
    frame = pd.read_csv(FIXTURES / "fixture2_meta_reissue.csv")
    result = check_key_duplicates(frame, source_id="meta", keys=["date", "campaign_id"])
    assert result.status is QualityStatus.BLOCKER
    latest = frame.sort_values("revision_ts").drop_duplicates(["date", "campaign_id"], keep="last")
    assert len(latest) == 2


def test_fixture3_promotions_need_business_decision() -> None:
    frame = pd.read_csv(FIXTURES / "fixture3_promotions.csv")
    periods = list(zip(frame["start_date"], frame["end_date"], strict=True))
    overlap = check_overlapping_periods(periods, source_id="promo")
    assert overlap.status is QualityStatus.REVIEW
    assert overlap.observed_count >= 1


def test_fixture5_does_not_invent_zero_rows() -> None:
    frame = pd.read_csv(FIXTURES / "fixture5_missing_vs_zero.csv")
    assert "2026-01-03" not in set(frame["date"].astype(str))
    assert 0 not in set(frame["spend"].tolist())

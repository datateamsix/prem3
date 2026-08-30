"""P6-08 metric semantics. Metrics stay distinct; no universal quality score."""

from __future__ import annotations

import pytest

from app.investment_planning.errors import ExposureMetricNotComparableError
from app.investment_planning.exposure_metrics import (
    EXPOSURE_METRIC_CATALOG,
    FORBIDDEN_COMPOSITE_METRIC_IDS,
    ExposureMetricDefinition,
    assert_comparable,
    get_metric_definition,
    qualified_impressions_proxy_allowed,
)


def test_viewability_not_same_as_in_target() -> None:
    viewability = get_metric_definition("VIEWABILITY_RATE")
    in_target = get_metric_definition("IN_TARGET_RATE")
    assert viewability.metric_id != in_target.metric_id
    assert viewability.population != in_target.population
    with pytest.raises(ExposureMetricNotComparableError):
        assert_comparable(viewability, in_target, period="FY2027Q1", grain="day")


def test_average_frequency_not_distribution() -> None:
    average = get_metric_definition("AVERAGE_FREQUENCY")
    over_share = get_metric_definition("OVER_FREQUENCY_SHARE")
    assert average.comparability_class != over_share.comparability_class
    with pytest.raises(ExposureMetricNotComparableError):
        assert_comparable(average, over_share, period="FY2027Q1", grain="campaign")


def test_provider_metric_definition_pinned() -> None:
    ads = get_metric_definition("VIEWABILITY_RATE")
    assert ads.provider == "google_ads"
    assert ads.fingerprint
    with pytest.raises(ExposureMetricNotComparableError):
        assert_comparable(
            ads,
            ads,
            period="FY2027Q1",
            grain="day",
            provider="meta",
        )


def test_incompatible_denominators_not_combined() -> None:
    human = get_metric_definition("HUMAN_VALID_IMPRESSIONS")
    viewable = get_metric_definition("VIEWABLE_IMPRESSIONS")
    in_target = get_metric_definition("IN_TARGET_RATE")
    assert qualified_impressions_proxy_allowed(human, viewable, in_target) is False
    with pytest.raises(ExposureMetricNotComparableError):
        assert_comparable(human, viewable, period="FY2027Q1", grain="day")


def test_no_universal_quality_score() -> None:
    ids = {item.metric_id for item in EXPOSURE_METRIC_CATALOG}
    assert "EXPOSURE_QUALITY_SCORE" not in ids
    assert "DELIVERY_CONFIDENCE" not in ids
    assert FORBIDDEN_COMPOSITE_METRIC_IDS.isdisjoint(ids)
    with pytest.raises(ValueError, match="Universal exposure quality"):
        ExposureMetricDefinition(
            metric_id="EXPOSURE_QUALITY_SCORE",
            canonical_name="Score",
            numerator_definition="mix",
            denominator_definition="1",
            population="mixed",
            unit="score",
            grain="day",
            comparability_class="composite",
            created_at=get_metric_definition("VIEWABILITY_RATE").created_at,
            fingerprint="fp",
        )

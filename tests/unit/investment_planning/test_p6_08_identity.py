"""P6-08 identity, coverage, and missing-not-zero proofs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.investment_planning.enums import (
    EvidenceCoverageStatus,
    ExposureCoverageDimension,
    ExposureFreshnessState,
)
from app.investment_planning.errors import (
    ExposureEntityMappingRequiredError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.exposure_evidence import (
    compile_delivery_health_evidence,
    default_exposure_risk_policy,
)
from app.investment_planning.exposure_observations import normalize_observation
from app.investment_planning.exposure_profile import compute_exposure_coverage
from tests.unit.investment_planning.p6_08_support import CHANNEL, PROJECT, observation
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A


def test_market_channel_canonical_refs() -> None:
    row = observation(metric_id="VIEWABILITY_RATE", value="0.40")
    normalized = normalize_observation(row, known_market_ids={MARKET_A})
    assert normalized.market_id == MARKET_A
    assert normalized.channel_id == CHANNEL
    with pytest.raises(UnresolvedMarketIdentityError):
        normalize_observation(
            observation(metric_id="VIEWABILITY_RATE", value="0.40", market_id="United States"),
            known_market_ids={MARKET_A},
        )


def test_campaign_context_optional() -> None:
    plain = normalize_observation(
        observation(metric_id="VIEWABILITY_RATE", value="0.80"),
        known_market_ids={MARKET_A},
    )
    assert plain.campaign_id is None
    with pytest.raises(ExposureEntityMappingRequiredError):
        normalize_observation(
            observation(
                metric_id="VIEWABILITY_RATE",
                value="0.80",
                campaign_id="camp_unknownaaaaaaaaaa",
            ),
            known_market_ids={MARKET_A},
            known_campaign_ids=frozenset(),
        )


def test_missing_exposure_not_zero_quality() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    evidence = compile_delivery_health_evidence(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=(),
        policy=policy,
        created_at=now,
    )
    coverage = compute_exposure_coverage(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=(),
        known_market_ids={MARKET_A},
        known_channel_ids={CHANNEL},
    )
    assert evidence.coverage is EvidenceCoverageStatus.MISSING
    assert coverage.overall_status is EvidenceCoverageStatus.MISSING
    assert "missing_evidence_is_not_zero_quality" in evidence.limitations
    assert not any(item.observed_count < 0 for item in coverage.items)


def test_coverage_computed() -> None:
    rows = (
        observation(metric_id="VIEWABILITY_RATE", value="0.80"),
        observation(metric_id="IVT_RATE", value="0.02"),
    )
    coverage = compute_exposure_coverage(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=rows,
        known_market_ids={MARKET_A},
        known_channel_ids={CHANNEL},
    )
    by_dim = {item.dimension: item for item in coverage.items}
    assert by_dim[ExposureCoverageDimension.MARKET].observed_count == 1
    assert by_dim[ExposureCoverageDimension.CHANNEL].observed_count == 1
    assert coverage.overall_status is not EvidenceCoverageStatus.MISSING


def test_stale_evidence_flagged() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    rows = (
        observation(
            metric_id="VIEWABILITY_RATE",
            value="0.80",
            freshness=ExposureFreshnessState.STALE,
        ),
    )
    evidence = compile_delivery_health_evidence(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=rows,
        policy=policy,
        created_at=now,
    )
    assert any(flag.value == "EXPOSURE_DATA_STALE" for flag in evidence.flags)
    coverage = compute_exposure_coverage(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=rows,
        known_market_ids={MARKET_A},
        known_channel_ids={CHANNEL},
    )
    assert coverage.overall_status is EvidenceCoverageStatus.REVIEW_REQUIRED

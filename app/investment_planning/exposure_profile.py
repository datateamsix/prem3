"""Portfolio exposure risk profile and coverage. Missing is not zero."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import (
    DeliveryHealthFlag,
    EvidenceCoverageStatus,
    ExposureCoverageDimension,
    ExposureOptimizationRole,
    SensitiveDataClass,
)
from app.investment_planning.exposure_evidence import DeliveryHealthEvidence
from app.investment_planning.exposure_observations import ExposureMetricObservation
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.ids import new_exposure_profile_id


class ExposureCoverageItem(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    dimension: ExposureCoverageDimension
    status: EvidenceCoverageStatus
    observed_count: int
    expected_count: int | None = None


class PortfolioExposureCoverage(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    project_id: str
    period: str
    items: tuple[ExposureCoverageItem, ...]
    overall_status: EvidenceCoverageStatus
    fingerprint: str


class PortfolioExposureRiskProfile(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    profile_id: str
    project_id: str
    period: str
    market_id: str | None = None
    channel_id: str | None = None
    campaign_id: str | None = None
    portfolio_snapshot_id: str | None = None
    coverage: PortfolioExposureCoverage
    risk_flags: tuple[DeliveryHealthFlag, ...] = ()
    metric_evidence_refs: tuple[str, ...] = ()
    role_eligibility: tuple[ExposureOptimizationRole, ...] = ()
    qualified_constraint_guardrail_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    fingerprint: str
    created_at: datetime


def compute_exposure_coverage(
    *,
    project_id: str,
    period: str,
    observations: tuple[ExposureMetricObservation, ...],
    known_market_ids: frozenset[str] | set[str],
    known_channel_ids: frozenset[str] | set[str],
) -> PortfolioExposureCoverage:
    markets = {item.market_id for item in observations}
    channels = {item.channel_id for item in observations}
    campaign_provider = {
        (item.campaign_id, item.provider_id)
        for item in observations
        if item.campaign_id or item.provider_id
    }
    stale = any(item.freshness.value == "STALE" for item in observations)
    items = (
        ExposureCoverageItem(
            dimension=ExposureCoverageDimension.PORTFOLIO_SPEND,
            status=(
                EvidenceCoverageStatus.PARTIAL
                if observations
                else EvidenceCoverageStatus.MISSING
            ),
            observed_count=len(observations),
            expected_count=None,
        ),
        ExposureCoverageItem(
            dimension=ExposureCoverageDimension.MARKET,
            status=(
                EvidenceCoverageStatus.COVERED
                if known_market_ids and markets == set(known_market_ids)
                else EvidenceCoverageStatus.PARTIAL
                if markets
                else EvidenceCoverageStatus.MISSING
            ),
            observed_count=len(markets),
            expected_count=len(known_market_ids),
        ),
        ExposureCoverageItem(
            dimension=ExposureCoverageDimension.CHANNEL,
            status=(
                EvidenceCoverageStatus.COVERED
                if known_channel_ids and channels == set(known_channel_ids)
                else EvidenceCoverageStatus.PARTIAL
                if channels
                else EvidenceCoverageStatus.MISSING
            ),
            observed_count=len(channels),
            expected_count=len(known_channel_ids),
        ),
        ExposureCoverageItem(
            dimension=ExposureCoverageDimension.CAMPAIGN_PROVIDER,
            status=(
                EvidenceCoverageStatus.PARTIAL
                if campaign_provider
                else EvidenceCoverageStatus.NOT_APPLICABLE
            ),
            observed_count=len(campaign_provider),
            expected_count=None,
        ),
        ExposureCoverageItem(
            dimension=ExposureCoverageDimension.FRESHNESS,
            status=(
                EvidenceCoverageStatus.REVIEW_REQUIRED
                if stale
                else EvidenceCoverageStatus.COVERED
                if observations
                else EvidenceCoverageStatus.MISSING
            ),
            observed_count=len(observations),
            expected_count=None,
        ),
    )
    if not observations:
        overall = EvidenceCoverageStatus.MISSING
    elif stale:
        overall = EvidenceCoverageStatus.REVIEW_REQUIRED
    elif markets or channels:
        overall = EvidenceCoverageStatus.PARTIAL
    else:
        overall = EvidenceCoverageStatus.COVERED
    fingerprint = metadata_fingerprint(
        {
            "project_id": project_id,
            "period": period,
            "items": tuple(
                (item.dimension.value, item.status.value, item.observed_count)
                for item in items
            ),
        }
    )
    return PortfolioExposureCoverage(
        project_id=project_id,
        period=period,
        items=items,
        overall_status=overall,
        fingerprint=fingerprint,
    )


def assemble_exposure_profile(
    *,
    project_id: str,
    period: str,
    evidence: DeliveryHealthEvidence,
    coverage: PortfolioExposureCoverage,
    created_at: datetime,
    portfolio_snapshot_id: str | None = None,
    market_id: str | None = None,
    channel_id: str | None = None,
    campaign_id: str | None = None,
    role_eligibility: tuple[ExposureOptimizationRole, ...] = (),
    qualified_constraint_guardrail_ids: tuple[str, ...] = (),
) -> PortfolioExposureRiskProfile:
    profile_id = new_exposure_profile_id()
    fingerprint = metadata_fingerprint(
        {
            "profile_id": profile_id,
            "evidence": evidence.fingerprint,
            "coverage": coverage.fingerprint,
            "flags": tuple(item.value for item in evidence.flags),
            "roles": tuple(item.value for item in role_eligibility),
        }
    )
    limitations = evidence.limitations
    if coverage.overall_status is EvidenceCoverageStatus.MISSING:
        limitations = (*limitations, "missing_exposure_is_not_zero_risk")
    return PortfolioExposureRiskProfile(
        profile_id=profile_id,
        project_id=project_id,
        period=period,
        market_id=market_id,
        channel_id=channel_id,
        campaign_id=campaign_id,
        portfolio_snapshot_id=portfolio_snapshot_id,
        coverage=coverage,
        risk_flags=evidence.flags,
        metric_evidence_refs=(evidence.evidence_id, *evidence.metric_refs),
        role_eligibility=role_eligibility,
        qualified_constraint_guardrail_ids=qualified_constraint_guardrail_ids,
        limitations=limitations,
        fingerprint=fingerprint,
        created_at=created_at,
    )

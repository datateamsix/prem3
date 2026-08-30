"""Delivery health evidence and versioned exposure risk policy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import (
    DeliveryHealthFlag,
    EvidenceCoverageStatus,
    ExposureFreshnessState,
    ExposureQualityStatus,
    SensitiveDataClass,
)
from app.investment_planning.exposure_metrics import get_metric_definition
from app.investment_planning.exposure_observations import ExposureMetricObservation
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.ids import new_exposure_evidence_id, new_exposure_policy_id

POLICY_VERSION = "exposure_risk_policy/v1"


class MetricGuardrail(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    metric_id: str
    operator: str
    threshold: Decimal
    flag: DeliveryHealthFlag


class SpendQualityRelationship(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    relationship_id: str
    metric_id: str
    basis: str
    fingerprint: str


class ExposureRiskPolicy(FrozenModel):
    """Operational policy. Not universal scientific truth."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    policy_id: str
    metric_guardrails: tuple[MetricGuardrail, ...] = ()
    freshness_limits: tuple[str, ...] = ()
    minimum_coverage: tuple[str, ...] = ()
    provider_specific_rules: tuple[str, ...] = ()
    model_input_metrics: tuple[str, ...] = ()
    spend_quality_relationships: tuple[SpendQualityRelationship, ...] = ()
    created_at: datetime
    fingerprint: str


def default_exposure_risk_policy(*, created_at: datetime) -> ExposureRiskPolicy:
    guardrails = (
        MetricGuardrail(
            metric_id="VIEWABILITY_RATE",
            operator="lt",
            threshold=Decimal("0.70"),
            flag=DeliveryHealthFlag.LOW_VIEWABILITY,
        ),
        MetricGuardrail(
            metric_id="IVT_RATE",
            operator="gt",
            threshold=Decimal("0.05"),
            flag=DeliveryHealthFlag.HIGH_IVT,
        ),
        MetricGuardrail(
            metric_id="IN_TARGET_RATE",
            operator="lt",
            threshold=Decimal("0.60"),
            flag=DeliveryHealthFlag.LOW_IN_TARGET_RATE,
        ),
        MetricGuardrail(
            metric_id="UNIQUE_REACH",
            operator="lt",
            threshold=Decimal("1000"),
            flag=DeliveryHealthFlag.LOW_UNIQUE_REACH,
        ),
        MetricGuardrail(
            metric_id="OVER_FREQUENCY_SHARE",
            operator="gt",
            threshold=Decimal("0.20"),
            flag=DeliveryHealthFlag.OVER_FREQUENCY,
        ),
        MetricGuardrail(
            metric_id="UNDER_FREQUENCY_SHARE",
            operator="gt",
            threshold=Decimal("0.50"),
            flag=DeliveryHealthFlag.UNDER_FREQUENCY,
        ),
    )
    relationships = (
        SpendQualityRelationship(
            relationship_id="sqr_frequency_cap_v1",
            metric_id="OVER_FREQUENCY_SHARE",
            basis="PROVIDER_CAPACITY",
            fingerprint=metadata_fingerprint(
                {"metric_id": "OVER_FREQUENCY_SHARE", "basis": "PROVIDER_CAPACITY"}
            ),
        ),
    )
    policy_id = new_exposure_policy_id()
    fingerprint = metadata_fingerprint(
        {
            "version": POLICY_VERSION,
            "guardrails": tuple(item.metric_id for item in guardrails),
            "relationships": tuple(item.relationship_id for item in relationships),
        }
    )
    return ExposureRiskPolicy(
        policy_id=policy_id,
        metric_guardrails=guardrails,
        freshness_limits=("daily",),
        minimum_coverage=("channel",),
        provider_specific_rules=("provider_definitions_are_not_interchangeable",),
        model_input_metrics=("UNIQUE_REACH", "AVERAGE_FREQUENCY"),
        spend_quality_relationships=relationships,
        created_at=created_at,
        fingerprint=fingerprint,
    )


class DeliveryHealthEvidence(FrozenModel):
    """Evidence, not an optimization decision."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    evidence_id: str
    project_id: str
    period: str
    entity_refs: tuple[str, ...] = ()
    metric_refs: tuple[str, ...] = ()
    coverage: EvidenceCoverageStatus
    freshness: ExposureFreshnessState
    flags: tuple[DeliveryHealthFlag, ...] = ()
    limitations: tuple[str, ...] = ()
    source_fingerprints: tuple[str, ...] = ()
    created_at: datetime
    fingerprint: str


def _matches(operator: str, value: Decimal, threshold: Decimal) -> bool:
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    return False


def compile_delivery_health_evidence(
    *,
    project_id: str,
    period: str,
    observations: tuple[ExposureMetricObservation, ...],
    policy: ExposureRiskPolicy,
    created_at: datetime,
) -> DeliveryHealthEvidence:
    flags: list[DeliveryHealthFlag] = []
    if not observations:
        flags.append(DeliveryHealthFlag.EXPOSURE_DATA_INCOMPLETE)
        coverage = EvidenceCoverageStatus.MISSING
        freshness = ExposureFreshnessState.UNKNOWN
    else:
        coverage = EvidenceCoverageStatus.PARTIAL
        freshness = ExposureFreshnessState.FRESH
        for observation in observations:
            get_metric_definition(observation.metric_id)
            if observation.freshness is ExposureFreshnessState.STALE:
                flags.append(DeliveryHealthFlag.EXPOSURE_DATA_STALE)
                freshness = ExposureFreshnessState.STALE
            if observation.quality_status is ExposureQualityStatus.BLOCKER:
                flags.append(DeliveryHealthFlag.EXPOSURE_DATA_INCOMPLETE)
            for guardrail in policy.metric_guardrails:
                if guardrail.metric_id != observation.metric_id:
                    continue
                if _matches(guardrail.operator, observation.value, guardrail.threshold):
                    flags.append(guardrail.flag)
        if all(item.freshness is ExposureFreshnessState.FRESH for item in observations):
            coverage = EvidenceCoverageStatus.COVERED
    unique_flags = tuple(dict.fromkeys(flags))
    metric_refs = tuple(dict.fromkeys(item.metric_id for item in observations))
    entity_refs = tuple(
        dict.fromkeys(
            f"{item.market_id}:{item.channel_id}"
            + (f":{item.campaign_id}" if item.campaign_id else "")
            for item in observations
        )
    )
    source_fingerprints = tuple(dict.fromkeys(item.fingerprint for item in observations))
    limitations = ("missing_evidence_is_not_zero_quality",)
    if DeliveryHealthFlag.EXPOSURE_DATA_STALE in unique_flags:
        limitations = (*limitations, "stale_evidence_is_not_current")
    evidence_id = new_exposure_evidence_id()
    fingerprint = metadata_fingerprint(
        {
            "project_id": project_id,
            "period": period,
            "flags": tuple(item.value for item in unique_flags),
            "metric_refs": metric_refs,
            "policy": policy.fingerprint,
        }
    )
    return DeliveryHealthEvidence(
        evidence_id=evidence_id,
        project_id=project_id,
        period=period,
        entity_refs=entity_refs,
        metric_refs=metric_refs,
        coverage=coverage,
        freshness=freshness,
        flags=unique_flags,
        limitations=limitations,
        source_fingerprints=source_fingerprints,
        created_at=created_at,
        fingerprint=fingerprint,
    )

"""Immutable MMM result and Decision Intelligence contracts (M4-00)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.core.contracts import utc_now
from app.modeling.mmm.contracts import (
    DecisionIntelligenceAuthority,
    FrozenModel,
    OfficialHealthStatus,
    ReviewSource,
)


class MMMResultStatus(StrEnum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    FIT_COMPLETE_REVIEW_PENDING = "FIT_COMPLETE_REVIEW_PENDING"
    REVIEWED_NOT_ACCEPTED = "REVIEWED_NOT_ACCEPTED"
    ACCEPTED = "ACCEPTED"
    SUPERSEDED = "SUPERSEDED"


class MetricAvailability(StrEnum):
    VALUE = "VALUE"
    ZERO = "ZERO"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    INVALID = "INVALID"


class EvidenceEligibility(StrEnum):
    PRE_ACCEPTANCE_RESULTS = "PRE_ACCEPTANCE_RESULTS"
    ACCEPTED_MODEL_RESULTS = "ACCEPTED_MODEL_RESULTS"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


PRE_ACCEPTANCE_RESULTS = EvidenceEligibility.PRE_ACCEPTANCE_RESULTS
ACCEPTED_MODEL_RESULTS = EvidenceEligibility.ACCEPTED_MODEL_RESULTS


class LimitationCategory(StrEnum):
    UNCERTAINTY = "UNCERTAINTY"
    COLLINEARITY = "COLLINEARITY"
    DATA_COVERAGE = "DATA_COVERAGE"
    MODEL_SPECIFICATION = "MODEL_SPECIFICATION"
    EXTRAPOLATION = "EXTRAPOLATION"
    GEO_SCOPE = "GEO_SCOPE"
    PRIOR_SENSITIVITY = "PRIOR_SENSITIVITY"
    MODEL_REVIEW = "MODEL_REVIEW"


class LimitationSeverity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    BLOCKING = "BLOCKING"


class FindingType(StrEnum):
    CHANNEL_METRIC = "CHANNEL_METRIC"
    PORTFOLIO_METRIC = "PORTFOLIO_METRIC"
    MODEL_HEALTH = "MODEL_HEALTH"
    LIMITATION = "LIMITATION"
    BUSINESS_IQ_CONTEXT = "BUSINESS_IQ_CONTEXT"
    REVIEW_OBSERVATION = "REVIEW_OBSERVATION"


class UnavailableReason(StrEnum):
    FIT_NOT_COMPLETE = "FIT_NOT_COMPLETE"
    EXTRACTION_PENDING = "EXTRACTION_PENDING"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    NO_MODEL_ARTIFACT = "NO_MODEL_ARTIFACT"
    UNSUPPORTED_RUNTIME = "UNSUPPORTED_RUNTIME"


class IntervalEvidence(FrozenModel):
    lower: float | None = None
    upper: float | None = None
    confidence_level: float | None = None
    availability: MetricAvailability = MetricAvailability.NOT_AVAILABLE


class MetricValue(FrozenModel):
    value: float | None = None
    availability: MetricAvailability = MetricAvailability.NOT_AVAILABLE
    interval: IntervalEvidence | None = None
    unit: str | None = None
    source_method: str | None = None


class ResponseCurvePoint(FrozenModel):
    spend_level: float
    expected_outcome: float | None = None
    outcome_lower: float | None = None
    outcome_upper: float | None = None


class ResponseCurveEvidence(FrozenModel):
    response_curve_id: str
    result_snapshot_id: str
    channel_id: str
    points: tuple[ResponseCurvePoint, ...] = ()
    points_ref: str | None = None
    current_spend: float | None = None
    current_expected_outcome: float | None = None
    current_marginal_roi: float | None = None
    spend_unit: str | None = None
    outcome_unit: str | None = None
    uncertainty_available: bool = False
    source_method: str = "Analyzer.response_curves"
    fingerprint: str
    observed_spend_min: float | None = None
    observed_spend_max: float | None = None


class MarginalEfficiencyEvidence(FrozenModel):
    channel_id: str
    current_spend: float | None = None
    marginal_roi: MetricValue
    response_curve_ref: str | None = None
    authority: DecisionIntelligenceAuthority = DecisionIntelligenceAuthority.VERIFIED


class ModelFitEvidence(FrozenModel):
    official_review_source: ReviewSource
    convergence_status: str | None = None
    review_checks: tuple[str, ...] = ()
    review_acknowledgments: tuple[str, ...] = ()
    blocking_failures: tuple[str, ...] = ()
    review_items: tuple[str, ...] = ()
    model_accepted: bool = False
    overall_health_score: float | None = None
    official_health_status: OfficialHealthStatus | None = None


class ModelLimitation(FrozenModel):
    limitation_id: str
    category: LimitationCategory
    authority: DecisionIntelligenceAuthority
    severity: LimitationSeverity
    title: str
    description: str
    evidence_refs: tuple[str, ...] = ()
    affected_metrics: tuple[str, ...] = ()
    affected_channels: tuple[str, ...] = ()


class ResultProvenance(FrozenModel):
    model_ready_fingerprint: str | None = None
    business_profile_snapshot_id: str | None = None
    data_foundation_fingerprint: str | None = None
    model_plan_fingerprint: str | None = None
    model_decision_ids: tuple[str, ...] = ()
    fit_plan_fingerprint: str | None = None
    fit_approval_id: str | None = None
    fit_run_id: str
    model_artifact_sha256: str
    review_pack_fingerprint: str | None = None
    analyzer_source_methods: tuple[str, ...] = ()
    eda_finding_ids: tuple[str, ...] = ()
    eda_modeling_implication_ids: tuple[str, ...] = ()


class MMMChannelResult(FrozenModel):
    channel_id: str
    channel_name: str
    spend: MetricValue = Field(default_factory=MetricValue)
    incremental_outcome: MetricValue = Field(default_factory=MetricValue)
    contribution: MetricValue = Field(default_factory=MetricValue)
    roi: MetricValue = Field(default_factory=MetricValue)
    marginal_roi: MetricValue = Field(default_factory=MetricValue)
    response_curve_ref: str | None = None
    evidence_status: MetricAvailability = MetricAvailability.NOT_AVAILABLE
    availability: MetricAvailability = MetricAvailability.NOT_AVAILABLE


class MMMPortfolioSummary(FrozenModel):
    total_spend: MetricValue = Field(default_factory=MetricValue)
    modeled_incremental_outcome: MetricValue = Field(default_factory=MetricValue)
    portfolio_roi: MetricValue = Field(default_factory=MetricValue)
    formulas: tuple[str, ...] = (
        "total_spend = sum(channel.spend where VALUE or ZERO)",
        "modeled_incremental_outcome = sum(channel.incremental_outcome where VALUE or ZERO)",
        "portfolio_roi = modeled_incremental_outcome / total_spend when total_spend > 0",
    )


class MMMResultsSnapshot(FrozenModel):
    result_snapshot_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    model_version_id: str
    fit_run_id: str
    model_plan_fingerprint: str | None = None
    fit_plan_fingerprint: str | None = None
    model_artifact_sha256: str
    review_pack_fingerprint: str | None = None
    result_status: MMMResultStatus
    eligibility: EvidenceEligibility
    outcome_name: str | None = None
    outcome_unit: str | None = None
    currency: str | None = None
    model_window_start: str | None = None
    model_window_end: str | None = None
    channels: tuple[MMMChannelResult, ...] = ()
    portfolio_summary: MMMPortfolioSummary = Field(default_factory=MMMPortfolioSummary)
    response_curves: tuple[ResponseCurveEvidence, ...] = ()
    marginal_efficiency: tuple[MarginalEfficiencyEvidence, ...] = ()
    fit_evidence: ModelFitEvidence
    limitations: tuple[ModelLimitation, ...] = ()
    provenance: ResultProvenance
    source_runtime: str
    meridian_version: str
    adapter_version: str
    metric_extraction_policy_version: str
    synthetic: bool = False
    synthetic_label: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    result_fingerprint: str
    gcs_snapshot_ref: str | None = None
    gcs_channel_results_ref: str | None = None
    gcs_brief_ref: str | None = None
    ledger_readback_verified: bool = False


class MMMResultsUnavailable(FrozenModel):
    status: MMMResultStatus = MMMResultStatus.NOT_AVAILABLE
    reason: UnavailableReason
    project_id: str
    cycle_id: str
    model_version_id: str | None = None
    fit_run_id: str | None = None
    detail: str | None = None


class DecisionIntelligenceFinding(FrozenModel):
    finding_id: str
    authority: DecisionIntelligenceAuthority
    finding_type: FindingType
    title: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    affected_channels: tuple[str, ...] = ()
    confidence: str | None = None


class CounterEvidence(FrozenModel):
    counter_evidence_id: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    affected_channels: tuple[str, ...] = ()


class DecisionRequirement(FrozenModel):
    requirement_id: str
    authority: DecisionIntelligenceAuthority = DecisionIntelligenceAuthority.DECISION_REQUIRED
    title: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    affected_channels: tuple[str, ...] = ()


class AdvisorRecommendation(FrozenModel):
    recommendation_id: str
    authority: DecisionIntelligenceAuthority = DecisionIntelligenceAuthority.RECOMMENDATION
    title: str
    recommended_action: str
    rationale: str
    evidence_refs: tuple[str, ...] = ()
    counter_evidence_refs: tuple[str, ...] = ()
    uncertainty_refs: tuple[str, ...] = ()
    affected_channels: tuple[str, ...] = ()
    decision_required: bool = True
    status: str = "PROPOSED"
    investment_action: bool = False


class MMMDecisionIntelligenceBrief(FrozenModel):
    brief_id: str
    result_snapshot_id: str | None = None
    model_version_id: str
    fit_run_id: str | None = None
    result_status: MMMResultStatus
    eligibility: EvidenceEligibility
    executive_summary: str
    verified_findings: tuple[DecisionIntelligenceFinding, ...] = ()
    interpretations: tuple[DecisionIntelligenceFinding, ...] = ()
    recommendations: tuple[AdvisorRecommendation, ...] = ()
    counter_evidence: tuple[CounterEvidence, ...] = ()
    uncertainties: tuple[DecisionIntelligenceFinding, ...] = ()
    decision_requirements: tuple[DecisionRequirement, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    policy_version: str
    knowledge_version: str
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str
    gcs_brief_ref: str | None = None


class ResultSnapshotPointer(FrozenModel):
    """Compact Firestore pointer document — no nested channel arrays."""

    project_id: str
    cycle_id: str
    tenant_id: str
    latest_result_snapshot_id: str | None = None
    accepted_result_snapshot_id: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ResultSnapshotMetadata(FrozenModel):
    """Compact Firestore metadata for one immutable result snapshot."""

    result_snapshot_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    model_version_id: str
    fit_run_id: str
    result_status: MMMResultStatus
    eligibility: EvidenceEligibility
    result_fingerprint: str
    model_artifact_sha256: str
    adapter_version: str
    meridian_version: str
    metric_extraction_policy_version: str
    gcs_snapshot_ref: str | None = None
    gcs_channel_results_ref: str | None = None
    gcs_brief_ref: str | None = None
    ledger_readback_verified: bool = False
    synthetic: bool = False
    channel_count: int = 0
    generated_at: datetime = Field(default_factory=utc_now)


class RawChannelMetricBundle(FrozenModel):
    """Adapter output before typed validation — still null-safe."""

    channel_id: str
    channel_name: str
    spend: float | None = None
    incremental_outcome: float | None = None
    incremental_outcome_lower: float | None = None
    incremental_outcome_upper: float | None = None
    contribution: float | None = None
    contribution_lower: float | None = None
    contribution_upper: float | None = None
    roi: float | None = None
    roi_lower: float | None = None
    roi_upper: float | None = None
    marginal_roi: float | None = None
    marginal_roi_lower: float | None = None
    marginal_roi_upper: float | None = None
    source_methods: tuple[str, ...] = ()
    metric_flags: dict[str, str] = Field(default_factory=dict)


class RawResponseCurveBundle(FrozenModel):
    channel_id: str
    points: tuple[ResponseCurvePoint, ...] = ()
    current_spend: float | None = None
    spend_unit: str | None = None
    outcome_unit: str | None = None
    uncertainty_available: bool = False
    observed_spend_min: float | None = None
    observed_spend_max: float | None = None
    source_method: str = "Analyzer.response_curves"


class RawMeridianResultsEvidence(FrozenModel):
    meridian_version: str
    adapter_version: str
    source_methods_used: tuple[str, ...] = ()
    source_methods_unavailable: tuple[str, ...] = ()
    channels: tuple[RawChannelMetricBundle, ...] = ()
    response_curves: tuple[RawResponseCurveBundle, ...] = ()
    confidence_level: float | None = None
    notes: tuple[str, ...] = ()
    synthetic: bool = False

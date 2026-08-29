"""Immutable MTA result, visualization, and Decision Intelligence contracts.

Observable journey attribution evidence — never causal incrementality.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.core.contracts import utc_now
from app.modeling.mta.contracts import FrozenModel
from app.modeling.mta.runtime_contracts import MTAComputationAuthority, MTAInputMode

RESULTS_COMPILER_VERSION = "mta_results_compiler_v1"
SENSITIVITY_POLICY_VERSION = "mta_sensitivity_policy_v1"
ROLE_POLICY_VERSION = "mta_channel_role_policy_v1"
POSITION_POLICY_VERSION = "position_policy_v1"
OBSERVABILITY_POLICY_VERSION = "mta_observability_policy_v1"
DECISION_INTELLIGENCE_POLICY_VERSION = "mta_decision_intelligence_policy_v1"
POSITION_POLICY_SINGLE_TOUCH = "FIRST_AND_LAST"

# Result/brief field scan — stricter than public MTA copy (plan causal-language guard).
RESULT_FORBIDDEN_SUBSTRINGS = (
    "incremental",
    "causal",
    "lift",
    "true contribution",
)


class MTAResultStatus(StrEnum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUPERSEDED = "SUPERSEDED"


class MetricAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED_BY_PREFLIGHT = "BLOCKED_BY_PREFLIGHT"
    UNAVAILABLE_SOURCE = "UNAVAILABLE_SOURCE"
    INVALID = "INVALID"


class MTAEvidenceAuthority(StrEnum):
    LIVE_AUTHORIZED_SOURCE = "LIVE_AUTHORIZED_SOURCE"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"
    TEST = "TEST"


class MTAFindingAuthority(StrEnum):
    VERIFIED = "VERIFIED"
    INTERPRETATION = "INTERPRETATION"
    RECOMMENDATION = "RECOMMENDATION"
    DECISION_REQUIRED = "DECISION_REQUIRED"


class SensitivityLabel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class ChannelRoleLabel(StrEnum):
    INTRODUCER = "INTRODUCER"
    ASSISTER = "ASSISTER"
    CONVERTER = "CONVERTER"
    MULTI_ROLE = "MULTI_ROLE"
    DIRECT_CAPTURE = "DIRECT_CAPTURE"
    MODEL_SENSITIVE = "MODEL_SENSITIVE"
    LOW_OBSERVABILITY = "LOW_OBSERVABILITY"


class ObservabilityStatus(StrEnum):
    GOOD = "GOOD"
    REVIEW = "REVIEW"
    LIMITED = "LIMITED"


class LimitationSeverity(StrEnum):
    INFO = "INFO"
    ATTENTION = "ATTENTION"
    BLOCKING = "BLOCKING"


class MTALimitationType(StrEnum):
    IDENTITY_FRAGMENTATION = "IDENTITY_FRAGMENTATION"
    CONSENT_OBSERVABILITY = "CONSENT_OBSERVABILITY"
    UNMAPPED_TRAFFIC = "UNMAPPED_TRAFFIC"
    HIGH_DIRECT_SHARE = "HIGH_DIRECT_SHARE"
    LOW_CONVERSION_VOLUME = "LOW_CONVERSION_VOLUME"
    LOW_CHANNEL_VOLUME = "LOW_CHANNEL_VOLUME"
    SHAPLEY_PATH_LIMIT = "SHAPLEY_PATH_LIMIT"
    MODEL_SENSITIVITY = "MODEL_SENSITIVITY"
    MISSING_CONVERSION_VALUE = "MISSING_CONVERSION_VALUE"
    TRAFFIC_SOURCE_POLICY_FALLBACK = "TRAFFIC_SOURCE_POLICY_FALLBACK"
    OTHER = "OTHER"


class MTAVisualizationKind(StrEnum):
    ATTRIBUTION_BY_CHANNEL_MODEL = "ATTRIBUTION_BY_CHANNEL_MODEL"
    MODEL_COMPARISON_HEATMAP = "MODEL_COMPARISON_HEATMAP"
    CHANNEL_ROLE_POSITION = "CHANNEL_ROLE_POSITION"
    MARKOV_TRANSITION_MATRIX = "MARKOV_TRANSITION_MATRIX"
    MARKOV_REMOVAL_EFFECT = "MARKOV_REMOVAL_EFFECT"
    SHAPLEY_CONTRIBUTION = "SHAPLEY_CONTRIBUTION"
    TOP_CONVERSION_PATHS = "TOP_CONVERSION_PATHS"
    PATH_LENGTH_DISTRIBUTION = "PATH_LENGTH_DISTRIBUTION"
    TIME_TO_CONVERSION_DISTRIBUTION = "TIME_TO_CONVERSION_DISTRIBUTION"
    MODEL_SENSITIVITY_RANGE = "MODEL_SENSITIVITY_RANGE"


class ComparisonMetric(StrEnum):
    ATTRIBUTION_SHARE = "ATTRIBUTION_SHARE"
    ATTRIBUTED_CREDIT = "ATTRIBUTED_CREDIT"


class MTAResultsCompileFailureClass(StrEnum):
    MTA_RESULTS_SOURCE_NOT_VERIFIED = "MTA_RESULTS_SOURCE_NOT_VERIFIED"
    MTA_RESULTS_MISSING_REQUIRED_OUTPUT = "MTA_RESULTS_MISSING_REQUIRED_OUTPUT"
    MTA_RESULTS_SCHEMA_ERROR = "MTA_RESULTS_SCHEMA_ERROR"
    MTA_RESULTS_INVALID_NUMERIC = "MTA_RESULTS_INVALID_NUMERIC"
    MTA_VISUALIZATION_COMPILE_ERROR = "MTA_VISUALIZATION_COMPILE_ERROR"
    MTA_ROLE_POLICY_ERROR = "MTA_ROLE_POLICY_ERROR"
    MTA_DECISION_BRIEF_ERROR = "MTA_DECISION_BRIEF_ERROR"
    BIGQUERY_READBACK_ERROR = "BIGQUERY_READBACK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class MeasurementMethod(StrEnum):
    MTA = "MTA"
    MMM = "MMM"


class MetricAvailabilityItem(FrozenModel):
    metric_name: str
    status: MetricAvailability
    reason: str | None = None


class MTALimitation(FrozenModel):
    limitation_type: MTALimitationType
    severity: LimitationSeverity = LimitationSeverity.ATTENTION
    statement: str
    evidence_refs: tuple[str, ...] = ()
    affected_channels: tuple[str, ...] = ()


class MTAObservabilitySummary(FrozenModel):
    identity_strategy: str | None = None
    user_pseudo_id_coverage: float | None = None
    user_id_coverage: float | None = None
    traffic_source_coverage: float | None = None
    channel_mapping_coverage: float | None = None
    other_unclassified_share: float | None = None
    conversion_value_coverage: float | None = None
    nonconverting_path_coverage: float | None = None
    source_cutoff: str | None = None
    status: ObservabilityStatus
    policy_version: str = OBSERVABILITY_POLICY_VERSION
    limitations: tuple[MTALimitation, ...] = ()


class MeasurementEvidenceAlignmentKey(FrozenModel):
    channel_id: str
    conversion_event: str
    period_start: str
    period_end: str
    method: MeasurementMethod = MeasurementMethod.MTA
    market: str | None = None
    result_snapshot_id: str | None = None


class MTAChannelResult(FrozenModel):
    channel_id: str
    channel_display_name: str
    touchpoint_count: int | None = None
    journey_count: int | None = None
    journey_presence_rate: float | None = None
    first_position_share: float | None = None
    middle_position_share: float | None = None
    last_position_share: float | None = None
    first_touch_credit: float | None = None
    first_touch_share: float | None = None
    last_touch_credit: float | None = None
    last_touch_share: float | None = None
    last_non_direct_credit: float | None = None
    last_non_direct_share: float | None = None
    linear_credit: float | None = None
    linear_share: float | None = None
    time_decay_credit: float | None = None
    time_decay_share: float | None = None
    position_based_credit: float | None = None
    position_based_share: float | None = None
    markov_credit: float | None = None
    markov_share: float | None = None
    markov_removal_effect: float | None = None
    shapley_credit: float | None = None
    shapley_share: float | None = None
    model_credit_min: float | None = None
    model_credit_max: float | None = None
    model_credit_range: float | None = None
    model_credit_dispersion: float | None = None
    model_sensitivity_label: SensitivityLabel | None = None
    role_profile: tuple[str, ...] = ()
    metric_availability: tuple[MetricAvailabilityItem, ...] = ()
    limitations: tuple[MTALimitation, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    alignment_key: MeasurementEvidenceAlignmentKey | None = None


class MTAModelComparisonCell(FrozenModel):
    channel_id: str
    model_type: str
    attribution_share: float | None = None
    attributed_credit: float | None = None
    availability: MetricAvailability = MetricAvailability.AVAILABLE


class MTAModelComparison(FrozenModel):
    comparison_id: str
    run_id: str
    models: tuple[str, ...]
    channels: tuple[str, ...]
    comparison_metric: ComparisonMetric = ComparisonMetric.ATTRIBUTION_SHARE
    rows: tuple[MTAModelComparisonCell, ...]
    model_parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    dispersion_policy_version: str = SENSITIVITY_POLICY_VERSION
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class MTAModelSensitivityEvidence(FrozenModel):
    channel_id: str
    model_count: int
    min_attribution_share: float | None = None
    max_attribution_share: float | None = None
    range: float | None = None
    mean_attribution_share: float | None = None
    median_attribution_share: float | None = None
    dispersion: float | None = None
    sensitivity_label: SensitivityLabel | None = None
    models_included: tuple[str, ...] = ()
    policy_version: str = SENSITIVITY_POLICY_VERSION
    # Explicit: dispersion is max_share - min_share, not a confidence interval.
    is_confidence_interval: bool = False


class MTAModelSensitivityPolicy(FrozenModel):
    policy_version: str = SENSITIVITY_POLICY_VERSION
    low_lt: float = 0.05
    moderate_lt: float = 0.15
    high_lt: float = 0.30
    formula: str = "max_share - min_share across completed models with AVAILABLE share"


class MarkovChannelCredit(FrozenModel):
    channel_id: str
    attributed_credit: float
    attribution_share: float
    removal_effect: float | None = None


class MarkovTransitionRow(FrozenModel):
    from_channel_id: str
    to_channel_id: str
    transition_probability: float


class MarkovAttributionEvidence(FrozenModel):
    run_id: str
    channel_credit: tuple[MarkovChannelCredit, ...] = ()
    transition_matrix_ref: str | None = None
    transitions: tuple[MarkovTransitionRow, ...] = ()
    removal_effects: tuple[tuple[str, float], ...] = ()
    transition_to_same_state: bool | None = None
    input_mode: MTAInputMode | None = None
    conversion_value_as_frequency: bool | None = None
    removal_effect_explanation: str = (
        "The modeled conversion-probability sensitivity when that channel is "
        "removed from the observed Markov journey structure."
    )
    availability: MetricAvailability = MetricAvailability.AVAILABLE
    unavailable_reason: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class ShapleyChannelCredit(FrozenModel):
    channel_id: str
    shapley_credit: float
    shapley_share: float


class ShapleyAttributionEvidence(FrozenModel):
    run_id: str
    channel_credit: tuple[ShapleyChannelCredit, ...] = ()
    size: int | None = None
    order: bool | None = None
    values_col: str | None = None
    path_limit_applied: bool = False
    preflight_status: str | None = None
    input_path_count: int | None = None
    distinct_channel_count: int | None = None
    availability: MetricAvailability = MetricAvailability.NOT_RUN
    unavailable_reason: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class MTAJourneyPathEvidence(FrozenModel):
    path_rank: int
    path_string: str
    channels: tuple[str, ...]
    occurrences: int
    conversion_count: int | None = None
    conversion_value: float | None = None
    share_of_converting_paths: float | None = None
    share_of_all_paths: float | None = None


class PathLengthBin(FrozenModel):
    touchpoint_count: int
    journey_count: int
    share: float


class TimeToConversionBin(FrozenModel):
    bucket_start: float
    bucket_end: float | None
    unit: str = "days"
    journey_count: int
    share: float


class MTAChannelPositionEvidence(FrozenModel):
    channel_id: str
    first_position_count: int
    middle_position_count: int
    last_position_count: int
    first_position_share: float
    middle_position_share: float
    last_position_share: float
    journey_presence_count: int
    journey_presence_rate: float
    denominator: str = "converted_journey_count"
    single_touch_policy: str = POSITION_POLICY_SINGLE_TOUCH
    policy_version: str = POSITION_POLICY_VERSION


class MTAJourneySummary(FrozenModel):
    journey_count: int
    converted_journey_count: int
    nonconverting_journey_count: int = 0
    unique_subject_count: int | None = None
    avg_touchpoints: float | None = None
    median_touchpoints: float | None = None
    p90_touchpoints: float | None = None
    max_touchpoints: int | None = None
    avg_time_to_conversion: float | None = None
    median_time_to_conversion: float | None = None
    p90_time_to_conversion: float | None = None
    single_touch_share: float | None = None
    multi_touch_share: float | None = None
    unique_path_count: int = 0
    direct_presence_share: float | None = None
    identity_coverage_summary: str | None = None
    observability_status: ObservabilityStatus | None = None
    source_cutoff: str | None = None
    top_paths: tuple[MTAJourneyPathEvidence, ...] = ()
    path_length_distribution: tuple[PathLengthBin, ...] = ()
    time_to_conversion_distribution: tuple[TimeToConversionBin, ...] = ()
    position_evidence: tuple[MTAChannelPositionEvidence, ...] = ()
    position_policy_version: str = POSITION_POLICY_VERSION
    single_touch_policy: str = POSITION_POLICY_SINGLE_TOUCH


class ChannelRolePolicy(FrozenModel):
    policy_version: str = ROLE_POLICY_VERSION
    introducer_first_min: float = 0.40
    introducer_last_max: float = 0.25
    assister_middle_min: float = 0.40
    converter_last_min: float = 0.40
    converter_first_max: float = 0.25
    multi_role_position_min: float = 0.25
    direct_capture_last_min: float = 0.50
    presence_rate_floor: float = 0.02
    volume_floor: int = 3


class ChannelRoleProfile(FrozenModel):
    channel_id: str
    labels: tuple[ChannelRoleLabel, ...]
    policy_version: str = ROLE_POLICY_VERSION


class ChannelRoleEvidence(FrozenModel):
    channel_id: str
    labels: tuple[ChannelRoleLabel, ...]
    first_position_share: float | None = None
    middle_position_share: float | None = None
    last_position_share: float | None = None
    journey_presence_rate: float | None = None
    markov_removal_effect: float | None = None
    shapley_share: float | None = None
    sensitivity_label: SensitivityLabel | None = None
    evidence_refs: tuple[str, ...] = ()
    policy_version: str = ROLE_POLICY_VERSION


class MTAVisualization(FrozenModel):
    visualization_id: str
    kind: MTAVisualizationKind
    title: str
    description: str
    source_run_id: str
    source_result_snapshot_id: str
    source_model: str | None = None
    source_evidence_refs: tuple[str, ...] = ()
    data: tuple[dict[str, Any], ...] = ()
    available: bool = True
    unavailable_reason: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    default_view: str | None = None
    authority: MTAFindingAuthority = MTAFindingAuthority.VERIFIED
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class DecisionIntelligenceFinding(FrozenModel):
    finding_id: str
    authority: MTAFindingAuthority
    title: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    materiality: str = "CONTEXTUAL"
    affected_channels: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class DecisionIntelligenceRecommendation(FrozenModel):
    recommendation_id: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    counterevidence_refs: tuple[str, ...] = ()
    uncertainty: str | None = None
    recommended_action: str | None = None
    requires_human_decision: bool = True
    authority: MTAFindingAuthority = MTAFindingAuthority.RECOMMENDATION


class DecisionRequirement(FrozenModel):
    requirement_id: str
    decision_type: str
    statement: str
    authority: MTAFindingAuthority = MTAFindingAuthority.DECISION_REQUIRED
    evidence_refs: tuple[str, ...] = ()


class MTADecisionIntelligenceBrief(FrozenModel):
    brief_id: str
    project_id: str
    cycle_id: str
    track_id: str
    result_snapshot_id: str
    executive_summary: str
    verified_findings: tuple[DecisionIntelligenceFinding, ...] = ()
    interpretations: tuple[DecisionIntelligenceFinding, ...] = ()
    recommendations: tuple[DecisionIntelligenceRecommendation, ...] = ()
    counter_evidence: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    decision_requirements: tuple[DecisionRequirement, ...] = ()
    limitations: tuple[MTALimitation, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    policy_version: str = DECISION_INTELLIGENCE_POLICY_VERSION
    knowledge_version: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class MTAResultsSnapshot(FrozenModel):
    result_snapshot_id: str
    project_id: str
    cycle_id: str
    track_id: str
    run_id: str
    execution_plan_id: str
    run_receipt_id: str
    result_status: MTAResultStatus
    evidence_authority: MTAEvidenceAuthority
    computation_authority: MTAComputationAuthority = MTAComputationAuthority.TEST_FAKE_RUNTIME
    conversion_event: str
    conversion_period_start: str
    conversion_period_end: str
    lookback_window_days: int
    channel_registry_version: int
    channel_registry_fingerprint: str
    channel_grouping_version: str
    channel_grouping_fingerprint: str
    identity_strategy: str | None = None
    sessionization_policy: str | None = None
    traffic_source_policy: str | None = None
    direct_treatment_policy: str | None = None
    models_requested: tuple[str, ...] = ()
    models_completed: tuple[str, ...] = ()
    channel_results_ref: str
    model_comparison_ref: str
    markov_evidence_ref: str | None = None
    shapley_evidence_ref: str | None = None
    journey_summary_ref: str
    observability_summary: MTAObservabilitySummary
    limitations: tuple[MTALimitation, ...] = ()
    source_cutoff: str | None = None
    source_manifest_ref: str | None = None
    runtime_versions: dict[str, str] = Field(default_factory=dict)
    adapter_version: str
    results_compiler_version: str = RESULTS_COMPILER_VERSION
    role_policy_version: str = ROLE_POLICY_VERSION
    sensitivity_policy_version: str = SENSITIVITY_POLICY_VERSION
    position_policy_version: str = POSITION_POLICY_VERSION
    run_receipt_fingerprint: str
    execution_plan_fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class MTAResultSnapshotMetadata(FrozenModel):
    """Compact Firestore twin — no channel arrays or journey bodies."""

    result_snapshot_id: str
    project_id: str
    cycle_id: str
    track_id: str
    run_id: str
    result_status: MTAResultStatus
    evidence_authority: MTAEvidenceAuthority
    fingerprint: str
    models_completed: tuple[str, ...] = ()
    observability_status: ObservabilityStatus | None = None
    generated_at: datetime = Field(default_factory=utc_now)


class MTAResultPointers(FrozenModel):
    track_id: str
    latest_result_snapshot_id: str | None = None
    current_result_snapshot_id: str | None = None
    current_explicit: bool = False


class MTAChannelDetail(FrozenModel):
    channel_id: str
    channel_display_name: str
    observed_role: tuple[str, ...] = ()
    position: MTAChannelPositionEvidence | None = None
    channel_result: MTAChannelResult
    sensitivity: MTAModelSensitivityEvidence | None = None
    markov_removal_effect: float | None = None
    shapley_share: float | None = None
    top_paths_containing_channel: tuple[MTAJourneyPathEvidence, ...] = ()
    limitations: tuple[MTALimitation, ...] = ()
    interpretation: str | None = None
    recommended_next_actions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class MTAResultsCompileError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failure_class: MTAResultsCompileFailureClass = (
            MTAResultsCompileFailureClass.UNKNOWN_ERROR
        ),
    ) -> None:
        super().__init__(message)
        self.failure_class = failure_class

"""Immutable MMM modeling contracts. No Python distribution objects as authority."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import utc_now
from app.modeling.mmm.states import MMMModelingStage


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class KnowledgeClass(StrEnum):
    MERIDIAN_NORMATIVE = "MERIDIAN_NORMATIVE"
    PREM3_DETERMINISTIC_EVIDENCE = "PREM3_DETERMINISTIC_EVIDENCE"
    BUSINESS_CONTEXT = "BUSINESS_CONTEXT"
    HISTORICAL_EXPERIENCE = "HISTORICAL_EXPERIENCE"
    MMM_JUDGMENT = "MMM_JUDGMENT"


class DecisionType(StrEnum):
    MODEL_WINDOW = "MODEL_WINDOW"
    MODEL_SCOPE = "MODEL_SCOPE"
    KPI_TYPE = "KPI_TYPE"
    CONTROL_SELECTION = "CONTROL_SELECTION"
    TREATMENT_CLASSIFICATION = "TREATMENT_CLASSIFICATION"
    MEDIA_PRIOR_TYPE = "MEDIA_PRIOR_TYPE"
    RF_PRIOR_TYPE = "RF_PRIOR_TYPE"
    CUSTOM_PRIOR = "CUSTOM_PRIOR"
    ROI_CALIBRATION_PERIOD = "ROI_CALIBRATION_PERIOD"
    KNOT_STRATEGY = "KNOT_STRATEGY"
    ENABLE_AKS = "ENABLE_AKS"
    MAX_LAG = "MAX_LAG"
    ADSTOCK_DECAY_SPEC = "ADSTOCK_DECAY_SPEC"
    SATURATION_SPEC = "SATURATION_SPEC"
    HILL_BEFORE_ADSTOCK = "HILL_BEFORE_ADSTOCK"
    BASELINE_GEO = "BASELINE_GEO"
    POPULATION_SCALING = "POPULATION_SCALING"
    HOLDOUT = "HOLDOUT"
    MCMC_CONFIGURATION = "MCMC_CONFIGURATION"
    FIT_APPROVAL = "FIT_APPROVAL"
    MODEL_ACCEPTANCE = "MODEL_ACCEPTANCE"


class DecisionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class PriorSource(StrEnum):
    MERIDIAN_DEFAULT = "MERIDIAN_DEFAULT"
    EXPERIMENT = "EXPERIMENT"
    PRIOR_MMM = "PRIOR_MMM"
    INTERNAL_BENCHMARK = "INTERNAL_BENCHMARK"
    EXPERT_JUDGMENT = "EXPERT_JUDGMENT"
    PREM3_RECOMMENDATION = "PREM3_RECOMMENDATION"


class ComputeProfile(StrEnum):
    CPU_TEST = "CPU_TEST"
    CPU_STANDARD = "CPU_STANDARD"
    CPU_LARGE = "CPU_LARGE"
    GPU_STANDARD = "GPU_STANDARD"
    GPU_LARGE = "GPU_LARGE"


class OfficialHealthStatus(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


class PriorValidationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class AcceptanceDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class FitRunStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    FAILED_PRE_FIT = "FAILED_PRE_FIT"
    FAILED_RUNTIME = "FAILED_RUNTIME"
    FAILED_POSTERIOR = "FAILED_POSTERIOR"
    FAILED_REVIEW = "FAILED_REVIEW"
    CANCELED = "CANCELED"


class FitFailureClass(StrEnum):
    MODEL_SPEC_IDENTIFIABILITY_ERROR = "MODEL_SPEC_IDENTIFIABILITY_ERROR"
    MODEL_SPEC_VALIDATION_ERROR = "MODEL_SPEC_VALIDATION_ERROR"
    PRIOR_VALIDATION_ERROR = "PRIOR_VALIDATION_ERROR"
    INPUT_CONTRACT_ERROR = "INPUT_CONTRACT_ERROR"
    SERIALIZATION_ERROR = "SERIALIZATION_ERROR"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    MERIDIAN_RUNTIME_ERROR = "MERIDIAN_RUNTIME_ERROR"
    POSTERIOR_SAMPLING_ERROR = "POSTERIOR_SAMPLING_ERROR"
    OFFICIAL_REVIEW_ERROR = "OFFICIAL_REVIEW_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class FitFailureStage(StrEnum):
    MODEL_INITIALIZATION = "MODEL_INITIALIZATION"
    SERIALIZATION = "SERIALIZATION"
    POSTERIOR_SAMPLING = "POSTERIOR_SAMPLING"
    OFFICIAL_REVIEW = "OFFICIAL_REVIEW"
    DISPATCH = "DISPATCH"
    UNKNOWN = "UNKNOWN"


class RetrySemantics(StrEnum):
    EXACT_RETRY_ALLOWED = "EXACT_RETRY_ALLOWED"
    NEW_FIT_PLAN_REQUIRED = "NEW_FIT_PLAN_REQUIRED"
    NEW_MODEL_DESIGN_REQUIRED = "NEW_MODEL_DESIGN_REQUIRED"
    NOT_RETRYABLE = "NOT_RETRYABLE"


class FitNextActionType(StrEnum):
    REVIEW_MODEL_IDENTIFIABILITY = "REVIEW_MODEL_IDENTIFIABILITY"
    REVIEW_MODEL_SPEC = "REVIEW_MODEL_SPEC"


class FitDispatchOutcome(StrEnum):
    SUCCESSFULLY_LAUNCHED = "SUCCESSFULLY_LAUNCHED"
    LAUNCH_FAILED = "LAUNCH_FAILED"


class MeridianRuntimeMode(StrEnum):
    FAKE_TEST = "FAKE_TEST"
    OFFICIAL_CPU_SMOKE = "OFFICIAL_CPU_SMOKE"
    OFFICIAL_CPU = "OFFICIAL_CPU"
    OFFICIAL_GPU = "OFFICIAL_GPU"


PRODUCTION_OFFICIAL_RUNTIME_MODES = frozenset(
    {MeridianRuntimeMode.OFFICIAL_CPU, MeridianRuntimeMode.OFFICIAL_GPU}
)
QUALIFICATION_RUNTIME_MODES = frozenset(
    {MeridianRuntimeMode.FAKE_TEST, MeridianRuntimeMode.OFFICIAL_CPU_SMOKE}
)


class FitPurpose(StrEnum):
    RUNTIME_QUALIFICATION = "RUNTIME_QUALIFICATION"
    MODEL_ITERATION = "MODEL_ITERATION"
    FINAL_MODEL = "FINAL_MODEL"


class ReviewSource(StrEnum):
    FAKE_TEST = "FAKE_TEST"
    OFFICIAL_MERIDIAN = "OFFICIAL_MERIDIAN"


class FitDispatchStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class LedgerPublicationStatus(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    VERIFIED = "VERIFIED"
    PENDING_PUBLICATION = "PENDING_PUBLICATION"
    FAILED = "FAILED"


class DecisionIntelligenceAuthority(StrEnum):
    VERIFIED = "VERIFIED"
    INTERPRETATION = "INTERPRETATION"
    RECOMMENDATION = "RECOMMENDATION"
    DECISION_REQUIRED = "DECISION_REQUIRED"


class NormativeSourceKind(StrEnum):
    PINNED_REPO_SOURCE = "PINNED_REPO_SOURCE"
    OFFICIAL_MERIDIAN_WEB_DOC = "OFFICIAL_MERIDIAN_WEB_DOC"
    PREM3_CURATED_MERIDIAN_CONTEXT = "PREM3_CURATED_MERIDIAN_CONTEXT"


class Recommendation(FrozenModel):
    proposal: Any
    reason: str
    evidence_refs: tuple[str, ...] = ()
    knowledge_asset_refs: tuple[str, ...] = ()
    authority: KnowledgeClass = KnowledgeClass.MMM_JUDGMENT
    requires_approval: bool = True


class PriorSpec(FrozenModel):
    parameter: str
    distribution_family: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    channels: tuple[str, ...] = ()
    source: PriorSource = PriorSource.MERIDIAN_DEFAULT
    evidence_refs: tuple[str, ...] = ()
    rationale: str | None = None


class MeridianModelSpecProposal(FrozenModel):
    media_effects_dist: str = "log_normal"
    hill_before_adstock: bool = False
    max_lag: int = 8
    unique_sigma_for_each_geo: bool = False
    media_prior_type: str = "roi"
    rf_prior_type: str = "roi"
    roi_calibration_period: list[list[bool]] | None = None
    rf_roi_calibration_period: list[list[bool]] | None = None
    organic_media_prior_type: str = "contribution"
    organic_rf_prior_type: str = "contribution"
    non_media_treatments_prior_type: str = "contribution"
    non_media_baseline_values: list[float | str] | None = None
    knots: int | list[int] | None = None
    baseline_geo: int | str | None = None
    holdout_id: list[bool] | list[list[bool]] | None = None
    control_population_scaling_id: list[bool] | None = None
    non_media_population_scaling_id: list[bool] | None = None
    adstock_decay_spec: str | dict[str, str] = "geometric"
    saturation_spec: str | dict[str, str] = "hill"
    enable_aks: bool = False
    paid_media_prior_type: str | None = None


class CompiledMeridianModelSpec(FrozenModel):
    spec: MeridianModelSpecProposal
    priors: tuple[PriorSpec, ...] = ()
    fingerprint: str
    meridian_version: str
    compatibility_status: str


class ModelPlan(FrozenModel):
    model_plan_id: str
    model_version_id: str
    model_ready_run_id: str
    model_ready_manifest_fingerprint: str
    business_profile_snapshot_id: str | None = None
    meridian_version: str = "1.8.0"
    model_window_start: str
    model_window_end: str
    scope: str
    spec: MeridianModelSpecProposal
    priors: tuple[PriorSpec, ...] = ()
    mcmc: dict[str, Any] = Field(default_factory=dict)
    compute_profile: ComputeProfile = ComputeProfile.GPU_STANDARD
    rf_channels: tuple[str, ...] = ()
    media_channels: tuple[str, ...] = ()
    fingerprint: str


class ModelDecision(FrozenModel):
    decision_id: str
    model_version_id: str
    tenant_id: str
    project_id: str
    decision_type: DecisionType
    proposal: Any
    authority: KnowledgeClass
    evidence_refs: tuple[str, ...] = ()
    knowledge_asset_refs: tuple[str, ...] = ()
    recommended_value: Any = None
    chosen_value: Any = None
    reason: str | None = None
    requires_approval: bool = True
    status: DecisionStatus = DecisionStatus.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    plan_fingerprint: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ModelReadyCoverage(FrozenModel):
    earliest_time: str
    latest_time: str
    n_times: int
    n_geos: int
    n_treatments: int = 0
    n_controls: int = 0
    geos: tuple[str, ...] = ()
    source: str | None = None
    shared_usable_historical_coverage: str | None = None
    channel_limiting_coverage: dict[str, str] = Field(default_factory=dict)


class MMMModelVersion(FrozenModel):
    model_version_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    model_ready_run_id: str
    model_ready_manifest_ref: str | None = None
    model_ready_manifest_fingerprint: str
    business_profile_snapshot_id: str | None = None
    foundation_fingerprint: str | None = None
    meridian_version: str = "1.8.0"
    model_plan_id: str | None = None
    model_plan_fingerprint: str | None = None
    model_window_start: str | None = None
    model_window_end: str | None = None
    version: int = 1
    supersedes_model_version_id: str | None = None
    iteration_reason: str | None = None
    triggering_review_refs: tuple[str, ...] = ()
    changed_decision_ids: tuple[str, ...] = ()
    state: MMMModelingStage = MMMModelingStage.DESIGNING_MODEL
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str
    accepted: bool = False


class DesignBriefSection(FrozenModel):
    name: str
    recommendation: Recommendation


class MMMModelDesignBrief(FrozenModel):
    model_version_id: str
    model_objective: str
    kpi_treatment: str
    geo_vs_national: str
    final_model_window: str
    paid_media_treatments: tuple[str, ...] = ()
    rf_treatments: tuple[str, ...] = ()
    organic_media: tuple[str, ...] = ()
    non_media_treatments: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    time_effect_strategy: str
    prior_strategy: str
    calibration_evidence: tuple[str, ...] = ()
    adstock_strategy: str
    saturation_strategy: str
    population_scaling: str
    holdout_strategy: str
    mcmc_recommendation: dict[str, Any] = Field(default_factory=dict)
    known_limitations: tuple[str, ...] = ()
    decisions_requiring_human_input: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    sections: tuple[DesignBriefSection, ...] = ()
    candidate_window: str | None = None
    n_times: int | None = None
    n_geos: int | None = None
    n_treatments: int | None = None
    n_controls: int | None = None
    adequacy_evidence: tuple[str, ...] = ()
    generated_at: datetime = Field(default_factory=utc_now)


class MeridianPriorValidationReceipt(FrozenModel):
    model_version_id: str
    model_plan_fingerprint: str
    meridian_version: str
    prior_config_fingerprint: str
    n_draws: int
    seed: int
    status: PriorValidationStatus
    runtime_mode: MeridianRuntimeMode = MeridianRuntimeMode.FAKE_TEST
    artifact_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    generated_at: datetime = Field(default_factory=utc_now)


class MeridianFitPlan(FrozenModel):
    model_version_id: str
    model_plan_fingerprint: str
    meridian_version: str
    container_image_digest: str | None = None
    source_commit_sha: str | None = None
    worker_build_id: str | None = None
    python_version: str | None = None
    tensorflow_version: str | None = None
    backend: str = "tensorflow"
    n_chains: int
    n_adapt: int
    n_burnin: int
    n_keep: int
    seed: int
    reconstruction_batch_size: int | None = None
    n_chains_schedule: tuple[int, ...] | None = None
    compute_profile: ComputeProfile
    fit_purpose: FitPurpose = FitPurpose.MODEL_ITERATION
    artifact_destinations: dict[str, str] = Field(default_factory=dict)
    input_artifact_ref: str | None = None
    input_fingerprint: str
    created_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class FitApproval(FrozenModel):
    approval_id: str
    model_version_id: str
    tenant_id: str
    project_id: str
    fit_plan_fingerprint: str
    model_plan_fingerprint: str
    approved_by: str
    approved_at: datetime
    superseded: bool = False


class FitRun(FrozenModel):
    fit_run_id: str
    model_version_id: str
    tenant_id: str
    project_id: str
    fit_plan_fingerprint: str
    status: FitRunStatus = FitRunStatus.PENDING
    compute_profile: ComputeProfile
    runtime_mode: MeridianRuntimeMode = MeridianRuntimeMode.FAKE_TEST
    fit_purpose: FitPurpose = FitPurpose.MODEL_ITERATION
    python_version: str | None = None
    meridian_version: str | None = None
    tensorflow_version: str | None = None
    worker_image_digest: str | None = None
    source_commit_sha: str | None = None
    worker_build_id: str | None = None
    dispatch_id: str | None = None
    attempt: int = 1
    ledger_readback_verified: bool = False
    ledger_status: LedgerPublicationStatus = LedgerPublicationStatus.NOT_ATTEMPTED
    error_code: str | None = None
    failure_class: FitFailureClass | None = None
    failure_stage: FitFailureStage | None = None
    sampling_started: bool | None = None
    retry_semantics: RetrySemantics | None = None
    library: str | None = None
    library_version: str | None = None
    exception_type: str | None = None
    official_message: str | None = None
    prem3_summary: str | None = None
    next_actions: tuple[str, ...] = ()
    dispatch_outcome: FitDispatchOutcome | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MeridianModelArtifactManifest(FrozenModel):
    model_version_id: str
    fit_run_id: str
    meridian_version: str
    worker_image_digest: str | None = None
    input_manifest_ref: str | None = None
    input_fingerprint: str
    model_plan_fingerprint: str
    fit_plan_fingerprint: str
    binary_model_ref: str
    binary_sha256: str
    runtime_mode: MeridianRuntimeMode = MeridianRuntimeMode.FAKE_TEST
    serde_readback_ok: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class OfficialCheckResult(FrozenModel):
    check_name: str
    status: OfficialHealthStatus
    summary: str | None = None


class MeridianModelHealthReceipt(FrozenModel):
    model_version_id: str
    fit_run_id: str
    reviewer_version: str
    meridian_version: str
    overall_health_score: float | None = None
    check_results: tuple[OfficialCheckResult, ...] = ()
    blocking_fail_count: int = 0
    review_count: int = 0
    health_html_ref: str | None = None
    health_html_sha256: str | None = None
    runtime_mode: MeridianRuntimeMode = MeridianRuntimeMode.FAKE_TEST
    review_source: ReviewSource = ReviewSource.FAKE_TEST
    generated_at: datetime = Field(default_factory=utc_now)


class ResultsSummary(FrozenModel):
    html_ref: str | None = None
    html_sha256: str | None = None
    requested_date_range: str | None = None
    effective_date_range: str | None = None
    model_fit: dict[str, Any] = Field(default_factory=dict)
    incremental_outcomes: dict[str, Any] = Field(default_factory=dict)
    channel_contribution: dict[str, Any] = Field(default_factory=dict)
    roi: dict[str, Any] = Field(default_factory=dict)
    mroi: dict[str, Any] = Field(default_factory=dict)
    response_curve_metadata: dict[str, Any] = Field(default_factory=dict)
    baseline: dict[str, Any] = Field(default_factory=dict)
    adstock_saturation: dict[str, Any] = Field(default_factory=dict)


class MMMModelReviewPack(FrozenModel):
    model_version_id: str
    fit_run_id: str
    model_spec_summary: dict[str, Any] = Field(default_factory=dict)
    prior_summary: dict[str, Any] = Field(default_factory=dict)
    mcmc_summary: dict[str, Any] = Field(default_factory=dict)
    official_health: MeridianModelHealthReceipt | None = None
    results: ResultsSummary | None = None
    business_iq_assumptions: tuple[str, ...] = ()
    known_limitations: tuple[str, ...] = ()
    review_required_items: tuple[str, ...] = ()
    acknowledged_review_items: tuple[str, ...] = ()
    agent_interpretation: str | None = None
    recommended_next_action: str | None = None
    evidence_refs: tuple[str, ...] = ()
    fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)


class ModelAcceptanceApproval(FrozenModel):
    approval_id: str
    model_version_id: str
    fit_run_id: str
    tenant_id: str
    project_id: str
    review_pack_fingerprint: str
    model_artifact_fingerprint: str
    approved_by: str
    approved_at: datetime
    decision: AcceptanceDecision
    reason: str | None = None


class MMMReproducibilityManifest(FrozenModel):
    project_id: str
    cycle_id: str
    track_id: str
    business_profile_snapshot_id: str | None = None
    model_ready_manifest_fingerprint: str
    model_plan_fingerprint: str
    decision_ids: tuple[str, ...] = ()
    meridian_version: str
    external_knowledge_asset_versions: tuple[str, ...] = ()
    worker_image_digest: str | None = None
    fit_configuration: dict[str, Any] = Field(default_factory=dict)
    model_artifact_hash: str | None = None
    review_artifact_refs: tuple[str, ...] = ()
    acceptance_approval_id: str | None = None


class ModelingReceipt(FrozenModel):
    receipt_type: str
    model_version_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=utc_now)


class NormativeRecommendation(FrozenModel):
    topic: str
    recommendation: str
    source_refs: tuple[str, ...] = ()
    upstream_asset_version: str
    meridian_version: str
    source_kind: NormativeSourceKind
    available: bool = True


class MeridianFitDispatch(FrozenModel):
    dispatch_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    model_version_id: str
    fit_run_id: str
    fit_plan_fingerprint: str
    fit_approval_id: str
    runtime_mode: MeridianRuntimeMode
    compute_profile: ComputeProfile
    status: FitDispatchStatus = FitDispatchStatus.PENDING
    launch_outcome: FitDispatchOutcome | None = None
    cloud_task_name: str | None = None
    cloud_run_execution_name: str | None = None
    attempt: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DecisionIntelligenceRecommendation(FrozenModel):
    recommendation_id: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    counterevidence_refs: tuple[str, ...] = ()
    uncertainty: str | None = None
    recommended_action: str | None = None
    requires_human_decision: bool = True
    authority: DecisionIntelligenceAuthority = DecisionIntelligenceAuthority.RECOMMENDATION


class MMMDecisionIntelligenceBrief(FrozenModel):
    model_version_id: str
    fit_run_id: str | None = None
    headline: str
    summary: str
    verified_findings: tuple[str, ...] = ()
    review_items: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    recommendations: tuple[DecisionIntelligenceRecommendation, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    model_health_receipt_ref: str | None = None
    review_pack_ref: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)

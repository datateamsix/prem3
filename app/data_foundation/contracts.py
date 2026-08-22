"""Typed Data Foundation contracts. No untyped authority dictionaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.data_foundation.enums import (
    AlignmentVerdict,
    CandidateGroup,
    ConfirmationClass,
    ConnectionLifecycle,
    ConsequenceClass,
    CoverageBucketState,
    CoverageGapCategory,
    CoverageState,
    CoverageView,
    CutoffOrigin,
    CycleCadence,
    DataFoundationReadyStatus,
    EvidenceRequirementType,
    ExecutionStatus,
    FoundationPlanSection,
    LocationType,
    PeriodStatus,
    PlanActionKind,
    PreviewMode,
    ProvenanceClass,
    ProviderProvisionerState,
    QualityFamily,
    QualityStatus,
    RowCountKind,
    ScopeProvenance,
    SourceFoundationStatus,
    TargetWindowStatus,
    TransformAuthority,
    TransformId,
)

RULE_VERSION = "data-foundation/quality/v1"
REGISTRY_CONTRACT_VERSION = "marketing_advertising_providers.v1"
PLAN_CONTRACT_VERSION = "data-foundation/plan/v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BusinessChannelFact(FrozenModel):
    channel_name: str
    role: str | None = None
    material: bool = True


class BusinessEventFact(FrozenModel):
    event_type: str
    name: str
    start_date: str | None = None
    end_date: str | None = None
    note: str | None = None


class PriorEvidenceFact(FrozenModel):
    evidence_type: str
    summary: str
    artifact_hint: str | None = None


class BusinessProfileSnapshot(FrozenModel):
    """Port for future Business IQ persistence. This branch does not write BIQ."""

    snapshot_id: str
    tenant_id: str
    workspace_id: str
    version: str
    fingerprint: str
    business_context_ready: bool
    kpi: str
    kpi_definition: str | None = None
    objective: str | None = None
    markets: tuple[str, ...] = ()
    channels: tuple[BusinessChannelFact, ...] = ()
    promotions_relevant: bool | None = None
    inventory_relevant: bool | None = None
    competition_relevant: bool | None = None
    seasonality_relevant: bool | None = None
    events: tuple[BusinessEventFact, ...] = ()
    prior_evidence: tuple[PriorEvidenceFact, ...] = ()
    unknowns: tuple[str, ...] = ()


class EvidenceRequirement(FrozenModel):
    requirement_id: str
    requirement_type: EvidenceRequirementType
    concept: str
    business_role: str
    channel_id: str | None = None
    market_scope: tuple[str, ...] = ()
    expected_category: str
    downstream_use: tuple[str, ...] = ()
    source_fact_ids: tuple[str, ...] = ()
    acknowledged_unknown: bool = False
    coverage_state: CoverageState = CoverageState.SOURCE_NOT_COLLECTED
    confirmation: ConfirmationClass = ConfirmationClass.NONE


class EvidenceRequirementSet(FrozenModel):
    tenant_id: str
    workspace_id: str
    snapshot_id: str
    snapshot_fingerprint: str
    compiled_at: datetime
    requirements: tuple[EvidenceRequirement, ...]


class DriveFoundationLayout(FrozenModel):
    tenant_id: str
    workspace_id: str
    root_folder_id: str
    sources_folder_id: str | None = None
    business_data_folder_id: str | None = None
    evidence_folder_id: str | None = None
    system_folder_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionView(FrozenModel):
    plane: str
    required: bool
    lifecycle: ConnectionLifecycle
    connection_id: str | None = None
    binding_summary: str | None = None


class ResourceIdentity(FrozenModel):
    location_type: LocationType
    project_id: str | None = None
    dataset_id: str | None = None
    table_id: str | None = None
    drive_file_id: str | None = None
    drive_folder_id: str | None = None
    logical_path: str | None = None


class ProviderMatchEvidence(FrozenModel):
    provider_id: str | None
    registry_version: str
    score: float
    signals: tuple[str, ...]
    provenance: ProvenanceClass


class SourceCandidate(FrozenModel):
    candidate_id: str
    tenant_id: str
    workspace_id: str
    evidence_requirement_id: str | None
    location_type: LocationType
    resource: ResourceIdentity
    group: CandidateGroup
    provider_candidate: str | None = None
    provider_match: ProviderMatchEvidence | None = None
    history_summary: str | None = None
    freshness_summary: str | None = None
    grain_summary: str | None = None
    geo_summary: str | None = None
    metric_summary: str | None = None
    lineage_summary: str | None = None
    quality_summary: str | None = None
    authority: ProvenanceClass = ProvenanceClass.DETECTED


class SourceCoverageInventory(FrozenModel):
    tenant_id: str
    workspace_id: str
    requirements: tuple[EvidenceRequirement, ...]
    candidates: tuple[SourceCandidate, ...]
    verified: tuple[str, ...]
    likely: tuple[str, ...]
    needs_decision: tuple[str, ...]
    excluded: tuple[str, ...]


class SourceContract(FrozenModel):
    grain: str | None = None
    date_field: str | None = None
    date_format: str | None = None
    geo_field: str | None = None
    currency: str | None = None
    timezone: str | None = None
    unique_keys: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    summable_fields: tuple[str, ...] = ()
    schema_fingerprint: str | None = None


class SourceBinding(FrozenModel):
    source_id: str
    tenant_id: str
    workspace_id: str
    requirement_id: str | None
    provider_id: str | None
    location_type: LocationType
    resource: ResourceIdentity
    contract: SourceContract
    canonical: bool = True
    historical_role: str | None = None
    ongoing_role: str | None = None
    lifecycle_state: str
    governance_import_ready: bool = False
    created_at: datetime
    updated_at: datetime


class QualityCheckResult(FrozenModel):
    check_id: str
    check_family: QualityFamily
    status: QualityStatus
    severity: ConsequenceClass
    consequence: ConsequenceClass
    source_id: str
    field_ids: tuple[str, ...] = ()
    observed_count: int | None = None
    observed_rate: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    rule_version: str = RULE_VERSION
    executed_at: datetime


class QualityFinding(FrozenModel):
    finding_id: str
    source_id: str
    check_id: str
    status: QualityStatus
    consequence: ConsequenceClass
    observed_fact: str
    agent_interpretation: str | None = None
    field_ids: tuple[str, ...] = ()


class QualityOverview(FrozenModel):
    source_id: str
    blocker_count: int
    review_count: int
    advisory_count: int
    pass_count: int
    findings: tuple[QualityFinding, ...]


class OperationalHealthAssessment(FrozenModel):
    access_works: bool
    expected_cadence: str | None = None
    observed_cadence: str | None = None
    last_successful_load: str | None = None
    source_event_time: str | None = None
    ingestion_event_time: str | None = None
    authorization_state: ConnectionLifecycle
    late_arrival_watermark: str | None = None
    freshness_known: bool
    status: QualityStatus


class ContractStructureAssessment(FrozenModel):
    required_fields_present: bool
    unexpected_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    expected_grain: str | None = None
    observed_grain: str | None = None
    schema_fingerprint: str
    currency_known: bool
    timezone_known: bool
    status: QualityStatus


class DataQualityAssessment(FrozenModel):
    checks: tuple[QualityCheckResult, ...]
    status: QualityStatus


class MeasurementCoverageAssessment(FrozenModel):
    history_periods: int | None = None
    missing_periods: tuple[str, ...] = ()
    period_statuses: tuple[tuple[str, PeriodStatus], ...] = ()
    geo_summary: str | None = None
    metric_summary: str | None = None
    status: QualityStatus


class SourceAssessment(FrozenModel):
    source_id: str
    registry_version: str
    operational: OperationalHealthAssessment
    contract: ContractStructureAssessment
    quality: DataQualityAssessment
    coverage: MeasurementCoverageAssessment
    overall_status: QualityStatus
    assessed_at: datetime


class AlignmentRow(FrozenModel):
    dimension: str
    kpi_value: str
    media_value: str
    verdict: AlignmentVerdict
    note: str
    consequence: ConsequenceClass = ConsequenceClass.ADVISORY


class CrossSourceAlignmentAssessment(FrozenModel):
    workspace_id: str
    common_window: str | None
    rows: tuple[AlignmentRow, ...]
    assessed_at: datetime


class TransformationAction(FrozenModel):
    action_id: TransformId
    authority: TransformAuthority
    field_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason_finding_ids: tuple[str, ...] = ()
    lossy: bool = False


class TransformationPlan(FrozenModel):
    plan_id: str
    version: int
    source_id: str
    source_fingerprint: str
    registry_version: str
    actions: tuple[TransformationAction, ...]
    source_grain: str | None = None
    target_grain: str | None = None
    projected_row_delta: int | None = None
    lossy: bool
    missingness_behavior: str
    reconciliation_required: bool
    requires_approval: bool
    output_target: str
    fingerprint: str
    created_at: datetime
    immutable: bool = True


class TransformationPreview(FrozenModel):
    preview_id: str
    plan_id: str
    plan_fingerprint: str
    input_rows: int
    input_schema_fingerprint: str
    input_content_fingerprint: str
    projected_output_rows: int
    projected_schema: tuple[str, ...]
    projected_grain: str | None
    preserved_unknowns: tuple[str, ...]
    warnings: tuple[str, ...]
    requires_user_decision: tuple[str, ...]
    mutated_source: bool = False
    source_preview_id: str | None = None
    proposed_output_preview_id: str | None = None
    actions: tuple[str, ...] = ()
    authority: tuple[str, ...] = ()
    row_delta: int | None = None
    schema_before: tuple[str, ...] = ()
    schema_after: tuple[str, ...] = ()
    grain_before: str | None = None
    grain_after: str | None = None
    partitioning_proposed: str | None = None
    clustering_proposed: tuple[str, ...] = ()
    unknowns_preserved: tuple[str, ...] = ()
    raw_source_unchanged: bool = True


class FoundationPlanAction(FrozenModel):
    action_kind: PlanActionKind
    section: FoundationPlanSection
    resource_type: str
    target: str
    reason: str
    dependencies: tuple[str, ...] = ()
    permission_requirements: tuple[str, ...] = ()
    validation_method: str


class FoundationPlan(FrozenModel):
    plan_id: str
    version: int
    tenant_id: str
    workspace_id: str
    fingerprint: str
    actions: tuple[FoundationPlanAction, ...]
    created_at: datetime
    immutable: bool = True
    will_not_modify: tuple[str, ...] = ()
    permission_preview: tuple[str, ...] = ()
    domains: tuple[FoundationPlanSection, ...] = tuple(FoundationPlanSection)


class FoundationApproval(FrozenModel):
    approval_id: str
    plan_id: str
    plan_fingerprint: str
    tenant_id: str
    workspace_id: str
    approved_sections: tuple[FoundationPlanSection, ...]
    approved_by: str
    approved_at: datetime
    superseded: bool = False


class ProvisioningStep(FrozenModel):
    name: str
    status: ExecutionStatus
    detail: str


class ProvisioningRun(FrozenModel):
    run_id: str
    plan_id: str
    plan_fingerprint: str
    steps: tuple[ProvisioningStep, ...]
    status: ExecutionStatus


class QueryBudgetPolicy(FrozenModel):
    max_bytes_scanned: int = 100_000_000
    timeout_seconds: int = 30
    sample_limit: int = 10_000
    require_partition_predicate: bool = True
    allow_select_star: bool = False
    allow_arbitrary_sql: bool = False


class CompiledQuery(FrozenModel):
    operation: str
    sql: str
    labels: dict[str, str]
    estimated_bytes: int | None = None
    partition_predicate: str | None = None


class DriveFileRecord(FrozenModel):
    drive_file_id: str
    original_name: str
    canonical_logical_name: str | None = None
    parent_folder_id: str
    source_slug: str | None = None
    file_fingerprint: str
    mime_type: str
    size: int
    modified_time: str | None = None
    discovered_at: datetime
    registered_at: datetime | None = None


class FileSeriesCandidate(FrozenModel):
    series_id: str
    source_slug: str
    parent_folder_id: str
    file_ids: tuple[str, ...]
    schema_versions: int
    overlapping_periods: int
    confidence: float
    evidence: tuple[str, ...]


class SourceContinuityPlan(FrozenModel):
    historical_source_id: str
    ongoing_source_id: str
    cutoff: str
    overlap_handling: str
    reconciliation_required: bool
    canonical_precedence: str
    workspace_id: str | None = None


class UserDecision(FrozenModel):
    decision_id: str
    source_id: str
    kind: str
    value: str
    recorded_at: datetime


class ReceiptBase(FrozenModel):
    receipt_id: str
    tenant_id: str
    workspace_id: str
    source_ids: tuple[str, ...]
    plan_id: str | None = None
    plan_version: int | None = None
    input_fingerprints: dict[str, str] = Field(default_factory=dict)
    output_fingerprints: dict[str, str] = Field(default_factory=dict)
    rule_versions: tuple[str, ...] = ()
    executed_at: datetime
    executed_by: str
    status: str
    unresolved_findings: tuple[str, ...] = ()


class SourceAssessmentReceipt(ReceiptBase):
    assessment_status: QualityStatus


class DataQualityReceipt(ReceiptBase):
    blocker_count: int
    review_count: int


class TransformationReceipt(ReceiptBase):
    applied_actions: tuple[str, ...]
    input_rows: int
    output_rows: int
    source_mutated: bool


class DriveImportReceipt(ReceiptBase):
    files_evaluated: int
    files_accepted: int
    files_rejected: int
    destination: str
    raw_files_modified: bool


class FoundationProvisioningReceipt(ReceiptBase):
    created: tuple[str, ...]
    reused: tuple[str, ...]
    untouched: tuple[str, ...]
    remaining: tuple[str, ...]


class SourceFoundationReceipt(ReceiptBase):
    """Stricter DF source gate. Does not emit M2-11 IMPORT_READY."""

    status_code: SourceFoundationStatus
    governance_import_ready: bool
    premodel_review_remaining: bool
    premodel_review_findings: tuple[str, ...] = ()


class DataFoundationReadyReceipt(ReceiptBase):
    status_code: DataFoundationReadyStatus
    required_sources_ready: int
    typed_exceptions: tuple[str, ...] = ()
    m2_11_import_ready: bool = False
    foundation_source_ready_count: int = 0


class PrerequisiteNotice(FrozenModel):
    provider_id: str
    state: ProviderProvisionerState
    prerequisite: str
    prem3_can: tuple[str, ...]
    customer_must: tuple[str, ...]


class DataFoundationOverview(FrozenModel):
    workspace_id: str
    phase: str
    connections: tuple[ConnectionView, ...]
    requirement_count: int
    candidate_count: int
    source_ready_count: int
    foundation_ready: bool
    live_cloud_proof: str


class DiscoveryHints(FrozenModel):
    tenant_id: str
    workspace_id: str
    datasets_to_prioritize: tuple[str, ...] = ()
    only_inspect_prioritized_datasets: bool = False
    drive_sources_or_paths_to_prioritize: tuple[str, ...] = ()
    persisted_at: datetime | None = None


class SourceScope(FrozenModel):
    market_scope: tuple[str, ...] = ()
    geo_level: str | None = None
    geo_field: str | None = None
    geo_values_summary: str | None = None
    provenance: ScopeProvenance = ScopeProvenance.UNKNOWN
    filename_inferred: bool = False
    filename_has_authority: bool = False


class PhysicalMetadata(FrozenModel):
    object_type: str
    row_count: int | None = None
    row_count_kind: RowCountKind = RowCountKind.UNKNOWN
    column_count: int | None = None
    table_size_bytes: int | None = None
    dataset_location: str | None = None
    last_modified: str | None = None
    partitioning_type: str | None = None
    partitioning_field: str | None = None
    partition_count: int | None = None
    clustering_fields: tuple[str, ...] = ()
    file_count: int | None = None
    schema_versions: tuple[str, ...] = ()
    date_range: str | None = None
    latest_file_at: str | None = None
    folder_path: str | None = None
    view_lineage: str | None = None


class DataPreviewRow(FrozenModel):
    values: dict[str, Any]


class DataPreview(FrozenModel):
    preview_id: str
    mode: PreviewMode
    source_id: str | None = None
    compiled_sql: str | None = None
    row_selection: str
    rows: tuple[DataPreviewRow, ...]
    masked_fields: tuple[str, ...] = ()
    omitted_fields: tuple[str, ...] = ()
    contributing_file: str | None = None
    original_filename: str | None = None
    estimated_bytes: int | None = None
    verified_time_field: str | None = None


class CanonicalPreview(FrozenModel):
    preview_id: str
    output_resource: str
    actual_row_count: int
    actual_schema: tuple[str, ...]
    partitioning: str | None = None
    clustering: tuple[str, ...] = ()
    quality_summary: str | None = None
    reconciliation_summary: str | None = None
    latest_rows: tuple[DataPreviewRow, ...]
    receipt_id: str | None = None


class MeasurementCycle(FrozenModel):
    cycle_id: str
    tenant_id: str
    workspace_id: str
    name: str
    cadence: CycleCadence
    data_cutoff: str | None = None
    cutoff_origin: CutoffOrigin | None = None
    target_window_start: str | None = None
    target_window_end: str | None = None
    target_window_status: TargetWindowStatus = TargetWindowStatus.PROVISIONAL
    business_profile_snapshot_id: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    state: str = "OPEN"
    predecessor_cycle_id: str | None = None
    revision: int = 1


class CoverageBucket(FrozenModel):
    period: str
    state: CoverageBucketState
    expected: bool
    observed: bool
    valid_zero: bool = False
    source_ids: tuple[str, ...] = ()


class CoverageSeries(FrozenModel):
    series_id: str
    requirement_id: str | None
    source_id: str | None
    concept: str
    grain: str = "MONTH"
    buckets: tuple[CoverageBucket, ...]
    observed_span: str | None = None
    continuous_span: str | None = None
    most_recent_continuous_span: str | None = None
    longest_gap: str | None = None
    latest_observed_period: str | None = None


class CoverageGap(FrozenModel):
    gap_id: str
    category: CoverageGapCategory
    period: str
    requirement_id: str | None = None
    expected_business_state: str
    observed_data_state: str
    source_health: str
    evidence_refs: tuple[str, ...] = ()
    recommended_next_action: str


class CoverageSummary(FrozenModel):
    required_sources_meeting_target: int
    continuity_issue_count: int
    shared_continuous_window: str | None
    shared_continuous_window_start: str | None
    shared_continuous_window_end: str | None
    most_limiting_requirement: str | None
    target_window_coverage: str | None = None


class CoverageAssessment(FrozenModel):
    tenant_id: str
    workspace_id: str
    cycle_id: str
    view: CoverageView
    series: tuple[CoverageSeries, ...]
    gaps: tuple[CoverageGap, ...]
    summary: CoverageSummary
    assessed_at: datetime


class IntelligenceBriefSection(FrozenModel):
    heading: str
    body: str
    evidence_refs: tuple[str, ...] = ()


class DataIntelligenceBrief(FrozenModel):
    brief_id: str
    tenant_id: str
    workspace_id: str
    generated_at: datetime
    model_version: str
    what_prem3_found: IntelligenceBriefSection
    data_quality_findings: IntelligenceBriefSection
    prem3_can_mend: IntelligenceBriefSection
    needs_your_decision: IntelligenceBriefSection
    carries_into_premodeling: IntelligenceBriefSection
    evidence_refs: tuple[str, ...]
    advisory: bool = True

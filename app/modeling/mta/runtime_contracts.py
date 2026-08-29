"""M5-01 runtime contracts — execution, refresh, receipts, failures."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.core.contracts import utc_now
from app.modeling.mta.contracts import (
    AttributionModelId,
    ConversionValueStrategy,
    DirectTreatmentPolicy,
    FrozenModel,
    IdentityStrategy,
    JourneyDefinition,
    SessionizationPolicy,
    SessionTrafficSourcePolicy,
)


class MTAComputationAuthority(StrEnum):
    REAL_PINNED_RUNTIME = "REAL_PINNED_RUNTIME"
    TEST_FAKE_RUNTIME = "TEST_FAKE_RUNTIME"


class MTAInputMode(StrEnum):
    RAW_JOURNEYS = "RAW_JOURNEYS"
    GROUPED_PATH_FREQUENCY = "GROUPED_PATH_FREQUENCY"


class MTADispatchStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    LAUNCHED = "LAUNCHED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class MTARunStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class MTAFailureClass(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_SCHEMA_ERROR = "SOURCE_SCHEMA_ERROR"
    JOURNEY_COMPILATION_ERROR = "JOURNEY_COMPILATION_ERROR"
    CHANNEL_GROUPING_ERROR = "CHANNEL_GROUPING_ERROR"
    INPUT_VALIDATION_ERROR = "INPUT_VALIDATION_ERROR"
    DP6_CONFIGURATION_ERROR = "DP6_CONFIGURATION_ERROR"
    DP6_RUNTIME_ERROR = "DP6_RUNTIME_ERROR"
    MARKOV_ERROR = "MARKOV_ERROR"
    SHAPLEY_ERROR = "SHAPLEY_ERROR"
    BIGQUERY_WRITE_ERROR = "BIGQUERY_WRITE_ERROR"
    BIGQUERY_READBACK_ERROR = "BIGQUERY_READBACK_ERROR"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    MTA_RUNTIME_INPUT_ERROR = "MTA_RUNTIME_INPUT_ERROR"
    MTA_RUNTIME_DP6_API_ERROR = "MTA_RUNTIME_DP6_API_ERROR"
    MTA_RUNTIME_MODEL_ERROR = "MTA_RUNTIME_MODEL_ERROR"
    MTA_RUNTIME_INVALID_OUTPUT = "MTA_RUNTIME_INVALID_OUTPUT"
    MTA_RUNTIME_SHAPLEY_PREFLIGHT_BLOCKED = "MTA_RUNTIME_SHAPLEY_PREFLIGHT_BLOCKED"
    MTA_RUNTIME_BIGQUERY_WRITE_ERROR = "MTA_RUNTIME_BIGQUERY_WRITE_ERROR"
    MTA_RUNTIME_READBACK_ERROR = "MTA_RUNTIME_READBACK_ERROR"
    MTA_FAKE_RUNTIME_NOT_ALLOWED = "MTA_FAKE_RUNTIME_NOT_ALLOWED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class MTAModelRequirement(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class ScheduledRefreshApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    PLAN_READY = "PLAN_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    PROVISIONING = "PROVISIONING"
    VERIFYING = "VERIFYING"
    PROVISIONED = "PROVISIONED"
    PROVISIONING_FAILED = "PROVISIONING_FAILED"
    DISABLED = "DISABLED"


class MTAAnalysisConfig(FrozenModel):
    conversion_event: str
    conversion_period_start: str
    conversion_period_end: str
    lookback_window_days: int
    identity_strategy: IdentityStrategy
    sessionization_policy: SessionizationPolicy
    traffic_source_policy: SessionTrafficSourcePolicy
    direct_treatment_policy: DirectTreatmentPolicy
    channel_registry_version: int
    channel_grouping_version: int
    include_nonconverting_paths: bool = False
    conversion_value_strategy: ConversionValueStrategy = ConversionValueStrategy.NONE
    models: tuple[AttributionModelId, ...] = ()
    journey_definition: JourneyDefinition = Field(default_factory=JourneyDefinition)
    model_parameters: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str


class MTARefreshWindow(FrozenModel):
    run_date: str
    settlement_days: int
    source_overlap_days: int
    lookback_window_days: int
    source_start_date: str
    source_end_date: str
    affected_conversion_start: str
    affected_conversion_end: str
    fingerprint: str
    calculation_trace: tuple[str, ...] = ()


class MTAScheduledRefreshPlan(FrozenModel):
    schedule_id: str
    enabled: bool
    cadence: str
    timezone: str
    settlement_days: int
    source_overlap_days: int
    lookback_window_days: int
    conversion_event: str
    channel_registry_version: int
    channel_grouping_version: int
    sql_asset_library_version: int = 1
    approval_status: ScheduledRefreshApprovalStatus = ScheduledRefreshApprovalStatus.DRAFT
    fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)


class MTAScheduledRefreshReceipt(FrozenModel):
    receipt_id: str
    schedule_id: str
    plan_fingerprint: str
    provisioned: bool
    verified: bool
    generated_at: datetime = Field(default_factory=utc_now)
    schedule_resource_id: str | None = None
    schedule_name: str | None = None
    cadence: str | None = None
    timezone: str | None = None
    service_identity: str | None = None
    sql_asset_id: str | None = None
    sql_asset_version: str | None = None
    rendered_sql_fingerprint: str | None = None
    source_binding: str | None = None
    destination_binding: str | None = None
    channel_registry_version: int | None = None
    channel_grouping_version: int | None = None
    lookback_window_days: int | None = None
    settlement_days: int | None = None
    status: str | None = None
    disabled_by: str | None = None
    disabled_at: datetime | None = None
    verified_at: datetime | None = None
    evidence_label: str | None = None
    fingerprint: str | None = None


class ModelParameterSet(FrozenModel):
    model_id: AttributionModelId
    requirement: MTAModelRequirement
    parameters: dict[str, Any] = Field(default_factory=dict)


class MTAExecutionPlan(FrozenModel):
    execution_plan_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    input_contract_id: str
    readiness_receipt_id: str
    analysis_config_fingerprint: str
    models: tuple[AttributionModelId, ...]
    model_parameters: tuple[ModelParameterSet, ...] = ()
    channel_registry_version: int
    channel_grouping_version: int
    channel_grouping_fingerprint: str
    journey_fingerprint: str
    input_mode: MTAInputMode = MTAInputMode.GROUPED_PATH_FREQUENCY
    dp6_version: str
    adapter_version: str
    worker_image_digest: str | None = None
    source_commit_sha: str | None = None
    output_targets: tuple[str, ...] = ()
    runtime_mode: str = "FAKE_TEST"
    compute_profile: str = "CPU_STANDARD"
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class MTAExecutionDispatch(FrozenModel):
    dispatch_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    run_id: str
    execution_plan_id: str
    execution_plan_fingerprint: str
    status: MTADispatchStatus = MTADispatchStatus.PENDING
    cloud_task_name: str | None = None
    cloud_run_execution_name: str | None = None
    attempt: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MTAModelExecutionEvidence(FrozenModel):
    model_type: AttributionModelId
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_mode: MTAInputMode | None = None
    input_fingerprint: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    runtime: str | None = None
    runtime_version: str | None = None
    row_count: int | None = None
    path_count: int | None = None
    input_row_count: int | None = None
    input_path_count: int | None = None
    output_row_count: int | None = None
    output_refs: tuple[str, ...] = ()
    output_fingerprint: str | None = None
    duration_ms: int | None = None
    limitations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class MTARun(FrozenModel):
    run_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    execution_plan_id: str
    execution_plan_fingerprint: str
    status: MTARunStatus = MTARunStatus.PENDING
    dispatch_id: str | None = None
    failure_class: MTAFailureClass | None = None
    model_evidence: tuple[MTAModelExecutionEvidence, ...] = ()
    proof_label: str = "SYNTHETIC"
    worker_image_digest: str | None = None
    source_commit_sha: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MTARunReceipt(FrozenModel):
    receipt_id: str
    run_id: str
    execution_plan_id: str
    status: MTARunStatus
    source_manifest_ref: str | None = None
    input_contract_fingerprint: str
    session_count: int = 0
    touchpoint_count: int = 0
    journey_count: int = 0
    grouped_path_count: int = 0
    model_statuses: tuple[MTAModelExecutionEvidence, ...] = ()
    output_refs: tuple[str, ...] = ()
    readback_status: str = "NOT_ATTEMPTED"
    limitations: tuple[str, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_commit_sha: str | None = None
    worker_image_digest: str | None = None
    computation_authority: MTAComputationAuthority = MTAComputationAuthority.TEST_FAKE_RUNTIME
    fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)

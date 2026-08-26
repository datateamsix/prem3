"""Presentation contracts for MTA APIs."""

from __future__ import annotations

from pydantic import Field

from app.service.models import ApiModel


class MTAOverviewNextActionView(ApiModel):
    action_type: str
    statement: str
    owner: str = "server"
    blocking: bool = False


class MTAOverviewResponse(ApiModel):
    project_id: str
    cycle_id: str
    track_id: str | None = None
    domain_stage: str
    readiness_state: str
    foundation_ready: bool
    conversion_event: str | None = None
    conversion_period_start: str | None = None
    conversion_period_end: str | None = None
    lookback_window_days: int | None = None
    ga4_dataset_id: str | None = None
    ga4_property_id: str | None = None
    identity_strategy: str | None = None
    user_pseudo_id_coverage: float | None = None
    user_id_coverage: float | None = None
    channel_grouping_version: str | None = None
    attribution_models: list[str] = Field(default_factory=list)
    latest_result_state: str | None = None
    latest_result_snapshot_id: str | None = None
    current_result_snapshot_id: str | None = None
    models_available: list[str] = Field(default_factory=list)
    top_verified_findings: list[str] = Field(default_factory=list)
    channels_needing_review: list[str] = Field(default_factory=list)
    model_sensitivity_summary: str | None = None
    observability_status: str | None = None
    settlement_policy: str | None = None
    epistemic_label: str = "Observable journey attribution"
    next_action: MTAOverviewNextActionView
    attention: list[str] = Field(default_factory=list)
    acceptance_computed_by_server: bool = True


class MTAReadinessResponse(ApiModel):
    receipt_id: str
    state: str
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str
    ga4_dataset_id: str | None = None
    conversion_event: str | None = None


class EvaluateMTAReadinessRequest(ApiModel):
    ga4_dataset_exists: bool = False
    daily_shards_continuous: bool = True
    key_event_present: bool = False
    conversion_volume_ok: bool = False
    channel_grouping_approved: bool = False
    unmapped_share_ok: bool = True
    uses_intraday_for_canonical: bool = False
    lookback_covered: bool = False
    user_pseudo_id_coverage: float | None = None


class MTARunResponse(ApiModel):
    run_id: str
    status: str
    execution_plan_id: str
    dispatch_id: str | None = None
    proof_label: str = "SYNTHETIC"


class MTARunReceiptResponse(ApiModel):
    receipt_id: str
    run_id: str
    status: str
    fingerprint: str
    readback_status: str
    journey_count: int = 0
    grouped_path_count: int = 0
    limitations: list[str] = Field(default_factory=list)


class CreateMTARunRequest(ApiModel):
    """Customer create-run body — no BQ/GCS/authority fields allowed."""

    note: str | None = None


class CanonicalChannelView(ApiModel):
    channel_id: str
    display_name: str
    channel_family_id: str
    mmm_allowed: bool
    mta_default: bool


class MTAProvisioningPlanView(ApiModel):
    plan_id: str
    fingerprint: str
    gcp_project_id: str
    dataset_id: str
    channel_grouping_routine: str
    ux: dict = Field(default_factory=dict)


class ApproveProvisionRequest(ApiModel):
    approved: bool = True
    note: str | None = None


class MTAProvisioningReceiptView(ApiModel):
    receipt_id: str
    plan_id: str
    plan_fingerprint: str
    created: list[str] = Field(default_factory=list)
    reused: list[str] = Field(default_factory=list)
    verified: bool = False


class ScheduledRefreshPlanRequest(ApiModel):
    conversion_event: str = "purchase"
    lookback_window_days: int = 30
    settlement_days: int = 3
    source_overlap_days: int = 3
    cadence: str = "every 24 hours"
    timezone: str = "America/Los_Angeles"


class ScheduledRefreshPlanView(ApiModel):
    schedule_id: str
    fingerprint: str
    approval_status: str
    lookback_window_days: int
    cadence: str
    timezone: str


class ScheduledRefreshReceiptView(ApiModel):
    receipt_id: str
    schedule_id: str
    provisioned: bool
    verified: bool
    schedule_resource_id: str | None = None
    status: str | None = None
    evidence_label: str | None = None


class DisableScheduleRequest(ApiModel):
    resource_name: str
    note: str | None = None


class ParameterExplanationsView(ApiModel):
    explanations: dict[str, str] = Field(default_factory=dict)
    models: list[dict] = Field(default_factory=list)


class MTAResultsSnapshotView(ApiModel):
    result_snapshot_id: str
    run_id: str
    result_status: str
    evidence_authority: str
    fingerprint: str
    models_requested: list[str] = Field(default_factory=list)
    models_completed: list[str] = Field(default_factory=list)
    conversion_event: str
    conversion_period_start: str
    conversion_period_end: str
    channel_registry_version: int
    channel_registry_fingerprint: str
    channel_grouping_version: str
    channel_grouping_fingerprint: str
    observability_status: str | None = None
    latest_result_snapshot_id: str | None = None
    current_result_snapshot_id: str | None = None
    source_cutoff: str | None = None
    adapter_version: str
    limitations: list[dict] = Field(default_factory=list)


class MTAResultsNotAvailableView(ApiModel):
    result_status: str = "NOT_AVAILABLE"
    detail: str = "No verified MTA result snapshot is available."

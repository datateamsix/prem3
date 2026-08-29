"""Presentation contracts for Project, Project Home, and Foundation overviews."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.service.models import ApiModel


class ProjectResponse(ApiModel):
    project_id: str
    workspace_id: str
    name: str
    description: str | None = None
    scope_type: str
    brand_name: str | None = None
    business_unit: str | None = None
    primary_market: str | None = None
    markets: list[str] = Field(default_factory=list)
    default_currency: str | None = None
    default_timezone: str | None = None
    logo_ref: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CreateProjectRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    scope_type: str = "CUSTOM"
    brand_name: str | None = None
    business_unit: str | None = None
    primary_market: str | None = None
    markets: list[str] = Field(default_factory=list)
    default_currency: str | None = None
    default_timezone: str | None = None
    logo_ref: str | None = None


class PatchProjectRequest(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    scope_type: str | None = None
    brand_name: str | None = None
    business_unit: str | None = None
    primary_market: str | None = None
    markets: list[str] | None = None
    default_currency: str | None = None
    default_timezone: str | None = None
    logo_ref: str | None = None
    status: str | None = None


class NextAction(ApiModel):
    action_type: str
    label: str
    capability: str
    resource_ref: str | None = None
    route_hint: str | None = None
    priority: int = 100


class AttentionItem(ApiModel):
    attention_id: str
    severity: str
    title: str
    summary: str
    owning_capability: str
    evidence_refs: list[str] = Field(default_factory=list)
    next_action: NextAction | None = None
    created_at: datetime
    state: str = "OPEN"


class RecentChange(ApiModel):
    event_id: str
    event_type: str
    title: str
    occurred_at: datetime
    capability: str
    resource_ref: str | None = None
    receipt_ref: str | None = None


class FoundationSummary(ApiModel):
    readiness: str
    attention_count: int = 0
    next_action: NextAction | None = None


class MeasurementTrackSummary(ApiModel):
    track_id: str
    track_type: str
    display_name: str
    engine: str | None = None
    availability: str
    domain_state: str | None = None
    latest_run_id: str | None = None
    context_items: list[str] = Field(default_factory=list)
    attention_count: int = 0
    next_action: NextAction | None = None
    updated_at: datetime


class ProjectListItem(ApiModel):
    project: ProjectResponse
    foundation_state: str
    active_tracks: list[str] = Field(default_factory=list)
    attention_count: int = 0
    latest_activity_at: datetime | None = None
    next_action: NextAction | None = None


class ProjectListResponse(ApiModel):
    items: list[ProjectListItem]
    next_cursor: str | None = None
    active_project_count: int
    max_active_projects: int
    capacity_remaining: int


class ProjectMeasurementHomeBinding(ApiModel):
    project_id: str
    google_connection_id: str | None = None
    gcp_project_id: str | None = None
    bigquery_dataset_id: str | None = None
    drive_root_folder_id: str | None = None
    region: str | None = None
    binding_status: str
    namespace_conflict: bool = False
    created_at: datetime | None = None
    verified_at: datetime | None = None


class MeasurementCycleSummary(ApiModel):
    cycle_id: str
    project_id: str
    name: str
    cadence: str
    data_cutoff: str | None = None
    data_cutoff_origin: str | None = None
    business_profile_snapshot_id: str
    foundation_snapshot_ref: str | None = None
    state: str
    created_at: datetime
    updated_at: datetime


class BusinessIqHomeSummary(ApiModel):
    readiness: str
    profile_version: int | None = None
    profile_snapshot_id: str | None = None
    channel_count: int = 0
    market_count: int = 0
    material_driver_count: int = 0
    acknowledged_unknown_count: int = 0
    high_priority_question_count: int = 0
    updated_at: datetime | None = None
    next_action: NextAction | None = None


class DataFoundationHomeSummary(ApiModel):
    readiness: str
    required_source_count: int = 0
    healthy_source_count: int = 0
    review_source_count: int = 0
    blocked_source_count: int = 0
    shared_continuous_window: str | None = None
    last_refresh_at: datetime | None = None
    most_limiting_source: str | None = None
    attention_count: int = 0
    next_action: NextAction | None = None


class PlanningCapabilitySummary(ApiModel):
    capability: str
    availability: str
    dependency_reason: str | None = None
    latest_artifact_ref: str | None = None
    next_action: NextAction | None = None


class IntelligenceHomeSummary(ApiModel):
    opportunity_count: int = 0
    risk_count: int = 0
    decision_required_count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


class ProjectHomeReadModel(ApiModel):
    project: ProjectResponse
    current_cycle: MeasurementCycleSummary | None = None
    selected_cycle: MeasurementCycleSummary | None = None
    is_current_cycle: bool = True
    measurement_home: ProjectMeasurementHomeBinding
    business_iq_summary: BusinessIqHomeSummary
    data_foundation_summary: DataFoundationHomeSummary
    measurement_tracks: list[MeasurementTrackSummary] = Field(default_factory=list)
    planning_capabilities: list[PlanningCapabilitySummary] = Field(default_factory=list)
    intelligence_summary: IntelligenceHomeSummary
    attention_items: list[AttentionItem] = Field(default_factory=list)
    recent_changes: list[RecentChange] = Field(default_factory=list)
    generated_at: datetime


class BusinessIqOverviewReadModel(ApiModel):
    project_id: str
    readiness: str
    profile_summary: dict[str, Any] | None = None
    brief_summary: str | None = None
    top_measurement_considerations: list[str] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)
    evidence_summary: dict[str, int] = Field(default_factory=dict)
    open_question_summary: dict[str, int] = Field(default_factory=dict)
    attention_items: list[AttentionItem] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    updated_at: datetime | None = None
    generated_at: datetime


class DataFoundationOverviewReadModel(ApiModel):
    project_id: str
    readiness: str
    phase: str
    connection_summary: list[dict[str, Any]] = Field(default_factory=list)
    source_summary: dict[str, int] = Field(default_factory=dict)
    quality_summary: dict[str, int] = Field(default_factory=dict)
    coverage_summary: dict[str, Any] | None = None
    data_intelligence_summary: dict[str, Any] | None = None
    next_actions: list[NextAction] = Field(default_factory=list)
    attention_items: list[AttentionItem] = Field(default_factory=list)
    last_refresh_at: datetime | None = None
    updated_at: datetime | None = None
    generated_at: datetime


class CoverageReadModel(ApiModel):
    project_id: str
    cycle_id: str
    view: str
    summary: dict[str, Any]
    series: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    assessed_at: datetime
    generated_at: datetime


class OrganizationReadModel(ApiModel):
    display_name: str
    current_plan: str
    plan_status: str
    active_project_count: int
    max_active_projects: int
    user_role: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class MeEntitlementSummary(ApiModel):
    plan_id: str
    status: str
    feature_summary: list[str]
    capabilities: list[str] = Field(default_factory=list)


class MeasurementTrackResponse(ApiModel):
    track_id: str
    project_id: str
    workspace_id: str
    cycle_id: str
    track_type: str
    status: str
    configuration_version: int
    config: dict[str, Any] = Field(default_factory=dict)
    input_readiness_state: str | None = None
    latest_run_id: str | None = None
    created_at: datetime
    updated_at: datetime


class MeasurementTrackListResponse(ApiModel):
    items: list[MeasurementTrackResponse]


class PatchMeasurementTrackRequest(ApiModel):
    config: dict[str, Any] | None = None

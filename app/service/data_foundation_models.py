"""Presentation-safe Data Foundation API contracts."""

from __future__ import annotations

from typing import Any

from app.service.models import ApiModel


class DataFoundationOverviewResponse(ApiModel):
    workspace_id: str
    phase: str
    requirement_count: int
    candidate_count: int
    source_ready_count: int
    foundation_ready: bool
    live_cloud_proof: str
    connections: list[dict[str, Any]]


class LoadSnapshotRequest(ApiModel):
    snapshot: dict[str, Any]


class BindSourceRequest(ApiModel):
    candidate_id: str
    requirement_id: str | None = None
    governance_import_ready: bool = False
    grain: str | None = None
    date_field: str | None = None
    date_format: str | None = None
    unique_keys: list[str] = []
    required_fields: list[str] = []
    currency: str | None = None
    timezone: str | None = None


class CompileTransformRequest(ApiModel):
    source_id: str
    action_ids: list[str]
    parameters: dict[str, dict[str, Any]] | None = None


class CompileFoundationPlanRequest(ApiModel):
    include_drive: bool = False
    dv360: bool = False


class ApprovePlanRequest(ApiModel):
    plan_id: str
    sections: list[str] | None = None


class MaterializeDriveRequest(ApiModel):
    drive_file_id: str
    sheet_name: str | None = None


class ExecutePlanRequest(ApiModel):
    plan_id: str


class ResolveDecisionRequest(ApiModel):
    source_id: str
    kind: str
    value: str


class DiscoveryHintsRequest(ApiModel):
    datasets_to_prioritize: list[str] = []
    only_inspect_prioritized_datasets: bool = False
    drive_sources_or_paths_to_prioritize: list[str] = []


class CreateCycleRequest(ApiModel):
    name: str
    cadence: str
    business_profile_snapshot_id: str
    data_cutoff: str | None = None
    cutoff_origin: str | None = None
    target_window_start: str | None = None
    target_window_end: str | None = None
    target_window_status: str = "PROVISIONAL"


class UpdateCycleRequest(ApiModel):
    name: str | None = None
    cadence: str | None = None
    data_cutoff: str | None = None
    cutoff_origin: str | None = None
    target_window_start: str | None = None
    target_window_end: str | None = None
    target_window_status: str | None = None


class ReviseCycleRequest(ApiModel):
    name: str | None = None
    business_profile_snapshot_id: str | None = None
    data_cutoff: str | None = None
    cutoff_origin: str | None = None
    target_window_start: str | None = None
    target_window_end: str | None = None


class ReplaceSourceRequest(ApiModel):
    candidate_id: str
    governance_import_ready: bool = False
    grain: str | None = None
    date_field: str | None = None
    date_format: str | None = None
    unique_keys: list[str] = []
    required_fields: list[str] = []
    currency: str | None = None
    timezone: str | None = None


class TransitionRequest(ApiModel):
    historical_source_id: str
    ongoing_source_id: str
    cutoff: str
    overlap_handling: str = "REVIEW"
    reconciliation_required: bool = True
    canonical_precedence: str = "ongoing_after_cutoff"

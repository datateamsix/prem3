"""Presentation contracts for MMM modeling APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.service.models import ApiModel


class MMMSummaryResponse(ApiModel):
    project_id: str
    cycle_id: str
    track_id: str | None = None
    state: str | None = None
    model_version_id: str | None = None
    model_ready: bool = False


class CreateModelDesignRequest(ApiModel):
    model_ready_run_id: str
    model_ready_manifest_fingerprint: str
    model_ready_manifest_ref: str | None = None
    business_profile_snapshot_id: str | None = None
    model_window_start: str
    model_window_end: str
    scope: str = "GEO"
    kpi: str = "revenue"
    media_channels: list[str] = Field(default_factory=list)
    rf_channels: list[str] = Field(default_factory=list)
    compute_profile: str = "CPU_TEST"
    include_ambiguous_promotion: bool = False
    include_insufficient_controls: bool = False
    include_experiment_prior: bool = False


class DecisionActionRequest(ApiModel):
    chosen_value: Any = None
    reason: str | None = None


class AcknowledgeReviewRequest(ApiModel):
    items: list[str] = Field(default_factory=list)


class AcceptModelRequest(ApiModel):
    reason: str | None = None


class IterateModelRequest(ApiModel):
    reason: str


class ModelVersionResponse(ApiModel):
    model_version_id: str
    project_id: str
    cycle_id: str
    track_id: str
    state: str
    version: int
    model_plan_fingerprint: str | None = None
    model_ready_manifest_fingerprint: str
    supersedes_model_version_id: str | None = None
    accepted: bool
    created_at: datetime


class FitRunResponse(ApiModel):
    fit_run_id: str
    model_version_id: str
    status: str
    fit_plan_fingerprint: str
    python_version: str | None = None
    meridian_version: str | None = None
    tensorflow_version: str | None = None
    worker_image_digest: str | None = None

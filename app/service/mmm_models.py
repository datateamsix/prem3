"""Presentation contracts for MMM modeling APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.service.models import ApiModel


class MeasurementCycleView(ApiModel):
    cycle_id: str
    name: str | None = None
    data_cutoff: str | None = None


class MmmTrackWindowView(ApiModel):
    model_window_start: str | None = None
    model_window_end: str | None = None


class MMMSummaryResponse(ApiModel):
    project_id: str
    cycle_id: str
    track_id: str | None = None
    state: str | None = None
    model_version_id: str | None = None
    model_ready: bool = False
    measurement_cycle: MeasurementCycleView | None = None
    mmm_track: MmmTrackWindowView | None = None


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
    model_window_start: str | None = None
    model_window_end: str | None = None
    supersedes_model_version_id: str | None = None
    accepted: bool
    created_at: datetime


class FitNextActionView(ApiModel):
    action_type: str
    statement: str
    owner: str = "human"
    blocking: bool = True
    route_hint: str | None = None


class FitEvidenceLinks(ApiModel):
    fit_run_id: str
    model_version_id: str
    fit_approval_id: str | None = None
    fit_plan_fingerprint: str | None = None
    model_plan_fingerprint: str | None = None
    model_plan_id: str | None = None


class FitRunResponse(ApiModel):
    fit_run_id: str
    model_version_id: str
    status: str
    fit_plan_fingerprint: str
    runtime_mode: str | None = None
    python_version: str | None = None
    meridian_version: str | None = None
    tensorflow_version: str | None = None
    worker_image_digest: str | None = None
    failure_class: str | None = None
    failure_stage: str | None = None
    sampling_started: bool | None = None
    retry_semantics: str | None = None
    library: str | None = None
    library_version: str | None = None
    exception_type: str | None = None
    official_message: str | None = None
    prem3_summary: str | None = None
    next_actions: list[FitNextActionView] = Field(default_factory=list)
    dispatch_outcome: str | None = None
    evidence: FitEvidenceLinks | None = None


_FIT_NEXT_ACTION_COPY = {
    "REVIEW_MODEL_IDENTIFIABILITY": (
        "Review Model Design. Identifiability of the promotion treatment "
        "versus knot strategy must be resolved before another fit can be approved."
    ),
    "REVIEW_MODEL_SPEC": "Review Model Design. The current specification cannot proceed.",
}


def to_fit_run_response(
    run,
    *,
    approval=None,
    plan=None,
    version=None,
) -> FitRunResponse:
    del version
    actions: list[FitNextActionView] = []
    for action_type in run.next_actions:
        if action_type == "RETRY_FIT":
            continue
        actions.append(
            FitNextActionView(
                action_type=action_type,
                statement=_FIT_NEXT_ACTION_COPY.get(
                    action_type, "Review Model Design before another fit."
                ),
                owner="human",
                blocking=True,
                route_hint="model-design",
            )
        )
    evidence = FitEvidenceLinks(
        fit_run_id=run.fit_run_id,
        model_version_id=run.model_version_id,
        fit_approval_id=None if approval is None else approval.approval_id,
        fit_plan_fingerprint=run.fit_plan_fingerprint,
        model_plan_fingerprint=None if plan is None else plan.fingerprint,
        model_plan_id=None if plan is None else plan.model_plan_id,
    )
    return FitRunResponse(
        fit_run_id=run.fit_run_id,
        model_version_id=run.model_version_id,
        status=run.status.value,
        fit_plan_fingerprint=run.fit_plan_fingerprint,
        runtime_mode=None if run.runtime_mode is None else run.runtime_mode.value,
        python_version=run.python_version,
        meridian_version=run.meridian_version,
        tensorflow_version=run.tensorflow_version,
        worker_image_digest=run.worker_image_digest,
        failure_class=None if run.failure_class is None else run.failure_class.value,
        failure_stage=None if run.failure_stage is None else run.failure_stage.value,
        sampling_started=run.sampling_started,
        retry_semantics=None if run.retry_semantics is None else run.retry_semantics.value,
        library=run.library,
        library_version=run.library_version,
        exception_type=run.exception_type,
        official_message=run.official_message,
        prem3_summary=run.prem3_summary,
        next_actions=actions,
        dispatch_outcome=(
            None if run.dispatch_outcome is None else run.dispatch_outcome.value
        ),
        evidence=evidence,
    )


class OfficialEdaReportView(ApiModel):
    official_report_available: bool
    content_type: str = "text/html"
    authorized_view_url: str | None = None
    sha256: str | None = None
    artifact_class: str | None = None


class EdaLatestRunView(ApiModel):
    premodel_run_id: str
    official_gate_status: str
    official_gate_outcome: str


class EdaAttentionView(ApiModel):
    review_recommended: bool
    max_official_severity: str
    attention_count: int
    error_count: int


class EdaNextActionView(ApiModel):
    action_type: str
    statement: str
    owner: str
    blocking: bool
    route_hint: str | None = None


class ExtendedEdaReadModelResponse(ApiModel):
    status: str
    extended_report: dict[str, Any]
    official_report: OfficialEdaReportView
    latest_run: EdaLatestRunView
    attention: EdaAttentionView
    next_actions: list[EdaNextActionView] = Field(default_factory=list)

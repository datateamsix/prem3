"""MMM modeling APIs. Tenant is never taken from the request body."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.control_plane.models import Feature, Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, require_tenant
from app.eda.html_trust import HtmlNotTrustedError, embed_headers, inspect_generated_html
from app.eda.service import ExtendedEDAService
from app.modeling.common.errors import ModelingError
from app.modeling.mmm.contracts import ComputeProfile
from app.modeling.mmm.service import MMMModelingService
from app.project.tracks import ensure_tracks_for_cycle
from app.service.dependencies import (
    authenticated_tenant,
    authorized_workspace,
    get_control_plane,
)
from app.service.entitlements import require_feature
from app.service.errors import APIError, artifact_not_trusted, resource_not_found
from app.service.mmm_models import (
    AcceptModelRequest,
    AcknowledgeReviewRequest,
    CreateModelDesignRequest,
    DecisionActionRequest,
    EdaAttentionView,
    EdaLatestRunView,
    EdaNextActionView,
    ExtendedEdaReadModelResponse,
    FitRunResponse,
    IdentifiabilityDecisionRequest,
    IdentifiabilityReviewResponse,
    IterateModelRequest,
    MeasurementCycleView,
    MMMSummaryResponse,
    MmmTrackWindowView,
    ModelVersionResponse,
    OfficialEdaReportView,
    to_fit_run_response,
    to_identifiability_review,
)

router = APIRouter(prefix="/v1", tags=["mmm-modeling"])


def _modeling(request: Request) -> MMMModelingService:
    service = getattr(request.app.state, "mmm_modeling", None)
    if service is None:
        raise RuntimeError("MMM modeling service is not configured.")
    return service


def _extended_eda(request: Request) -> ExtendedEDAService:
    service = getattr(request.app.state, "extended_eda", None)
    if service is None:
        raise RuntimeError("Extended EDA service is not configured.")
    return service


def _raise_modeling(exc: ModelingError) -> None:
    status = 409
    if exc.code == "RESOURCE_NOT_FOUND":
        status = 404
    if exc.code in {
        "FIT_APPROVAL_REQUIRED",
        "STALE_APPROVAL",
        "FAKE_RUNTIME_INELIGIBLE",
        "EXACT_RETRY_NOT_ALLOWED",
        "IDENTIFIABILITY_DECISION_REQUIRED",
        "PREFIT_VALIDATION_FAILED",
        "HUMAN_APPROVAL_REQUIRED",
        "FABRICATED_GEO_VARIATION",
    }:
        status = 409
    if exc.code == "LEDGER_PUBLICATION_FAILED":
        status = 409
    if exc.code == "RESOURCE_EXHAUSTED":
        status = 429
    raise APIError(code=exc.code, status=status, title="Modeling error", detail=str(exc)) from exc


def _version_response(version) -> ModelVersionResponse:
    return ModelVersionResponse(
        model_version_id=version.model_version_id,
        project_id=version.project_id,
        cycle_id=version.cycle_id,
        track_id=version.track_id,
        state=version.state.value,
        version=version.version,
        model_plan_fingerprint=version.model_plan_fingerprint,
        model_ready_manifest_fingerprint=version.model_ready_manifest_fingerprint,
        model_window_start=version.model_window_start,
        model_window_end=version.model_window_end,
        supersedes_model_version_id=version.supersedes_model_version_id,
        accepted=version.accepted,
        created_at=version.created_at,
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mmm",
    operation_id="getProjectCycleMmm",
)
async def get_cycle_mmm(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MMMSummaryResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    current = _modeling(request).current_for_cycle(
        tenant_id=tenant.tenant_id, project_id=project_id, cycle_id=cycle_id
    )
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    mmm = next((item for item in tracks if item.track_type.value == "MMM"), None)
    plan = None if current is None else _modeling(request).repo.get_plan(current.model_version_id)
    return MMMSummaryResponse(
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=None if mmm is None else mmm.track_id,
        state=None if current is None else current.state.value,
        model_version_id=None if current is None else current.model_version_id,
        model_ready=current is not None or mmm is not None,
        measurement_cycle=MeasurementCycleView(cycle_id=cycle_id, name=None, data_cutoff=None),
        mmm_track=MmmTrackWindowView(
            model_window_start=None if plan is None else plan.model_window_start,
            model_window_end=None if plan is None else plan.model_window_end,
        ),
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mmm/eda",
    operation_id="getProjectCycleMmmEda",
)
async def get_cycle_mmm_eda(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ExtendedEdaReadModelResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    report = _extended_eda(request).latest_for_cycle(
        tenant_id=tenant.tenant_id, project_id=project_id, cycle_id=cycle_id
    )
    if report is None:
        raise resource_not_found()
    view_url = f"/v1/projects/{project_id}/cycles/{cycle_id}/mmm/eda/official-html"
    official = _extended_eda(request).official_report_view(
        report, authorized_view_url=view_url
    )
    ready = report.readiness_summary
    return ExtendedEdaReadModelResponse(
        status=report.status.value,
        extended_report=report.model_dump(mode="json"),
        official_report=OfficialEdaReportView(**official.model_dump(mode="json")),
        latest_run=EdaLatestRunView(
            premodel_run_id=report.premodel_run_id,
            official_gate_status=ready.official_gate_status,
            official_gate_outcome=ready.official_gate_outcome,
        ),
        attention=EdaAttentionView(
            review_recommended=ready.review_recommended,
            max_official_severity=ready.max_official_severity,
            attention_count=ready.attention_count,
            error_count=ready.error_count,
        ),
        next_actions=[
            EdaNextActionView(
                action_type=item.action_type.value,
                statement=item.statement,
                owner=item.owner.value,
                blocking=item.blocking,
                route_hint=item.route_hint,
            )
            for item in report.recommended_next_steps
        ],
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mmm/eda/official-html",
    operation_id="getProjectCycleMmmEdaOfficialHtml",
)
async def get_cycle_mmm_eda_official_html(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> HTMLResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    try:
        payload, report = _extended_eda(request).load_trusted_html(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
        )
    except KeyError:
        raise resource_not_found() from None
    except HtmlNotTrustedError as exc:
        raise artifact_not_trusted(detail=str(exc)) from exc
    inspection = inspect_generated_html(
        payload, artifact_class=report.official_html_artifact_class
    )
    return HTMLResponse(content=payload, headers=embed_headers(inspection))


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mmm/model-design",
    operation_id="createMmmModelDesign",
)
async def create_model_design(
    project_id: str,
    cycle_id: str,
    body: CreateModelDesignRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    mmm = next(item for item in tracks if item.track_type.value == "MMM")
    eda_report = _extended_eda(request).latest_for_cycle(
        tenant_id=tenant.tenant_id, project_id=project_id, cycle_id=cycle_id
    )
    eda_handoff = None if eda_report is None else eda_report.model_design_handoff
    try:
        version = _modeling(request).start_design(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=mmm.track_id,
            actor_id=tenant.user_id or "authenticated-user",
            model_ready_run_id=body.model_ready_run_id,
            model_ready_manifest_fingerprint=body.model_ready_manifest_fingerprint,
            model_ready_manifest_ref=body.model_ready_manifest_ref,
            business_profile_snapshot_id=body.business_profile_snapshot_id,
            model_window_start=body.model_window_start,
            model_window_end=body.model_window_end,
            scope=body.scope,
            kpi=body.kpi,
            media_channels=tuple(body.media_channels),
            rf_channels=tuple(body.rf_channels),
            compute_profile=ComputeProfile(body.compute_profile),
            include_ambiguous_promotion=body.include_ambiguous_promotion,
            include_insufficient_controls=body.include_insufficient_controls,
            include_experiment_prior=body.include_experiment_prior,
            eda_handoff=eda_handoff,
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    brief = _modeling(request).repo.get_brief(version.model_version_id)
    decisions = _modeling(request).repo.list_decisions(version.model_version_id)
    return {
        "version": _version_response(version).model_dump(mode="json"),
        "brief": None if brief is None else brief.model_dump(mode="json"),
        "decisions": [item.model_dump(mode="json") for item in decisions],
    }


@router.get(
    "/projects/{project_id}/mmm/model-design/{model_version_id}",
    operation_id="getMmmModelDesign",
)
async def get_model_design(
    project_id: str,
    model_version_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        version = _modeling(request).get_version(
            tenant_id=tenant.tenant_id, project_id=project_id, model_version_id=model_version_id
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return {
        "version": _version_response(version).model_dump(mode="json"),
        "brief": None
        if _modeling(request).repo.get_brief(model_version_id) is None
        else _modeling(request).repo.get_brief(model_version_id).model_dump(mode="json"),
        "plan": None
        if _modeling(request).repo.get_plan(model_version_id) is None
        else _modeling(request).repo.get_plan(model_version_id).model_dump(mode="json"),
        "decisions": [
            item.model_dump(mode="json")
            for item in _modeling(request).repo.list_decisions(model_version_id)
        ],
    }


@router.get(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/identifiability",
    operation_id="getMmmIdentifiabilityReview",
)
async def get_identifiability_review(
    project_id: str,
    model_version_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> IdentifiabilityReviewResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        package = _modeling(request).identifiability_package(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return to_identifiability_review(package)


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/identifiability/decide",
    operation_id="recordMmmIdentifiabilityDecision",
)
async def record_identifiability_decision(
    project_id: str,
    model_version_id: str,
    body: IdentifiabilityDecisionRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        decision = _modeling(request).record_identifiability_decision(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
            actor_id=tenant.user_id or "authenticated-user",
            selected_alternative_id=body.selected_alternative,
            selected_configuration=body.selected_configuration,
            rationale=body.rationale,
            evidence_refs=tuple(body.evidence_refs),
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return decision.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-decisions/{decision_id}/approve",
    operation_id="approveMmmModelDecision",
)
async def approve_decision(
    project_id: str,
    decision_id: str,
    body: DecisionActionRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        decision = _modeling(request).approve_decision(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            decision_id=decision_id,
            actor_id=tenant.user_id or "authenticated-user",
            chosen_value=body.chosen_value,
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return decision.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-decisions/{decision_id}/reject",
    operation_id="rejectMmmModelDecision",
)
async def reject_decision(
    project_id: str,
    decision_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        decision = _modeling(request).reject_decision(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            decision_id=decision_id,
            actor_id=tenant.user_id or "authenticated-user",
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return decision.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/validate-prior",
    operation_id="validateMmmPrior",
)
async def validate_prior(
    project_id: str,
    model_version_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        receipt = _modeling(request).validate_prior(
            tenant_id=tenant.tenant_id, project_id=project_id, model_version_id=model_version_id
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return receipt.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/fit-approval",
    operation_id="approveMmmFit",
)
async def approve_fit(
    project_id: str,
    model_version_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        approval = _modeling(request).approve_fit(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
            actor_id=tenant.user_id or "authenticated-user",
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return approval.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/fit",
    operation_id="startMmmFit",
)
async def start_fit(
    project_id: str,
    model_version_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> FitRunResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        run = _modeling(request).start_fit(
            tenant_id=tenant.tenant_id, project_id=project_id, model_version_id=model_version_id
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return to_fit_run_response(
        run,
        approval=_modeling(request).repo.get_fit_approval(model_version_id),
        plan=_modeling(request).repo.get_plan(model_version_id),
    )


@router.get(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/fit-runs/{fit_run_id}",
    operation_id="getMmmFitRun",
)
async def get_fit_run(
    project_id: str,
    model_version_id: str,
    fit_run_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> FitRunResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    run = _modeling(request).repo.get_fit_run(
        tenant_id=tenant.tenant_id, project_id=project_id, fit_run_id=fit_run_id
    )
    if run is None or run.model_version_id != model_version_id:
        raise resource_not_found()
    modeling = _modeling(request)
    return to_fit_run_response(
        run,
        approval=modeling.repo.get_fit_approval(model_version_id),
        plan=modeling.repo.get_plan(model_version_id),
        version=modeling.repo.get_version(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
        ),
    )


@router.get(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/review",
    operation_id="getMmmModelReview",
)
async def get_review(
    project_id: str,
    model_version_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        _modeling(request).get_version(
            tenant_id=tenant.tenant_id, project_id=project_id, model_version_id=model_version_id
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    pack = _modeling(request).repo.get_review(model_version_id)
    if pack is None:
        raise resource_not_found()
    return pack.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/review/acknowledge",
    operation_id="acknowledgeMmmReview",
)
async def acknowledge_review(
    project_id: str,
    model_version_id: str,
    body: AcknowledgeReviewRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        pack = _modeling(request).acknowledge_review(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
            items=tuple(body.items),
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return pack.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/accept",
    operation_id="acceptMmmModel",
)
async def accept_model(
    project_id: str,
    model_version_id: str,
    body: AcceptModelRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        approval = _modeling(request).accept(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
            actor_id=tenant.user_id or "authenticated-user",
            reason=body.reason,
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return approval.model_dump(mode="json")


@router.post(
    "/projects/{project_id}/mmm/model-versions/{model_version_id}/iterate",
    operation_id="iterateMmmModel",
)
async def iterate_model(
    project_id: str,
    model_version_id: str,
    body: IterateModelRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ModelVersionResponse:
    require_tenant()
    require_feature(repo, Feature.MMM)
    try:
        version = _modeling(request).iterate(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            model_version_id=model_version_id,
            actor_id=tenant.user_id or "authenticated-user",
            reason=body.reason,
        )
    except ModelingError as exc:
        _raise_modeling(exc)
    return _version_response(version)


@router.post(
    "/workspaces/{workspace_id}/cycles/{cycle_id}/mmm/model-design",
    operation_id="createWorkspaceMmmModelDesign",
)
async def workspace_create_model_design(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    cycle_id: str,
    body: CreateModelDesignRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> dict[str, Any]:
    return await create_model_design(
        workspace.workspace_id, cycle_id, body, request, tenant, repo
    )

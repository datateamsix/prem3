"""MTA track APIs. Tenant is never taken from the request body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.config import settings
from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, require_tenant
from app.domain.channels import cached_channel_registry
from app.modeling.mta.parameter_explanations import (
    list_model_explanations,
    parameter_explanations,
)
from app.modeling.mta.provisioning_service import MTAProvisioningService
from app.modeling.mta.service import MTAService
from app.modeling.mta.sql.registry import cached_sql_asset_manifest
from app.modeling.mta.sql.renderer import render_sql_asset
from app.project.tracks import ensure_tracks_for_cycle
from app.service.dependencies import authenticated_tenant, get_control_plane
from app.service.entitlements import require_feature
from app.service.errors import resource_not_found
from app.service.mta_models import (
    ApproveProvisionRequest,
    CanonicalChannelView,
    CreateMTARunRequest,
    DisableScheduleRequest,
    EvaluateMTAReadinessRequest,
    MTAOverviewNextActionView,
    MTAOverviewResponse,
    MTAProvisioningPlanView,
    MTAProvisioningReceiptView,
    MTAReadinessResponse,
    MTARunReceiptResponse,
    MTARunResponse,
    ParameterExplanationsView,
    ScheduledRefreshPlanRequest,
    ScheduledRefreshPlanView,
    ScheduledRefreshReceiptView,
)

router = APIRouter(prefix="/v1", tags=["mta"])


def _mta(request: Request) -> MTAService:
    service = getattr(request.app.state, "mta_service", None)
    if service is None:
        service = MTAService()
        request.app.state.mta_service = service
    return service


def _overview_response(model) -> MTAOverviewResponse:
    return MTAOverviewResponse(
        project_id=model.project_id,
        cycle_id=model.cycle_id,
        track_id=model.track_id,
        domain_stage=model.domain_stage.value,
        readiness_state=model.readiness_state.value,
        foundation_ready=model.foundation_ready,
        conversion_event=model.conversion_event,
        conversion_period_start=model.conversion_period_start,
        conversion_period_end=model.conversion_period_end,
        lookback_window_days=model.lookback_window_days,
        ga4_dataset_id=model.ga4_dataset_id,
        ga4_property_id=model.ga4_property_id,
        identity_strategy=None
        if model.identity_strategy is None
        else model.identity_strategy.value,
        user_pseudo_id_coverage=model.user_pseudo_id_coverage,
        user_id_coverage=model.user_id_coverage,
        channel_grouping_version=model.channel_grouping_version,
        attribution_models=list(model.attribution_models),
        latest_result_state=model.latest_result_state,
        settlement_policy=None
        if model.settlement_policy is None
        else model.settlement_policy.value,
        epistemic_label=model.epistemic_label,
        next_action=MTAOverviewNextActionView(
            action_type=model.next_action.action_type,
            statement=model.next_action.statement,
            owner=model.next_action.owner,
            blocking=model.next_action.blocking,
        ),
        attention=list(model.attention),
        acceptance_computed_by_server=model.acceptance_computed_by_server,
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mta",
    operation_id="getProjectCycleMta",
    response_model=MTAOverviewResponse,
)
async def get_cycle_mta(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTAOverviewResponse:
    require_tenant()
    require_feature(repo, Feature.MTA)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    mta_track = next((t for t in tracks if t.track_type.value == "MTA"), None)
    foundation = repo.get_data_foundation_receipt(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    ) if hasattr(repo, "get_data_foundation_receipt") else None
    # Fall back: treat missing receipt helper as not ready unless home path provides it.
    foundation_ready = False
    if foundation is not None:
        state = getattr(foundation, "state", None) or getattr(foundation, "readiness", None)
        foundation_ready = str(state) == "DATA_FOUNDATION_READY"
    # Project home assembler is authoritative for DF; for this route use DF ready flag
    # from data foundation store when available via request.app.state.
    df_service = getattr(request.app.state, "data_foundation", None)
    if df_service is not None:
        try:
            env = df_service.get_environment(
                tenant_id=tenant.tenant_id, workspace_id=project_id
            )
            readiness = getattr(env, "readiness", None) if env is not None else None
            foundation_ready = str(readiness) == "DATA_FOUNDATION_READY"
        except Exception:
            pass

    overview = _mta(request).overview(
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=None if mta_track is None else mta_track.track_id,
        foundation_ready=foundation_ready,
        track_id_for_config=None if mta_track is None else mta_track.track_id,
    )
    return _overview_response(overview)


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mta/readiness",
    operation_id="evaluateProjectCycleMtaReadiness",
    response_model=MTAReadinessResponse,
)
async def evaluate_cycle_mta_readiness(
    project_id: str,
    cycle_id: str,
    body: EvaluateMTAReadinessRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTAReadinessResponse:
    require_tenant()
    require_feature(repo, Feature.MTA)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    mta_track = next((t for t in tracks if t.track_type.value == "MTA"), None)
    if mta_track is None:
        raise resource_not_found()
    service = _mta(request)
    config = service.get_config(mta_track.track_id)
    contract = None
    if config is not None and config.ga4_dataset_id and config.key_event_name:
        # Use latest matching contract if present.
        for item in service.repo.contracts.values():
            if item.track_id == mta_track.track_id:
                contract = item
                break
    receipt = service.evaluate_readiness(
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=mta_track.track_id,
        contract=contract,
        ga4_dataset_exists=body.ga4_dataset_exists,
        daily_shards_continuous=body.daily_shards_continuous,
        key_event_present=body.key_event_present,
        conversion_volume_ok=body.conversion_volume_ok,
        channel_grouping_approved=body.channel_grouping_approved,
        unmapped_share_ok=body.unmapped_share_ok,
        uses_intraday_for_canonical=body.uses_intraday_for_canonical,
        lookback_covered=body.lookback_covered,
        user_pseudo_id_coverage=body.user_pseudo_id_coverage,
    )
    return MTAReadinessResponse(
        receipt_id=receipt.receipt_id,
        state=receipt.state.value,
        blocking_failures=list(receipt.blocking_failures),
        warnings=list(receipt.warnings),
        fingerprint=receipt.fingerprint,
        ga4_dataset_id=receipt.ga4_dataset_id,
        conversion_event=receipt.conversion_event,
    )


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mta/runs",
    operation_id="createProjectCycleMtaRun",
    response_model=MTARunResponse,
)
async def create_mta_run(
    project_id: str,
    cycle_id: str,
    body: CreateMTARunRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTARunResponse:
    del body
    require_tenant()
    require_feature(repo, Feature.MTA)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    mta_track = next((t for t in tracks if t.track_type.value == "MTA"), None)
    if mta_track is None:
        raise resource_not_found()
    run = _mta(request).start_run(
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=mta_track.track_id,
    )
    return MTARunResponse(
        run_id=run.run_id,
        status=run.status.value,
        execution_plan_id=run.execution_plan_id,
        dispatch_id=run.dispatch_id,
        proof_label=run.proof_label,
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mta/runs",
    operation_id="listProjectCycleMtaRuns",
    response_model=list[MTARunResponse],
)
async def list_mta_runs(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> list[MTARunResponse]:
    require_tenant()
    require_feature(repo, Feature.MTA)
    service = _mta(request)
    runs = [
        r
        for r in service.repo.list_runs(project_id=project_id, cycle_id=cycle_id)
        if r.tenant_id == tenant.tenant_id
    ]
    return [
        MTARunResponse(
            run_id=r.run_id,
            status=r.status.value,
            execution_plan_id=r.execution_plan_id,
            dispatch_id=r.dispatch_id,
            proof_label=r.proof_label,
        )
        for r in runs
    ]


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mta/runs/{run_id}",
    operation_id="getProjectCycleMtaRun",
    response_model=MTARunResponse,
)
async def get_mta_run(
    project_id: str,
    cycle_id: str,
    run_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTARunResponse:
    require_tenant()
    require_feature(repo, Feature.MTA)
    run = _mta(request).repo.get_run(run_id)
    if (
        run is None
        or run.tenant_id != tenant.tenant_id
        or run.project_id != project_id
        or run.cycle_id != cycle_id
    ):
        raise resource_not_found()
    return MTARunResponse(
        run_id=run.run_id,
        status=run.status.value,
        execution_plan_id=run.execution_plan_id,
        dispatch_id=run.dispatch_id,
        proof_label=run.proof_label,
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mta/runs/{run_id}/receipt",
    operation_id="getProjectCycleMtaRunReceipt",
    response_model=MTARunReceiptResponse,
)
async def get_mta_run_receipt(
    project_id: str,
    cycle_id: str,
    run_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTARunReceiptResponse:
    require_tenant()
    require_feature(repo, Feature.MTA)
    service = _mta(request)
    run = service.repo.get_run(run_id)
    if (
        run is None
        or run.tenant_id != tenant.tenant_id
        or run.project_id != project_id
        or run.cycle_id != cycle_id
    ):
        raise resource_not_found()
    receipt = service.repo.get_run_receipt_for_run(run_id)
    if receipt is None:
        raise resource_not_found()
    return MTARunReceiptResponse(
        receipt_id=receipt.receipt_id,
        run_id=receipt.run_id,
        status=receipt.status.value,
        fingerprint=receipt.fingerprint,
        readback_status=receipt.readback_status,
        journey_count=receipt.journey_count,
        grouped_path_count=receipt.grouped_path_count,
        limitations=list(receipt.limitations),
    )


@router.get(
    "/channels",
    operation_id="listCanonicalChannels",
    response_model=list[CanonicalChannelView],
)
async def list_canonical_channels(
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> list[CanonicalChannelView]:
    require_tenant()
    require_feature(repo, Feature.MTA)

    registry = cached_channel_registry()
    return [
        CanonicalChannelView(
            channel_id=c.channel_id,
            display_name=c.display_name,
            channel_family_id=c.channel_family_id,
            mmm_allowed=c.mmm_allowed,
            mta_default=c.mta_default,
        )
        for c in registry.channels
    ]


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/mta/provisioning-plan",
    operation_id="getMtaProvisioningPlan",
    response_model=MTAProvisioningPlanView,
)
async def get_mta_provisioning_plan(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTAProvisioningPlanView:
    require_tenant()
    require_feature(repo, Feature.MTA)
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    mta_track = next((t for t in tracks if t.track_type.value == "MTA"), None)
    if mta_track is None:
        raise resource_not_found()

    svc = MTAProvisioningService(live=False)
    gcp = settings.project_id
    plan = svc.compile_infrastructure_plan(
        plan_id=f"mtap_{project_id}_{cycle_id}",
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=mta_track.track_id,
        gcp_project_id=gcp,
    )
    _mta(request).repo.put_plan(plan)
    ux = svc.render_ready_plan_view(
        gcp_project_id=gcp,
        ga4_dataset_id="analytics_music_center_synthetic",
    )
    return MTAProvisioningPlanView(
        plan_id=plan.plan_id,
        fingerprint=plan.fingerprint,
        gcp_project_id=plan.gcp_project_id,
        dataset_id=plan.dataset_id,
        channel_grouping_routine=plan.channel_grouping_routine,
        ux=ux,
    )


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mta/provisioning-plan/approve",
    operation_id="approveMtaProvisioningPlan",
    response_model=MTAProvisioningReceiptView,
)
async def approve_mta_provisioning(
    project_id: str,
    cycle_id: str,
    body: ApproveProvisionRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MTAProvisioningReceiptView:
    require_tenant()
    require_feature(repo, Feature.MTA)
    service = _mta(request)
    plan = next(
        (
            p
            for p in service.repo.plans.values()
            if p.project_id == project_id and p.cycle_id == cycle_id
        ),
        None,
    )
    if plan is None:
        raise resource_not_found()

    receipt = MTAProvisioningService(live=False).provision_infrastructure(
        plan, approved=body.approved
    )
    service.repo.put_provisioning_receipt(receipt)
    return MTAProvisioningReceiptView(
        receipt_id=receipt.receipt_id,
        plan_id=receipt.plan_id,
        plan_fingerprint=receipt.plan_fingerprint,
        created=list(receipt.created),
        reused=list(receipt.reused),
        verified=receipt.verified,
    )


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mta/scheduled-refresh/plan",
    operation_id="createMtaScheduledRefreshPlan",
    response_model=ScheduledRefreshPlanView,
)
async def create_scheduled_refresh_plan(
    project_id: str,
    cycle_id: str,
    body: ScheduledRefreshPlanRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ScheduledRefreshPlanView:
    require_tenant()
    require_feature(repo, Feature.MTA)

    plan = MTAProvisioningService(live=False).build_and_approve_schedule(
        schedule_id=f"mts_{project_id}_{cycle_id}",
        conversion_event=body.conversion_event,
        lookback_window_days=body.lookback_window_days,
        settlement_days=body.settlement_days,
        source_overlap_days=body.source_overlap_days,
        cadence=body.cadence,
        timezone=body.timezone,
    )
    # Store awaiting→approved plan; API create also approves for server-bound demo path
    # after explicit body — here build_and_approve already requires the approve step.
    _mta(request).repo.scheduled_refresh[plan.schedule_id] = plan
    return ScheduledRefreshPlanView(
        schedule_id=plan.schedule_id,
        fingerprint=plan.fingerprint,
        approval_status=plan.approval_status.value,
        lookback_window_days=plan.lookback_window_days,
        cadence=plan.cadence,
        timezone=plan.timezone,
    )


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mta/scheduled-refresh/provision",
    operation_id="provisionMtaScheduledRefresh",
    response_model=ScheduledRefreshReceiptView,
)
async def provision_scheduled_refresh(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ScheduledRefreshReceiptView:
    require_tenant()
    require_feature(repo, Feature.MTA)

    service = _mta(request)
    plan = next(
        (
            p
            for p in service.repo.scheduled_refresh.values()
            if p.schedule_id.endswith(f"{project_id}_{cycle_id}")
            or f"{project_id}_{cycle_id}" in p.schedule_id
        ),
        None,
    )
    if plan is None:
        raise resource_not_found()
    entry = cached_sql_asset_manifest().get("daily_refresh_v1")
    sql, _ = render_sql_asset(
        entry,
        params={
            "settlement_days": plan.settlement_days,
            "source_overlap_days": plan.source_overlap_days,
            "lookback_window_days": plan.lookback_window_days,
        },
    )
    prov = MTAProvisioningService(live=False)
    receipt = prov.provision_schedule(
        plan,
        gcp_project_id=settings.project_id,
        query_sql=sql,
    )
    return ScheduledRefreshReceiptView(
        receipt_id=receipt.receipt_id,
        schedule_id=receipt.schedule_id,
        provisioned=receipt.provisioned,
        verified=receipt.verified,
        schedule_resource_id=receipt.schedule_resource_id,
        status=receipt.status,
        evidence_label=receipt.evidence_label,
    )


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/mta/scheduled-refresh/disable",
    operation_id="disableMtaScheduledRefresh",
    response_model=ScheduledRefreshReceiptView,
)
async def disable_scheduled_refresh(
    project_id: str,
    cycle_id: str,
    body: DisableScheduleRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ScheduledRefreshReceiptView:
    del project_id, cycle_id
    require_tenant()
    require_feature(repo, Feature.MTA)

    receipt = MTAProvisioningService(live=False).disable_schedule(
        schedule_id="disabled",
        resource_name=body.resource_name,
        disabled_by=tenant.tenant_id,
    )
    return ScheduledRefreshReceiptView(
        receipt_id=receipt.receipt_id,
        schedule_id=receipt.schedule_id,
        provisioned=receipt.provisioned,
        verified=receipt.verified,
        schedule_resource_id=receipt.schedule_resource_id,
        status=receipt.status,
        evidence_label=receipt.evidence_label,
    )


@router.get(
    "/mta/parameter-explanations",
    operation_id="getMtaParameterExplanations",
    response_model=ParameterExplanationsView,
)
async def get_parameter_explanations(
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ParameterExplanationsView:
    require_tenant()
    require_feature(repo, Feature.MTA)
    return ParameterExplanationsView(
        explanations=parameter_explanations(),
        models=list_model_explanations(),
    )

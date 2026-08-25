"""MTA track APIs. Tenant is never taken from the request body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, require_tenant
from app.modeling.mta.service import MTAService
from app.project.tracks import ensure_tracks_for_cycle
from app.service.dependencies import authenticated_tenant, get_control_plane
from app.service.entitlements import require_feature
from app.service.errors import resource_not_found
from app.service.mta_models import (
    EvaluateMTAReadinessRequest,
    MTAOverviewNextActionView,
    MTAOverviewResponse,
    MTAReadinessResponse,
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

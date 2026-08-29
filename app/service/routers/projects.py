"""Project-centered API over the canonical Workspace store."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.control_plane.models import ProjectScopeType, Workspace, WorkspaceStatus
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import (
    EntitlementUnavailableError,
    ProjectLimitReachedError,
    TrackConfigurationImmutableError,
)
from app.core.tenancy import TenantContext, require_tenant
from app.project.capabilities import capability_summary
from app.project.home import ProjectHomeAssembler, apply_project_fields, project_response
from app.project.tracks import apply_track_mutation, default_config, ensure_tracks_for_cycle
from app.service.dependencies import (
    authenticated_tenant,
    authorized_workspace,
    get_control_plane,
)
from app.service.entitlements import (
    remaining_projects,
    require_paid_capacity_mutation,
    resolve_current_entitlement,
)
from app.service.errors import (
    ProblemFieldError,
    entitlement_unavailable,
    project_limit_reached,
    resource_not_found,
    track_configuration_immutable,
    validation_error,
)
from app.service.pagination import paginate_by_id
from app.service.project_models import (
    CoverageReadModel,
    CreateProjectRequest,
    MeasurementTrackListResponse,
    MeasurementTrackResponse,
    OrganizationReadModel,
    PatchMeasurementTrackRequest,
    PatchProjectRequest,
    ProjectHomeReadModel,
    ProjectListResponse,
    ProjectResponse,
)

router = APIRouter(prefix="/v1", tags=["projects"])


def _assembler(request: Request, repo: ControlPlaneRepository) -> ProjectHomeAssembler:
    return ProjectHomeAssembler(
        repo=repo,
        business_iq=request.app.state.business_iq,
        data_foundation=request.app.state.data_foundation,
        model_ready=getattr(request.app.state, "model_ready_resolver", None),
    )


def _track_response(track) -> MeasurementTrackResponse:
    return MeasurementTrackResponse(
        track_id=track.track_id,
        project_id=track.workspace_id,
        workspace_id=track.workspace_id,
        cycle_id=track.cycle_id,
        track_type=track.track_type.value,
        status=track.status.value,
        configuration_version=track.configuration_version,
        config=dict(track.config),
        input_readiness_state=track.input_readiness_state,
        latest_run_id=track.latest_run_id,
        created_at=track.created_at,
        updated_at=track.updated_at,
    )


@router.get("/projects", operation_id="listProjects", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
    cursor: str | None = None,
) -> ProjectListResponse:
    require_tenant()
    entitlement = resolve_current_entitlement(repo)
    items = _assembler(request, repo).list_items(
        tenant_id=tenant.tenant_id, entitlement=entitlement
    )
    page, next_cursor = paginate_by_id(
        items, cursor=cursor, limit=limit, id_of=lambda item: item.project.project_id
    )
    stored = repo.get_tenant(tenant.tenant_id)
    active = stored.active_workspace_count if stored is not None else 0
    return ProjectListResponse(
        items=page,
        next_cursor=next_cursor,
        active_project_count=active,
        max_active_projects=entitlement.max_active_projects,
        capacity_remaining=remaining_projects(entitlement, active_projects=active),
    )


@router.post(
    "/projects",
    operation_id="createProject",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    body: CreateProjectRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ProjectResponse:
    require_tenant()
    snapshot = resolve_current_entitlement(repo)
    require_paid_capacity_mutation(snapshot)
    try:
        ProjectScopeType(body.scope_type)
    except ValueError as exc:
        raise validation_error(
            [ProblemFieldError(field="scope_type", message="Unsupported project scope.")]
        ) from exc
    try:
        workspace = repo.create_workspace_with_capacity(
            tenant_id=tenant.tenant_id, name=body.name
        )
    except ProjectLimitReachedError as exc:
        raise project_limit_reached() from exc
    except EntitlementUnavailableError as exc:
        raise entitlement_unavailable() from exc
    workspace = repo.put_workspace(
        apply_project_fields(
            workspace,
            {
                "description": body.description,
                "scope_type": body.scope_type,
                "brand_name": body.brand_name,
                "business_unit": body.business_unit,
                "primary_market": body.primary_market,
                "markets": body.markets,
                "default_currency": body.default_currency,
                "default_timezone": body.default_timezone,
                "logo_ref": body.logo_ref,
            },
        )
    )
    return project_response(workspace)


@router.get(
    "/projects/{project_id}",
    operation_id="getProject",
    response_model=ProjectResponse,
)
async def get_project(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ProjectResponse:
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    return project_response(workspace)


@router.patch(
    "/projects/{project_id}",
    operation_id="patchProject",
    response_model=ProjectResponse,
)
async def patch_project(
    project_id: str,
    body: PatchProjectRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> ProjectResponse:
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    updates = body.model_dump(exclude_unset=True)
    if "scope_type" in updates:
        try:
            ProjectScopeType(updates["scope_type"])
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="scope_type", message="Unsupported project scope.")]
            ) from exc
    if "status" in updates:
        try:
            WorkspaceStatus(updates["status"])
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported project status.")]
            ) from exc
        if updates["status"] == WorkspaceStatus.ACTIVE.value:
            require_paid_capacity_mutation(resolve_current_entitlement(repo))
    try:
        updated = repo.put_workspace(apply_project_fields(workspace, updates))
    except ProjectLimitReachedError as exc:
        raise project_limit_reached() from exc
    return project_response(updated)


@router.get(
    "/projects/{project_id}/home",
    operation_id="getProjectHome",
    response_model=ProjectHomeReadModel,
)
async def get_project_home(
    project_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    cycle_id: str | None = None,
) -> ProjectHomeReadModel:
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    home = _assembler(request, repo).build_home(
        workspace=workspace,
        entitlement=resolve_current_entitlement(repo),
        cycle_id=cycle_id,
    )
    if home is None:
        raise resource_not_found()
    return home


@router.get(
    "/workspaces/{workspace_id}/home",
    operation_id="getWorkspaceHome",
    response_model=ProjectHomeReadModel,
)
async def get_workspace_home(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    request: Request,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    cycle_id: str | None = None,
) -> ProjectHomeReadModel:
    home = _assembler(request, repo).build_home(
        workspace=workspace,
        entitlement=resolve_current_entitlement(repo),
        cycle_id=cycle_id,
    )
    if home is None:
        raise resource_not_found()
    return home


@router.get(
    "/projects/{project_id}/measurement-home",
    operation_id="getProjectMeasurementHome",
)
async def get_project_measurement_home(
    project_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
):
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    return _assembler(request, repo).build_home(
        workspace=workspace, entitlement=resolve_current_entitlement(repo)
    ).measurement_home


@router.get(
    "/projects/{project_id}/business-iq/overview",
    operation_id="getBusinessIqOverview",
)
async def get_business_iq_overview(
    project_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
):
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    return _assembler(request, repo).business_iq_overview(
        workspace=workspace, entitlement=resolve_current_entitlement(repo)
    )


@router.get(
    "/workspaces/{workspace_id}/business-iq/overview",
    operation_id="getWorkspaceBusinessIqOverview",
)
async def get_workspace_business_iq_overview(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    request: Request,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
):
    return _assembler(request, repo).business_iq_overview(
        workspace=workspace, entitlement=resolve_current_entitlement(repo)
    )


@router.get(
    "/projects/{project_id}/data-foundation/overview",
    operation_id="getProjectDataFoundationOverview",
)
async def get_project_data_foundation_overview(
    project_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
):
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    return _assembler(request, repo).data_foundation_overview(
        workspace=workspace, entitlement=resolve_current_entitlement(repo)
    )


@router.get(
    "/workspaces/{workspace_id}/data-foundation/overview-home",
    operation_id="getWorkspaceDataFoundationOverviewHome",
)
async def get_workspace_data_foundation_overview_home(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    request: Request,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
):
    return _assembler(request, repo).data_foundation_overview(
        workspace=workspace, entitlement=resolve_current_entitlement(repo)
    )


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/coverage",
    operation_id="getProjectCycleCoverage",
    response_model=CoverageReadModel,
)
async def get_project_cycle_coverage(
    project_id: str,
    cycle_id: str,
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> CoverageReadModel:
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    coverage = _assembler(request, repo).coverage(workspace=workspace, cycle_id=cycle_id)
    if coverage is None:
        raise resource_not_found()
    return coverage


@router.get(
    "/projects/{project_id}/cycles/{cycle_id}/tracks",
    operation_id="listProjectTracks",
    response_model=MeasurementTrackListResponse,
)
async def list_project_tracks(
    project_id: str,
    cycle_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MeasurementTrackListResponse:
    require_tenant()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id=cycle_id)
    return MeasurementTrackListResponse(items=[_track_response(item) for item in tracks])


@router.patch(
    "/projects/{project_id}/tracks/{track_id}",
    operation_id="patchProjectTrack",
    response_model=MeasurementTrackResponse,
)
async def patch_project_track(
    project_id: str,
    track_id: str,
    body: PatchMeasurementTrackRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MeasurementTrackResponse:
    require_tenant()
    track = repo.get_measurement_track(
        tenant_id=tenant.tenant_id, workspace_id=project_id, track_id=track_id
    )
    if track is None:
        raise resource_not_found()
    config = dict(default_config(track.track_type))
    config.update(track.config)
    if body.config:
        config.update(body.config)
    try:
        stored = repo.put_measurement_track(
            apply_track_mutation(track, config=config)
        )
    except TrackConfigurationImmutableError as exc:
        raise track_configuration_immutable() from exc
    return _track_response(stored)


@router.get("/organization", operation_id="getOrganization", response_model=OrganizationReadModel)
async def get_organization(
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> OrganizationReadModel:
    require_tenant()
    stored = repo.get_tenant(tenant.tenant_id)
    entitlement = resolve_current_entitlement(repo)
    membership = repo.get_membership_projection(
        tenant_id=tenant.tenant_id,
        provider="clerk",
        provider_user_id=tenant.user_id or "",
    )
    active = stored.active_workspace_count if stored is not None else 0
    return OrganizationReadModel(
        display_name=stored.display_name if stored is not None else tenant.tenant_id,
        current_plan=entitlement.plan_id,
        plan_status=entitlement.status.value,
        active_project_count=active,
        max_active_projects=entitlement.max_active_projects,
        user_role=membership.role if membership is not None else None,
        capabilities=capability_summary(entitlement),
    )

"""Project-scoped Marketing Identity Graph API. Tenant is never accepted from the client."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status

from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, require_tenant
from app.identity_graph.enums import CampaignStatus
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.service import CampaignIdentityService
from app.service.dependencies import authenticated_tenant, get_control_plane
from app.service.errors import ProblemFieldError, resource_not_found, validation_error
from app.service.identity_graph_models import CreateIdentityGraphCampaignRequest

router = APIRouter(
    prefix="/v1/projects/{project_id}/identity-graph",
    tags=["identity-graph"],
)


def get_identity_graph(request: Request) -> CampaignIdentityService:
    service = getattr(request.app.state, "identity_graph", None)
    if service is None:
        raise RuntimeError("Identity Graph service is not configured.")
    return service


def _require_project(
    *,
    tenant: TenantContext,
    repo: ControlPlaneRepository,
    project_id: str,
) -> None:
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()


@router.get("", operation_id="getIdentityGraph")
async def get_identity_graph_overview(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    return service.overview(
        tenant_id=tenant.tenant_id, project_id=project_id
    ).model_dump(mode="json")


@router.get("/campaigns", operation_id="listIdentityGraphCampaigns")
async def list_campaigns(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    rows = service.list_campaigns(tenant_id=tenant.tenant_id, project_id=project_id)
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post(
    "/campaigns",
    operation_id="createIdentityGraphCampaign",
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    project_id: str,
    body: CreateIdentityGraphCampaignRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    status_value = CampaignStatus.PLANNED
    if body.status is not None:
        try:
            status_value = CampaignStatus(body.status)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported campaign status.")]
            ) from exc
    try:
        result = service.create_campaign(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            name=body.name,
            actor_id=ctx.user_id or "unknown",
            description=body.description,
            status=status_value,
            market_ids=tuple(body.market_ids),
            channel_ids=tuple(body.channel_ids),
            parent_campaign_id=body.parent_campaign_id,
            start_date=body.start_date,
            end_date=body.end_date,
            utm_campaign=body.utm_campaign,
        )
    except IdentityGraphError as exc:
        raise validation_error(
            [ProblemFieldError(field="campaign", message=str(exc))]
        ) from exc
    return result.model_dump(mode="json")


@router.get("/sources", operation_id="listIdentityGraphSources")
async def list_sources(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    rows = service.list_sources(tenant_id=tenant.tenant_id, project_id=project_id)
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/markets", operation_id="listIdentityGraphMarkets")
async def list_markets(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    return {"items": service.list_markets(tenant_id=tenant.tenant_id, project_id=project_id)}


@router.get("/mappings", operation_id="listIdentityGraphMappings")
async def list_mappings(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    rows = service.list_mappings(tenant_id=tenant.tenant_id, project_id=project_id)
    return {"items": [item.model_dump(mode="json") for item in rows]}

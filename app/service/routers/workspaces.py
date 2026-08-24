from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.control_plane.models import Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import EntitlementUnavailableError, ProjectLimitReachedError
from app.core.tenancy import TenantContext, require_tenant
from app.service.dependencies import (
    authenticated_tenant,
    authorized_workspace,
    get_control_plane,
)
from app.service.entitlements import require_paid_capacity_mutation, resolve_current_entitlement
from app.service.errors import entitlement_unavailable, project_limit_reached
from app.service.models import CreateWorkspaceRequest, WorkspaceListResponse, WorkspaceResponse
from app.service.pagination import paginate_by_id

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


def _to_response(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        project_id=workspace.workspace_id,
        name=workspace.name,
        status=workspace.status.value,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.get("", operation_id="listWorkspaces", response_model=WorkspaceListResponse)
async def list_workspaces(
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
    cursor: str | None = None,
) -> WorkspaceListResponse:
    require_tenant()
    rows = repo.list_workspaces_for_tenant(tenant.tenant_id)
    page, next_cursor = paginate_by_id(
        rows, cursor=cursor, limit=limit, id_of=lambda item: item.workspace_id
    )
    return WorkspaceListResponse(
        items=[_to_response(item) for item in page],
        next_cursor=next_cursor,
    )


@router.post(
    "",
    operation_id="createWorkspace",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    body: CreateWorkspaceRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> WorkspaceResponse:
    require_tenant()
    snapshot = resolve_current_entitlement(repo)
    require_paid_capacity_mutation(snapshot)
    try:
        workspace = repo.create_workspace_with_capacity(
            tenant_id=tenant.tenant_id, name=body.name
        )
    except ProjectLimitReachedError as exc:
        raise project_limit_reached() from exc
    except EntitlementUnavailableError as exc:
        raise entitlement_unavailable() from exc
    return _to_response(workspace)


@router.get(
    "/{workspace_id}",
    operation_id="getWorkspace",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
) -> WorkspaceResponse:
    return _to_response(workspace)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, require_tenant
from app.project.capabilities import capability_summary
from app.service.auth import VerifiedIdentity
from app.service.dependencies import authenticated_tenant, get_control_plane
from app.service.entitlements import remaining_projects, resolve_current_entitlement
from app.service.models import (
    MeEntitlementSummary,
    MeOrganization,
    MePlan,
    MeProjectCapacity,
    MeProjectSummary,
    MeResponse,
    MeUser,
)

router = APIRouter(prefix="/v1", tags=["identity"])


@router.get("/me", operation_id="getMe", response_model=MeResponse)
async def get_me(
    request: Request,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> MeResponse:
    require_tenant()
    stored = repo.get_tenant(tenant.tenant_id)
    identity: VerifiedIdentity = request.state.verified_identity
    entitlement = resolve_current_entitlement(repo)
    active = stored.active_workspace_count if stored is not None else 0
    organization = MeOrganization(
        tenant_id=tenant.tenant_id,
        display_name=stored.display_name if stored is not None else tenant.tenant_id,
    )
    features = sorted(feature.value for feature in entitlement.features)
    capabilities = capability_summary(entitlement)
    projects = [
        MeProjectSummary(
            project_id=item.workspace_id,
            name=item.name,
            status=item.status.value,
        )
        for item in repo.list_workspaces_for_tenant(tenant.tenant_id)
    ]
    return MeResponse(
        user=MeUser(user_id=identity.provider_user_id),
        organization=organization,
        plan=MePlan(
            plan_id=entitlement.plan_id,
            status=entitlement.status.value,
            feature_summary=features,
        ),
        project_capacity=MeProjectCapacity(
            active_projects=active,
            max_active_projects=entitlement.max_active_projects,
            remaining_projects=remaining_projects(entitlement, active_projects=active),
        ),
        organizations=[organization],
        current_organization=organization,
        project_summaries=projects,
        entitlement_summary=MeEntitlementSummary(
            plan_id=entitlement.plan_id,
            status=entitlement.status.value,
            feature_summary=features,
            capabilities=capabilities,
        ),
    )

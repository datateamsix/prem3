"""Request-scoped authority dependencies for prem3-api."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.control_plane.models import (
    Dataset,
    IdentityProvider,
    MembershipProjection,
    MembershipStatus,
    TenantStatus,
    Workspace,
)
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import (
    AuthState,
    TenantContext,
    WorkspaceContext,
    bind_tenant,
    bind_workspace,
    require_tenant,
)
from app.service.auth import IdentityVerifier, VerifiedIdentity
from app.service.billing import BillingGateway
from app.service.clerk_runtime import MembershipAuthority, OrganizationDirectory, WebhookVerifier
from app.service.errors import entitlement_denied, resource_not_found, tenant_not_found
from app.service.evaluation_service import EvaluationService
from app.service.middleware import current_request_id
from app.service.provisioning import ensure_tenant_for_clerk_org
from app.service.security_log import security_log
from app.service.upload_service import UploadService

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description=(
        "Clerk session token forwarded by the Next.js BFF. "
        "prem3-api verifies the session token and resolves the PreM3 tenant "
        "from the Clerk Organization mapping. Tenant IDs are never accepted "
        "from the client."
    ),
)

BearerAuth = Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)]


def get_control_plane(request: Request) -> ControlPlaneRepository:
    return request.app.state.control_plane


def get_upload_service(request: Request) -> UploadService:
    service = getattr(request.app.state, "upload_service", None)
    if service is None:
        raise RuntimeError("Upload service is not configured.")
    return service


def get_evaluation_service(request: Request) -> EvaluationService:
    service = getattr(request.app.state, "evaluation_service", None)
    if service is None:
        raise RuntimeError("Evaluation service is not configured.")
    return service


def get_identity_verifier(request: Request) -> IdentityVerifier:
    return request.app.state.identity_verifier


def get_billing_gateway(request: Request) -> BillingGateway:
    return request.app.state.billing_gateway


def get_membership_authority(request: Request) -> MembershipAuthority | None:
    return getattr(request.app.state, "membership_authority", None)


def get_webhook_verifier(request: Request) -> WebhookVerifier | None:
    return getattr(request.app.state, "webhook_verifier", None)


def get_organization_directory(request: Request) -> OrganizationDirectory | None:
    return getattr(request.app.state, "organization_directory", None)


def _authorization_header(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is None:
        return None
    return f"{credentials.scheme} {credentials.credentials}"


def _project_membership(
    repo: ControlPlaneRepository,
    *,
    tenant_id: str,
    identity: VerifiedIdentity,
    status: MembershipStatus,
    role: str | None,
) -> None:
    repo.upsert_membership_projection(
        MembershipProjection(
            tenant_id=tenant_id,
            provider=IdentityProvider.CLERK,
            provider_user_id=identity.provider_user_id,
            provider_organization_id=identity.provider_organization_id,
            role=role,
            status=status,
            updated_at=datetime.now(UTC),
        )
    )


async def authenticated_tenant(
    request: Request,
    credentials: BearerAuth,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    verifier: Annotated[IdentityVerifier, Depends(get_identity_verifier)],
    membership_authority: Annotated[MembershipAuthority | None, Depends(get_membership_authority)],
) -> AsyncIterator[TenantContext]:
    identity = verifier.verify(_authorization_header(credentials))
    current: Any = None
    if membership_authority is not None:
        current = membership_authority.verify_current_membership(identity)
        if not current.active:
            tenant_id = repo.get_tenant_id_for_provider_org(
                provider=identity.provider,
                provider_organization_id=identity.provider_organization_id,
            )
            if tenant_id is not None:
                _project_membership(
                    repo,
                    tenant_id=tenant_id,
                    identity=identity,
                    status=MembershipStatus.REMOVED,
                    role=current.role,
                )
            security_log(
                "identity.membership_denied",
                provider_user_id=identity.provider_user_id,
                request_id=current_request_id() or None,
            )
            raise entitlement_denied()

    tenant_id = repo.get_tenant_id_for_provider_org(
        provider=identity.provider,
        provider_organization_id=identity.provider_organization_id,
    )
    if tenant_id is None:
        if membership_authority is None:
            raise tenant_not_found()
        tenant = ensure_tenant_for_clerk_org(
            repo,
            provider_organization_id=identity.provider_organization_id,
            display_name="Organization",
        )
        tenant_id = tenant.tenant_id
        security_log(
            "identity.tenant_mapped",
            tenant_id=tenant_id,
            provider_user_id=identity.provider_user_id,
            request_id=current_request_id() or None,
        )
    tenant = repo.get_tenant(tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE:
        raise tenant_not_found()

    if membership_authority is None:
        membership = repo.get_membership_projection(
            tenant_id=tenant_id,
            provider=identity.provider,
            provider_user_id=identity.provider_user_id,
        )
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise entitlement_denied()
    else:
        _project_membership(
            repo,
            tenant_id=tenant_id,
            identity=identity,
            status=MembershipStatus.ACTIVE,
            role=current.role if current is not None else None,
        )

    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=identity.provider_user_id,
        auth_state=AuthState.AUTHENTICATED,
        entitlement_snapshot_id=tenant.current_entitlement_snapshot_id,
    )
    request.state.verified_identity = identity
    security_log(
        "identity.authenticated",
        tenant_id=tenant_id,
        provider_user_id=identity.provider_user_id,
        request_id=current_request_id() or None,
    )
    with bind_tenant(ctx) as bound:
        yield bound


async def authorized_workspace(
    workspace_id: str,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
) -> AsyncIterator[Workspace]:
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=workspace_id
    )
    if workspace is None:
        raise resource_not_found()
    with bind_workspace(WorkspaceContext(workspace_id=workspace.workspace_id)) as _:
        yield workspace


async def authorized_project(
    project_id: str,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
) -> AsyncIterator[Workspace]:
    """Project_id is the Workspace alias. Tenant is never taken from the path as authority beyond lookup."""
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()
    with bind_workspace(WorkspaceContext(workspace_id=workspace.workspace_id)) as _:
        yield workspace


def authorized_dataset(
    dataset_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> Dataset:
    tenant = require_tenant()
    dataset = repo.get_dataset_for_workspace(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        dataset_id=dataset_id,
    )
    if dataset is None:
        raise resource_not_found()
    return dataset

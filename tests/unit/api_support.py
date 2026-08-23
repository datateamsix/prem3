"""Factory helpers for prem3-api tests. No GCP, Clerk, or Stripe."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.control_plane.entitlements import PlanId, entitlement_for_plan
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.control_plane.models import (
    EntitlementSource,
    IdentityProvider,
    IdentityProviderOrganizationMapping,
    MembershipProjection,
    MembershipStatus,
)
from app.service.app import create_app
from app.service.auth import (
    FakeIdentityVerifier,
    UnconfiguredIdentityVerifier,
    VerifiedIdentity,
)
from app.service.billing import UnavailableBillingGateway
from app.service.catalog import build_plan_catalog
from app.service.clerk_runtime import FakeClerkRuntime
from app.service.clerk_webhooks import sign_standard_webhook


def now() -> datetime:
    return datetime.now(UTC)


def seed_tenant(
    repo: InMemoryControlPlaneRepository,
    *,
    display_name: str = "Acme",
    provider_org: str = "org_acme",
    provider_user: str = "user_acme",
    plan_id: str = PlanId.PLANNER,
    membership_status: MembershipStatus = MembershipStatus.ACTIVE,
):
    mapping = IdentityProviderOrganizationMapping(
        provider=IdentityProvider.CLERK,
        provider_organization_id=provider_org,
        tenant_id="placeholder",
        created_at=now(),
        updated_at=now(),
    )
    tenant = repo.create_tenant(display_name=display_name, identity_mapping=mapping)
    if plan_id != PlanId.PLANNER:
        repo.put_entitlement_snapshot(
            entitlement_for_plan(
                tenant_id=tenant.tenant_id,
                plan_id=plan_id,
                source=EntitlementSource.MANUAL_GRANT,
            )
        )
    repo.upsert_membership_projection(
        MembershipProjection(
            tenant_id=tenant.tenant_id,
            provider=IdentityProvider.CLERK,
            provider_user_id=provider_user,
            provider_organization_id=provider_org,
            role="member",
            status=membership_status,
            updated_at=now(),
        )
    )
    identity = VerifiedIdentity(
        provider="clerk",
        provider_user_id=provider_user,
        provider_organization_id=provider_org,
    )
    return tenant, identity


def make_client(
    *,
    repo: InMemoryControlPlaneRepository | None = None,
    identity: VerifiedIdentity | None = None,
    identities: dict[str, VerifiedIdentity] | None = None,
    billing=None,
    billing_webhook_processor=None,
    catalog=None,
    unconfigured_auth: bool = False,
    membership_authority=None,
    webhook_verifier=None,
    organization_directory=None,
) -> tuple[TestClient, InMemoryControlPlaneRepository]:
    repository = repo or InMemoryControlPlaneRepository()
    if unconfigured_auth:
        verifier = UnconfiguredIdentityVerifier()
    else:
        verifier = FakeIdentityVerifier(default=identity, identities=identities)
    app = create_app(
        control_plane_repository=repository,
        identity_verifier=verifier,
        membership_authority=membership_authority,
        webhook_verifier=webhook_verifier,
        organization_directory=organization_directory,
        billing_gateway=billing if billing is not None else UnavailableBillingGateway(),
        billing_webhook_processor=billing_webhook_processor,
        plan_catalog=catalog or build_plan_catalog(checkout_eligible=False),
    )
    return TestClient(app, raise_server_exceptions=False), repository


def make_clerk_client(
    *,
    runtime: FakeClerkRuntime | None = None,
    repo: InMemoryControlPlaneRepository | None = None,
) -> tuple[TestClient, InMemoryControlPlaneRepository, FakeClerkRuntime]:
    repository = repo or InMemoryControlPlaneRepository()
    provider = runtime or FakeClerkRuntime()
    app = create_app(
        control_plane_repository=repository,
        identity_verifier=provider,
        membership_authority=provider,
        webhook_verifier=provider,
        organization_directory=provider,
        billing_gateway=UnavailableBillingGateway(),
    )
    return TestClient(app, raise_server_exceptions=False), repository, provider


def auth_header(token: str = "test-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signed_clerk_headers(
    body: bytes,
    *,
    secret: str,
    msg_id: str = "msg_test_1",
    timestamp: str | None = None,
) -> dict[str, str]:
    ts = timestamp or str(int(time.time()))
    signature = sign_standard_webhook(secret, body, msg_id=msg_id, timestamp=ts)
    return {
        "svix-id": msg_id,
        "svix-timestamp": ts,
        "svix-signature": signature,
    }

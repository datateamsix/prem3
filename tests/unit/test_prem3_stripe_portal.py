"""Mission 08 Stripe Customer Portal tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.entitlements import PlanId, entitlement_for_plan
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.control_plane.models import (
    BillingProvider,
    EntitlementSource,
    EntitlementStatus,
    StripeCustomerMapping,
)
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.stripe_support import make_stripe_client


def test_portal_requires_authentication() -> None:
    client, _ = make_client(unconfigured_auth=True)
    response = client.post("/v1/billing/portal-session", json={})
    assert response.status_code == 503
    assert response.json()["code"] == "AUTH_PROVIDER_NOT_CONFIGURED"


def test_portal_uses_server_customer_mapping() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo)
    client, stripe, gateway, _ = make_stripe_client(repo, identity)
    gateway.ensure_customer(tenant.tenant_id)
    response = client.post("/v1/billing/portal-session", headers=auth_header(), json={})
    assert response.status_code == 200
    mapping = repo.get_stripe_customer_mapping(tenant.tenant_id)
    assert mapping is not None
    assert stripe.portal_sessions[-1].customer_id == mapping.provider_customer_id


def test_portal_does_not_accept_customer_id() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo)
    client, *_ = make_stripe_client(repo, identity)
    rejected = client.post(
        "/v1/billing/portal-session",
        headers=auth_header(),
        json={"customer_id": "cus_injected"},
    )
    assert rejected.status_code == 422


def test_portal_return_url_server_owned() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo)
    client, stripe, gateway, _ = make_stripe_client(repo, identity)
    gateway.ensure_customer(tenant.tenant_id)
    response = client.post(
        "/v1/billing/portal-session",
        headers=auth_header(),
        json={"return_path": "/billing"},
    )
    assert response.status_code == 200
    assert stripe.portal_sessions[-1].url.startswith("https://billing.stripe.test/")


def test_portal_available_for_billing_recovery_policy() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    repo.put_entitlement_snapshot(
        entitlement_for_plan(
            tenant_id=tenant.tenant_id,
            plan_id=PlanId.PROJECT,
            source=EntitlementSource.BILLING_PROVIDER,
            status=EntitlementStatus.PAST_DUE,
        )
    )
    now = datetime.now(UTC)
    repo.put_stripe_customer_mapping(
        StripeCustomerMapping(
            tenant_id=tenant.tenant_id,
            billing_provider=BillingProvider.STRIPE,
            provider_customer_id="cus_recovery",
            created_at=now,
            updated_at=now,
        )
    )
    client, stripe, *_ = make_stripe_client(repo, identity)
    response = client.post("/v1/billing/portal-session", headers=auth_header(), json={})
    assert response.status_code == 200
    assert stripe.portal_sessions[-1].customer_id == "cus_recovery"


def test_portal_provider_failure_is_safe() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo)
    client, stripe, gateway, _ = make_stripe_client(repo, identity)
    gateway.ensure_customer(tenant.tenant_id)
    stripe.fail_portal = True
    response = client.post("/v1/billing/portal-session", headers=auth_header(), json={})
    assert response.status_code == 503
    assert response.json()["code"] == "BILLING_PROVIDER_UNAVAILABLE"


def test_portal_without_customer_mapping_is_stable() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, *_ = make_stripe_client(repo, identity)
    response = client.post("/v1/billing/portal-session", headers=auth_header(), json={})
    assert response.status_code == 409
    assert response.json()["code"] == "BILLING_CUSTOMER_UNAVAILABLE"

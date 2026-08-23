"""Billing contract tests. Stripe runtime is injected; default factory stays fail-closed."""

from __future__ import annotations

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.service.app import create_app
from app.service.billing import FakeBillingGateway
from tests.unit.api_support import auth_header, make_client, seed_tenant

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_checkout_requires_authentication() -> None:
    client, _ = make_client(unconfigured_auth=True)
    response = client.post("/v1/billing/checkout-session", json={"plan_id": "project"})
    assert response.status_code == 503
    assert response.json()["code"] == "AUTH_PROVIDER_NOT_CONFIGURED"


def test_portal_requires_authentication() -> None:
    client, _ = make_client(unconfigured_auth=True)
    response = client.post("/v1/billing/portal-session", json={})
    assert response.status_code == 503
    assert response.json()["code"] == "AUTH_PROVIDER_NOT_CONFIGURED"


def test_checkout_default_gateway_fails_closed() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, _ = make_client(repo=repo, identity=identity)
    response = client.post(
        "/v1/billing/checkout-session",
        headers=auth_header(),
        json={"plan_id": "project"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "BILLING_PROVIDER_NOT_CONFIGURED"


def test_portal_default_gateway_fails_closed() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, _ = make_client(repo=repo, identity=identity)
    response = client.post("/v1/billing/portal-session", headers=auth_header(), json={})
    assert response.status_code == 503
    assert response.json()["code"] == "BILLING_PROVIDER_NOT_CONFIGURED"


def test_checkout_fake_gateway_returns_redirect_contract() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PLANNER)
    client, _ = make_client(repo=repo, identity=identity, billing=FakeBillingGateway())
    response = client.post(
        "/v1/billing/checkout-session",
        headers=auth_header(),
        json={"plan_id": "project", "return_path": "/app"},
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://billing.test/checkout")
    assert "url" in response.json()


def test_portal_fake_gateway_returns_redirect_contract() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, _ = make_client(repo=repo, identity=identity, billing=FakeBillingGateway())
    response = client.post("/v1/billing/portal-session", headers=auth_header(), json={})
    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.test/portal"


def test_checkout_request_accepts_plan_id_not_price_id() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, _ = make_client(repo=repo, identity=identity, billing=FakeBillingGateway())
    rejected = client.post(
        "/v1/billing/checkout-session",
        headers=auth_header(),
        json={"plan_id": "project", "stripe_price_id": "price_123"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "VALIDATION_ERROR"


def test_portal_does_not_accept_customer_id() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, _ = make_client(repo=repo, identity=identity, billing=FakeBillingGateway())
    rejected = client.post(
        "/v1/billing/portal-session",
        headers=auth_header(),
        json={"customer_id": "cus_123"},
    )
    assert rejected.status_code == 422


def test_absolute_external_return_url_rejected_if_return_path_supported() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo)
    client, _ = make_client(repo=repo, identity=identity, billing=FakeBillingGateway())
    rejected = client.post(
        "/v1/billing/checkout-session",
        headers=auth_header(),
        json={"plan_id": "project", "return_path": "https://evil.example/phish"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "VALIDATION_ERROR"


def test_billing_webhook_not_processed_without_provider_adapter() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        "/v1/webhooks/billing",
        json={"id": "evt_unsigned", "type": "customer.subscription.updated"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "BILLING_PROVIDER_NOT_CONFIGURED"


def test_stripe_sdk_is_declared_as_a_pinned_dependency() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "stripe==15.5.0" in pyproject["project"]["dependencies"]

"""ProblemDetail and request-id contract tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.service.app import create_app
from tests.unit.api_support import auth_header, make_client, seed_tenant


def test_problem_detail_has_stable_code() -> None:
    client, _ = make_client(unconfigured_auth=True)
    response = client.get("/v1/me", headers=auth_header())
    body = response.json()
    assert body["code"] == "AUTH_PROVIDER_NOT_CONFIGURED"
    assert body["status"] == 503
    assert "type" in body
    assert "title" in body
    assert "request_id" in body


def test_validation_error_uses_problem_contract() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    response = client.post("/v1/workspaces", headers=auth_header(), json={})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"]


def test_request_id_present_on_problem() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/v1/me", headers={"X-Request-ID": "req_client_trace_001"})
    assert response.json()["request_id"] == "req_client_trace_001"
    assert response.headers["x-request-id"] == "req_client_trace_001"


def test_request_id_header_returned() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.headers["x-request-id"].startswith("req_")


def test_foreign_resource_problem_does_not_leak_existence() -> None:
    repo = InMemoryControlPlaneRepository()
    _a, identity_a = seed_tenant(repo, provider_org="org_a", provider_user="user_a")
    _b, identity_b = seed_tenant(
        repo,
        display_name="B",
        provider_org="org_b",
        provider_user="user_b",
        plan_id=PlanId.PROJECT,
    )
    client_b, _ = make_client(repo=repo, identity=identity_b)
    workspace = client_b.post(
        "/v1/workspaces", headers=auth_header(), json={"name": "Hidden"}
    ).json()
    client_a, _ = make_client(repo=repo, identity=identity_a)
    missing = client_a.get("/v1/workspaces/wsp_doesnotexist000000", headers=auth_header())
    foreign = client_a.get(
        f"/v1/workspaces/{workspace['workspace_id']}", headers=auth_header()
    )
    assert missing.json()["code"] == foreign.json()["code"] == "RESOURCE_NOT_FOUND"
    assert missing.json()["detail"] == foreign.json()["detail"]


def test_unhandled_error_does_not_return_stack_trace() -> None:
    app = create_app()

    @app.get("/__boom")
    def _boom() -> None:
        raise RuntimeError("secret-stack-trace")

    assert isinstance(app, FastAPI)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__boom")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "secret-stack-trace" not in response.text
    assert "Traceback" not in response.text

"""Helpers for Google connection / governance API tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.governance.codes import DRIVE_SCOPE, OPENID_SCOPES
from app.integrations.google.adapters import (
    FakeBigQueryClient,
    FakeDriveClient,
    FakeGoogleOAuthProvider,
    GoogleTokenSet,
)
from app.integrations.google.vault import InMemoryCredentialVault
from app.service.app import create_app
from app.service.auth import FakeIdentityVerifier
from app.service.billing import UnavailableBillingGateway
from app.service.catalog import build_plan_catalog
from app.service.object_store import FakeObjectStore
from app.service.upload_config import UploadConfig
from app.service.upload_service import UploadService
from app.service.upload_signing import FakeUploadSigner
from tests.unit.api_support import auth_header, seed_tenant


def google_harness(*, plan_id: str = PlanId.PROJECT, **app_kwargs):
    oauth = FakeGoogleOAuthProvider()
    drive = FakeDriveClient()
    bigquery = FakeBigQueryClient()
    vault = InMemoryCredentialVault()
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=plan_id)
    store = FakeObjectStore()
    signer = FakeUploadSigner()
    upload_service = UploadService(
        repo=repo,
        config=UploadConfig(
            raw_bucket="prem3-test-raw",
            signed_url_ttl_seconds=900,
            max_files=5,
            max_file_bytes=1024 * 1024,
            max_total_bytes=2 * 1024 * 1024,
            runtime_sa=None,
        ),
        signer=signer,
        object_store=store,
    )
    app = create_app(
        control_plane_repository=repo,
        identity_verifier=FakeIdentityVerifier(default=identity),
        billing_gateway=UnavailableBillingGateway(),
        plan_catalog=build_plan_catalog(checkout_eligible=False),
        upload_service=upload_service,
        google_oauth_provider=oauth,
        google_credential_vault=vault,
        google_drive_client=drive,
        google_bigquery_client=bigquery,
        **app_kwargs,
    )
    client = TestClient(app, raise_server_exceptions=False)
    workspace = client.post(
        "/v1/workspaces",
        headers=auth_header(),
        json={"name": "MMM One"},
    ).json()
    dataset = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets",
        headers=auth_header(),
        json={"name": "Sales"},
    ).json()
    return {
        "client": client,
        "repo": repo,
        "tenant": tenant,
        "identity": identity,
        "workspace": workspace,
        "dataset": dataset,
        "oauth": oauth,
        "drive": drive,
        "bigquery": bigquery,
        "vault": vault,
        "store": store,
    }


def connect_google(harness, *, capabilities: list[str], refresh_token: str | None = "rt-1") -> str:
    client = harness["client"]
    oauth: FakeGoogleOAuthProvider = harness["oauth"]
    started = client.post(
        "/v1/integrations/google/oauth/start",
        headers=auth_header(),
        json={
            "capabilities": capabilities,
            "workspace_id": harness["workspace"]["workspace_id"],
            "return_path": "/app/settings",
        },
    )
    assert started.status_code == 200, started.text
    state = parse_qs(urlparse(started.json()["authorization_url"]).query)["state"][0]
    code = f"code-{state[:8]}"
    scopes = list(OPENID_SCOPES)
    if "GOOGLE_DRIVE" in capabilities:
        scopes.append(DRIVE_SCOPE)
    if "BIGQUERY_READ" in capabilities:
        scopes.append("https://www.googleapis.com/auth/bigquery.readonly")
    if "BIGQUERY_WRITE" in capabilities:
        scopes.append("https://www.googleapis.com/auth/bigquery")
    oauth.seed_code(
        code,
        GoogleTokenSet(
            access_token="ya29.user-access",
            refresh_token=refresh_token,
            granted_scopes=tuple(scopes),
            google_subject="google-sub-1",
            display_email="user@example.com",
        ),
    )
    callback = client.get(
        "/v1/integrations/google/oauth/callback",
        params={"state": state, "code": code},
        follow_redirects=False,
    )
    assert callback.status_code == 302, callback.text
    listed = client.get("/v1/integrations/google/connections", headers=auth_header())
    assert listed.status_code == 200, listed.text
    return listed.json()["items"][0]["connection_id"]

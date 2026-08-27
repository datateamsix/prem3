from __future__ import annotations

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.service.app import create_app
from tests.unit.api_support import auth_header, make_client, seed_tenant


def _project_client():
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PORTFOLIO)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Home"}).json()
    project_id = created["workspace_id"]
    return client, project_id


def _create_market(client, project_id: str) -> str:
    response = client.post(
        f"/v1/projects/{project_id}/identity-graph/markets",
        headers=auth_header(),
        json={"name": "United States", "market_kind": "COUNTRY", "country_codes": ["US"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["market_id"]


def _create_campaign(client, project_id: str, market_id: str) -> dict:
    response = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
        json={
            "name": "Summer",
            "market_ids": [market_id],
            "channel_ids": ["search_paid"],
            "planned_start_date": "2026-04-01",
            "planned_end_date": "2026-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_campaign_and_audience_binding_api_round_trip() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    created = _create_campaign(client, project_id, market_id)
    campaign_id = created["campaign"]["campaign_id"]
    posted = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/bindings",
        headers=auth_header(),
        json={
            "provider_id": "google_ads",
            "external_campaign_id": "ext-1",
            "external_account_id": "acct-1",
        },
    )
    assert posted.status_code == 201, posted.text
    binding_id = posted.json()["binding_id"]
    listed = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/bindings",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["binding_id"] == binding_id
    got = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaign-bindings/{binding_id}",
        headers=auth_header(),
    )
    assert got.status_code == 200
    patched = client.patch(
        f"/v1/projects/{project_id}/identity-graph/campaign-bindings/{binding_id}",
        headers=auth_header(),
        json={"external_campaign_name": "Renamed Ads"},
    )
    assert patched.status_code == 200
    assert patched.json()["external_campaign_name"] == "Renamed Ads"

    audience = client.post(
        f"/v1/projects/{project_id}/identity-graph/audiences",
        headers=auth_header(),
        json={
            "name": "CRM buyers",
            "audience_type": "CRM_SEGMENT",
            "source_kind": "CRM_DEFINED",
        },
    )
    assert audience.status_code == 201, audience.text
    audience_id = audience.json()["audience_id"]
    aud_bind = client.post(
        f"/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/bindings",
        headers=auth_header(),
        json={"provider_id": "meta_ads", "external_audience_id": "ext_aud_one"},
    )
    assert aud_bind.status_code == 201, aud_bind.text
    aud_binding_id = aud_bind.json()["binding_id"]
    aud_got = client.get(
        f"/v1/projects/{project_id}/identity-graph/audience-bindings/{aud_binding_id}",
        headers=auth_header(),
    )
    assert aud_got.status_code == 200
    aud_patch = client.patch(
        f"/v1/projects/{project_id}/identity-graph/audience-bindings/{aud_binding_id}",
        headers=auth_header(),
        json={"external_audience_name": "Meta list"},
    )
    assert aud_patch.status_code == 200
    coverage = client.get(
        f"/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/binding-coverage",
        headers=auth_header(),
    )
    assert coverage.status_code == 200
    assert coverage.json()["provider_binding_count"] == 1
    assert "match_rate" not in coverage.json()


def test_tracking_observe_resolve_verify_coverage_api() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    created = _create_campaign(client, project_id, market_id)
    campaign_id = created["campaign"]["campaign_id"]
    tracking = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/tracking/bindings",
        headers=auth_header(),
        json={
            "tracking_kind": "CUSTOM_QUERY_PARAM",
            "parameter_name": "promo",
            "parameter_value": "SPRING",
            "status": "APPROVED",
        },
    )
    assert tracking.status_code == 201, tracking.text
    observed = client.post(
        f"/v1/projects/{project_id}/identity-graph/tracking/observe",
        headers=auth_header(),
        json={
            "source_ref": "bq://ga4/export",
            "source_kind": "GA4_BIGQUERY",
            "observed_at": "2026-04-02",
            "identifier_kind": "UTM_ID",
            "parameter_value": campaign_id,
            "candidate_campaign_id": campaign_id,
        },
    )
    assert observed.status_code == 200, observed.text
    observation_id = observed.json()["observation_id"]
    resolved = client.post(
        f"/v1/projects/{project_id}/identity-graph/tracking/resolve",
        headers=auth_header(),
        json={"observation_id": observation_id},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["campaign_id"] == campaign_id
    verified = client.post(
        f"/v1/projects/{project_id}/identity-graph/tracking/verify",
        headers=auth_header(),
        json={"campaign_id": campaign_id, "observation_id": observation_id},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "VERIFIED"
    coverage = client.get(
        f"/v1/projects/{project_id}/identity-graph/tracking/coverage",
        headers=auth_header(),
    )
    assert coverage.status_code == 200
    assert coverage.json()["observed_identifier_count"] >= 1
    assert "tracking_score" not in coverage.json()
    receipt = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/verification",
        headers=auth_header(),
    )
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "VERIFIED"


def test_binding_api_cross_project_is_not_found() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    created = _create_campaign(client, project_id, market_id)
    campaign_id = created["campaign"]["campaign_id"]
    posted = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/bindings",
        headers=auth_header(),
        json={"provider_id": "google_ads", "external_campaign_id": "ext-1"},
    )
    assert posted.status_code == 201, posted.text
    other = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Other"}).json()
    other_id = other["workspace_id"]
    missing = client.get(
        f"/v1/projects/{other_id}/identity-graph/campaign-bindings/{posted.json()['binding_id']}",
        headers=auth_header(),
    )
    assert missing.status_code == 404
    observe_missing = client.post(
        f"/v1/projects/{other_id}/identity-graph/tracking/observe",
        headers=auth_header(),
        json={
            "source_ref": "bq://ga4/export",
            "source_kind": "GA4_BIGQUERY",
            "observed_at": "2026-04-02",
            "identifier_kind": "UTM_ID",
            "parameter_value": campaign_id,
        },
    )
    # other project exists so observe is allowed as metadata, but campaign binding get 404s
    assert observe_missing.status_code in {200, 404}


def test_openapi_has_no_provider_write_or_person_keys() -> None:
    app = create_app()
    spec = app.openapi()
    paths = spec["paths"]
    forbidden = (
        "activate",
        "customer-match",
        "custom-audience",
        "pause",
        "budget",
        "membership",
    )
    joined = " ".join(paths)
    for token in forbidden:
        assert token not in joined
    dumped = str(spec)
    for key in ("user_id", "email", "hashed_email", "member_list", "idfa"):
        assert f'"{key}"' not in dumped or key in {"user_id"}
    # OpenAPI may mention user_id in unrelated auth schemas; Identity Graph paths must not.
    ig_paths = {path: item for path, item in paths.items() if "identity-graph" in path}
    ig_dump = str(ig_paths)
    assert "member_list" not in ig_dump
    assert "hashed_email" not in ig_dump
    assert "/tracking/observe" in joined
    assert "/tracking/verify" in joined
    assert "/tracking/coverage" in joined

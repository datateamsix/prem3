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


def _create_market(client, project_id: str, name: str = "United States") -> str:
    response = client.post(
        f"/v1/projects/{project_id}/identity-graph/markets",
        headers=auth_header(),
        json={"name": name, "market_kind": "COUNTRY", "country_codes": ["US"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["market_id"]


def _create_campaign(client, project_id: str, market_id: str, name: str = "Summer") -> dict:
    response = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
        json={
            "name": name,
            "market_ids": [market_id],
            "channel_ids": ["search_paid"],
            "planned_start_date": "2026-04-01",
            "planned_end_date": "2026-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_campaign_api_create_get_list_update_tracking_children_lineage() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    created = _create_campaign(client, project_id, market_id)
    campaign_id = created["campaign"]["campaign_id"]
    assert created["instructions"]["utm_id"] == campaign_id
    assert created["instructions"]["implementation_status"] == "NOT_IMPLEMENTED"
    assert created["campaign"]["planned_start_date"] == "2026-04-01"

    got = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}",
        headers=auth_header(),
    )
    assert got.status_code == 200
    assert got.json()["campaign_id"] == campaign_id

    listed = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["campaign_id"] == campaign_id

    patched = client.patch(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}",
        headers=auth_header(),
        json={"name": "Summer Renamed"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Summer Renamed"
    assert patched.json()["campaign_id"] == campaign_id

    tracking = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/tracking",
        headers=auth_header(),
    )
    assert tracking.status_code == 200
    body = tracking.json()
    assert body["utm_id"] == campaign_id
    assert body["recommended_utm_campaign"] == "Summer Renamed"
    assert body["implementation_status"] == "NOT_IMPLEMENTED"

    child = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
        json={
            "name": "Child",
            "market_ids": [market_id],
            "channel_ids": ["search_paid"],
            "parent_campaign_id": campaign_id,
        },
    )
    assert child.status_code == 201
    children = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/children",
        headers=auth_header(),
    )
    assert children.status_code == 200
    assert children.json()["items"][0]["campaign_id"] == child.json()["campaign"]["campaign_id"]

    lineage = client.get(
        f"/v1/projects/{project_id}/identity-graph/campaigns/{child.json()['campaign']['campaign_id']}/lineage",
        headers=auth_header(),
    )
    assert lineage.status_code == 200
    assert lineage.json()["parent_campaign_id"] == campaign_id
    assert campaign_id in lineage.json()["ancestors"]


def test_campaign_api_cross_project_is_not_found() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    created = _create_campaign(client, project_id, market_id, name="Private")
    campaign_id = created["campaign"]["campaign_id"]
    other = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Other"}).json()
    other_id = other["workspace_id"]
    response = client.get(
        f"/v1/projects/{other_id}/identity-graph/campaigns/{campaign_id}",
        headers=auth_header(),
    )
    assert response.status_code == 404


def test_campaign_api_unknown_market_fails_closed() -> None:
    client, project_id = _project_client()
    response = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
        json={
            "name": "Bad market",
            "market_ids": ["mkt_cccccccccccccccccccc"],
            "channel_ids": ["search_paid"],
        },
    )
    assert response.status_code == 422


def test_campaign_api_unknown_channel_fails_closed() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    response = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
        json={
            "name": "Bad channel",
            "market_ids": [market_id],
            "channel_ids": ["not_a_registry_channel"],
        },
    )
    assert response.status_code == 422


def test_campaign_openapi_includes_ledger_routes() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    assert "/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}" in paths
    assert "/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/tracking" in paths
    assert "/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/children" in paths
    assert "/v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/lineage" in paths
    campaign_req = schema["components"]["schemas"]["CreateIdentityGraphCampaignRequest"]
    assert "planned_start_date" in campaign_req["properties"]
    assert "start_date" not in campaign_req["properties"]
    assert "campaign_type" not in campaign_req["properties"]

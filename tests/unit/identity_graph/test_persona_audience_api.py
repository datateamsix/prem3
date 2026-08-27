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


def test_persona_and_audience_api_create_get_list_update_relations() -> None:
    client, project_id = _project_client()
    market_id = _create_market(client, project_id)
    persona_resp = client.post(
        f"/v1/projects/{project_id}/identity-graph/personas",
        headers=auth_header(),
        json={"name": "Core buyer", "market_ids": [market_id]},
    )
    assert persona_resp.status_code == 201, persona_resp.text
    persona_id = persona_resp.json()["persona_id"]
    assert persona_id.startswith("per_")
    assert persona_resp.json()["status"] == "DRAFT"

    got = client.get(
        f"/v1/projects/{project_id}/identity-graph/personas/{persona_id}",
        headers=auth_header(),
    )
    assert got.status_code == 200
    patched = client.patch(
        f"/v1/projects/{project_id}/identity-graph/personas/{persona_id}",
        headers=auth_header(),
        json={"name": "Core buyer renamed"},
    )
    assert patched.status_code == 200
    assert patched.json()["persona_id"] == persona_id
    assert patched.json()["name"] == "Core buyer renamed"

    audience_resp = client.post(
        f"/v1/projects/{project_id}/identity-graph/audiences",
        headers=auth_header(),
        json={
            "name": "CRM buyers",
            "audience_type": "CRM_SEGMENT",
            "source_kind": "CRM_DEFINED",
            "persona_ids": [persona_id],
            "market_ids": [market_id],
        },
    )
    assert audience_resp.status_code == 201, audience_resp.text
    audience_id = audience_resp.json()["audience_id"]
    assert audience_id.startswith("aud_")

    listed = client.get(
        f"/v1/projects/{project_id}/identity-graph/audiences",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["audience_id"] == audience_id

    personas = client.get(
        f"/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/personas",
        headers=auth_header(),
    )
    assert personas.status_code == 200
    assert personas.json()["items"][0]["persona_id"] == persona_id

    audiences = client.get(
        f"/v1/projects/{project_id}/identity-graph/personas/{persona_id}/audiences",
        headers=auth_header(),
    )
    assert audiences.status_code == 200
    assert audiences.json()["items"][0]["audience_id"] == audience_id

    child = client.post(
        f"/v1/projects/{project_id}/identity-graph/audiences",
        headers=auth_header(),
        json={
            "name": "Child",
            "audience_type": "CUSTOM",
            "source_kind": "USER_DECLARED",
            "parent_audience_id": audience_id,
        },
    )
    assert child.status_code == 201
    children = client.get(
        f"/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/children",
        headers=auth_header(),
    )
    assert children.status_code == 200
    assert children.json()["items"][0]["audience_id"] == child.json()["audience_id"]
    lineage = client.get(
        f"/v1/projects/{project_id}/identity-graph/audiences/{child.json()['audience_id']}/lineage",
        headers=auth_header(),
    )
    assert lineage.status_code == 200
    assert lineage.json()["parent_audience_id"] == audience_id

    campaign = client.post(
        f"/v1/projects/{project_id}/identity-graph/campaigns",
        headers=auth_header(),
        json={
            "name": "Targeted",
            "market_ids": [market_id],
            "channel_ids": ["search_paid"],
            "persona_ids": [persona_id],
            "audience_ids": [audience_id],
        },
    )
    assert campaign.status_code == 201, campaign.text
    persona_campaigns = client.get(
        f"/v1/projects/{project_id}/identity-graph/personas/{persona_id}/campaigns",
        headers=auth_header(),
    )
    assert persona_campaigns.status_code == 200
    assert persona_campaigns.json()["items"][0]["campaign_id"] == campaign.json()["campaign"][
        "campaign_id"
    ]


def test_persona_api_cross_project_is_not_found() -> None:
    client, project_id = _project_client()
    created = client.post(
        f"/v1/projects/{project_id}/identity-graph/personas",
        headers=auth_header(),
        json={"name": "Private"},
    )
    persona_id = created.json()["persona_id"]
    other = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Other"}).json()
    response = client.get(
        f"/v1/projects/{other['workspace_id']}/identity-graph/personas/{persona_id}",
        headers=auth_header(),
    )
    assert response.status_code == 404


def test_persona_audience_openapi_includes_ledger_routes() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    assert "/v1/projects/{project_id}/identity-graph/personas" in paths
    assert "/v1/projects/{project_id}/identity-graph/personas/{persona_id}" in paths
    assert "/v1/projects/{project_id}/identity-graph/personas/{persona_id}/audiences" in paths
    assert "/v1/projects/{project_id}/identity-graph/personas/{persona_id}/campaigns" in paths
    assert "/v1/projects/{project_id}/identity-graph/audiences" in paths
    assert "/v1/projects/{project_id}/identity-graph/audiences/{audience_id}" in paths
    assert "/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/personas" in paths
    assert "/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/campaigns" in paths
    assert "/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/children" in paths
    assert "/v1/projects/{project_id}/identity-graph/audiences/{audience_id}/lineage" in paths
    audience_req = schema["components"]["schemas"]["CreateIdentityGraphAudienceRequest"]
    assert "member_list" not in audience_req["properties"]
    assert "estimated_size" not in audience_req["properties"]
    assert "match_rate" not in audience_req["properties"]


def test_openapi_examples_contain_no_person_identifier_keys() -> None:
    schema = create_app().openapi()
    prohibited = {
        "email",
        "phone",
        "user_id",
        "user_pseudo_id",
        "member_list",
        "hashed_member_list",
        "idfa",
        "gaid",
        "mobile_advertising_id",
    }

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"example", "examples"} and isinstance(value, dict):
                    assert prohibited.isdisjoint(value.keys())
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    identity_paths = {
        path: spec
        for path, spec in schema["paths"].items()
        if "identity-graph" in path
    }
    _walk(identity_paths)
    _walk(schema.get("components", {}))

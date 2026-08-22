from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.business_iq.conftest import ready_payload


def test_business_iq_profile_api_is_workspace_scoped() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Home"}).json()
    workspace_id = created["workspace_id"]
    response = client.post(
        f"/v1/workspaces/{workspace_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kpi"] == "Revenue"
    ready = client.get(
        f"/v1/workspaces/{workspace_id}/business-iq/ready",
        headers=auth_header(),
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "BUSINESS_CONTEXT_READY"
    brief = client.post(
        f"/v1/workspaces/{workspace_id}/business-iq/brief",
        headers=auth_header(),
    )
    assert brief.status_code == 200
    assert brief.json()["advisory"] is True

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from tests.unit.api_support import auth_header, make_client, seed_tenant


def test_data_foundation_overview_is_workspace_scoped() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Home"}).json()
    response = client.get(
        f"/v1/workspaces/{created['workspace_id']}/data-foundation",
        headers=auth_header(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["foundation_ready"] is False
    assert body["live_cloud_proof"] == "LIVE_CLOUD_PROOF_NOT_RUN"


def test_data_foundation_unknown_workspace_is_not_found() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    response = client.get(
        "/v1/workspaces/wsp_missing00000000001/data-foundation",
        headers=auth_header(),
    )
    assert response.status_code == 404

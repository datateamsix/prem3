from __future__ import annotations

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.privacy import PROHIBITED_PERSON_FIELDS
from app.service.app import create_app
from tests.unit.api_support import auth_header, make_client, seed_tenant


def _walk(payload) -> list[str]:
    keys: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.append(str(key))
            keys.extend(_walk(value))
    elif isinstance(payload, list):
        for item in payload:
            keys.extend(_walk(item))
    return keys


def _assert_no_person_keys(payload) -> None:
    person_keys = {key.lower() for key in _walk(payload)} & PROHIBITED_PERSON_FIELDS
    assert not person_keys
    assert "rows" not in (payload if isinstance(payload, dict) else {})
    assert "sessions" not in (payload if isinstance(payload, dict) else {})


def _project_client():
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PORTFOLIO)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Home"}).json()
    return client, created["workspace_id"], tenant.tenant_id


def _ready_source(client, project_id: str) -> str:
    market = client.post(
        f"/v1/projects/{project_id}/identity-graph/markets",
        headers=auth_header(),
        json={"name": "United States", "market_kind": "COUNTRY", "country_codes": ["US"]},
    )
    assert market.status_code == 201, market.text
    market_id = market.json()["market_id"]
    source = client.post(
        f"/v1/projects/{project_id}/identity-graph/sources",
        headers=auth_header(),
        json={
            "ga4_property_id": "analytics_us",
            "bq_project_id": "modelready-m3",
            "bq_dataset_id": "analytics_us",
            "bq_location": "US",
            "declared_market_ids": [market_id],
            "overlap_policy": "DISJOINT",
            "topology_kind": "SINGLE_MASTER_PROPERTY",
        },
    )
    assert source.status_code == 201, source.text
    validated = client.post(
        f"/v1/projects/{project_id}/identity-graph/ga4-topology/validate",
        headers=auth_header(),
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["state"] == "GA4_TOPOLOGY_READY"
    return source.json()["ga4_source_binding_id"]


def test_analytics_overview_not_configured() -> None:
    client, project_id, _tenant_id = _project_client()
    response = client.get(
        f"/v1/projects/{project_id}/identity-graph/analytics",
        headers=auth_header(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "NOT_CONFIGURED"
    assert "compilation_id" in payload
    _assert_no_person_keys(payload)


def test_compile_fake_bq_round_trip_artifacts_and_readiness() -> None:
    client, project_id, tenant_id = _project_client()
    binding_id = _ready_source(client, project_id)
    service = client.app.state.identity_graph
    service.analytical_adapter.seed(
        tenant_id=tenant_id,
        project_id=project_id,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
            ),
        ),
    )
    compiled = client.post(
        f"/v1/projects/{project_id}/identity-graph/analytics/compile",
        headers=auth_header(),
        json={
            "selected_source_binding_ids": [binding_id],
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
        },
    )
    assert compiled.status_code == 201, compiled.text
    body = compiled.json()
    _assert_no_person_keys(body)
    assert body["status"] == "READY"
    assert body["phase"] == "READY"
    assert body["destination_dataset"] == "prem3_modeling"
    compilation_id = body["compilation_id"]
    tables = {item["table_name"] for item in body["artifact_refs"]}
    assert f"ga4_sessions_unified_{compilation_id}" in tables
    assert f"mta_session_touchpoints_{compilation_id}" in tables
    assert f"mta_journeys_{compilation_id}" in tables
    assert any(item.get("current_pointer") for item in body["artifact_refs"])

    sessions = service.analytical_adapter.read_back_sessions(compilation_id)
    touchpoints = service.analytical_adapter.read_back_touchpoints(compilation_id)
    journeys = service.analytical_adapter.read_back_journeys(compilation_id)
    assert len(sessions) == 1
    assert len(touchpoints) == 1
    assert len(journeys) == 1
    assert "user_pseudo_id" not in sessions[0].model_dump()

    readiness = client.get(
        f"/v1/projects/{project_id}/identity-graph/analytics/readiness",
        headers=auth_header(),
    )
    assert readiness.status_code == 200, readiness.text
    receipt = readiness.json()
    _assert_no_person_keys(receipt)
    assert receipt["state"] == "READY"
    assert receipt["compilation_id"] == compilation_id
    assert receipt["session_count"] == 1
    assert receipt["session_denominator"] == 1
    assert receipt["touchpoint_count"] == 1
    assert receipt["journey_count"] == 1
    assert receipt["settlement_status"] == "DAILY_SETTLED"

    artifacts = client.get(
        f"/v1/projects/{project_id}/identity-graph/analytics/artifacts",
        headers=auth_header(),
    )
    assert artifacts.status_code == 200, artifacts.text
    artifact_body = artifacts.json()
    _assert_no_person_keys(artifact_body)
    assert artifact_body["status"] == "READY"
    assert artifact_body["compilation_id"] == compilation_id
    assert len(artifact_body["artifact_refs"]) >= 3

    issues = client.get(
        f"/v1/projects/{project_id}/identity-graph/analytics/issues",
        headers=auth_header(),
    )
    assert issues.status_code == 200, issues.text
    _assert_no_person_keys(issues.json())
    missing = client.get(
        "/v1/projects/wsp_otherproject000001/identity-graph/analytics",
        headers=auth_header(),
    )
    assert missing.status_code == 404


def test_analytics_openapi_has_no_person_identifier_keys() -> None:
    schema = create_app().openapi()
    prefix = "/v1/projects/{project_id}/identity-graph/analytics"
    assert f"{prefix}" in schema["paths"]
    assert f"{prefix}/compile" in schema["paths"]
    assert f"{prefix}/readiness" in schema["paths"]
    assert f"{prefix}/artifacts" in schema["paths"]
    assert f"{prefix}/issues" in schema["paths"]
    payload = schema["paths"][prefix]
    person_keys = {key.lower() for key in _walk(payload)} & PROHIBITED_PERSON_FIELDS
    assert not person_keys
    compile_op = schema["paths"][f"{prefix}/compile"]["post"]
    compile_keys = {key.lower() for key in _walk(compile_op)} & PROHIBITED_PERSON_FIELDS
    assert not compile_keys

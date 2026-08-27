"""P6-01 Investment Plan HTTP routes. Metadata only; Drive owns amounts."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.entitlements import PlanId
from app.identity_graph.contracts import CanonicalMarket
from app.identity_graph.enums import MarketKind, MarketStatus
from app.identity_graph.ids import new_market_id
from app.investment_planning.drive_binding import CSV_MIME
from tests.unit.api_support import auth_header, seed_tenant
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.google_support import google_harness
from tests.unit.test_prem3_drive_governance import _setup_drive


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def _create_profile(harness) -> str:
    workspace_id = harness["workspace"]["workspace_id"]
    response = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert response.status_code == 200, response.text
    return workspace_id


def _seed_market(harness, *, project_id: str, name: str = "DACH") -> str:
    market_id = new_market_id()
    harness["client"].app.state.identity_graph_store.put_market(
        CanonicalMarket(
            market_id=market_id,
            tenant_id=harness["tenant"].tenant_id,
            project_id=project_id,
            name=name,
            market_kind=MarketKind.MULTI_COUNTRY_REGION,
            status=MarketStatus.ACTIVE,
            country_codes=("DE", "AT", "CH"),
            created_at=_now(),
            updated_at=_now(),
            created_by="user_acme",
        )
    )
    return market_id


def _create_plan(client, project_id: str, name: str = "FY2027") -> dict:
    created = client.post(
        f"/v1/projects/{project_id}/investment-plans",
        headers=auth_header(),
        json={"name": name, "fiscal_year": 2027},
    )
    assert created.status_code == 200, created.text
    return created.json()


def _bind_csv(harness, *, project_id: str, plan_id: str, binding: dict, csv_bytes: bytes, name: str):
    uploaded = harness["drive"].upload_file(
        access_token="token",
        name=name,
        parent_id=binding["budget_plans_folder_id"],
        data=csv_bytes,
        mime_type=CSV_MIME,
    )
    bound = harness["client"].post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/sources/drive",
        headers=auth_header(),
        json={"drive_file_id": uploaded.file_id},
    )
    assert bound.status_code == 200, bound.text
    return uploaded, bound.json()


def test_investment_plan_http_create_list_get_and_workspace_alias() -> None:
    harness = google_harness()
    _setup_drive(harness)
    project_id = _create_profile(harness)
    client = harness["client"]
    plan = _create_plan(client, project_id, name="FY2027 Marketing Plan")
    assert plan["project_id"] == project_id
    assert plan["workspace_id"] == project_id
    assert "250000" not in str(plan)
    listed = client.get(
        f"/v1/projects/{project_id}/investment-plans",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["plan_id"] == plan["plan_id"]
    assert listed.headers.get("cache-control") == "private, no-store"
    fetched = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan['plan_id']}",
        headers=auth_header(),
    )
    assert fetched.status_code == 200
    alias = client.get(
        f"/v1/workspaces/{project_id}/investment-plans/{plan['plan_id']}",
        headers=auth_header(),
    )
    assert alias.status_code == 200
    assert alias.json()["plan_id"] == plan["plan_id"]
    assert alias.json() == fetched.json()
    ready = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan['plan_id']}/ready",
        headers=auth_header(),
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "PENDING"
    assert fetched.headers.get("cache-control") == "private, no-store"
    assert fetched.headers.get("pragma") == "no-cache"


def test_investment_plan_http_full_lifecycle_ready_after_approval() -> None:
    harness = google_harness()
    _connection_id, binding = _setup_drive(harness)
    project_id = _create_profile(harness)
    market_id = _seed_market(harness, project_id=project_id)
    client = harness["client"]
    plan = _create_plan(client, project_id)
    plan_id = plan["plan_id"]
    csv_bytes = (
        f"market_id,channel,Q1,Q2,Q3,Q4\n{market_id},search_paid,100,100,100,100\n"
    ).encode()
    original, bound = _bind_csv(
        harness,
        project_id=project_id,
        plan_id=plan_id,
        binding=binding,
        csv_bytes=csv_bytes,
        name="plan.csv",
    )
    assert "250000" not in str(bound)
    mapping_id = bound["mapping"]["mapping_id"]
    mapped = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/mapping",
        headers=auth_header(),
        json={"mapping_id": mapping_id},
    )
    assert mapped.status_code == 200
    first = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/validate",
        headers=auth_header(),
        json={"mapping_id": mapping_id, "blanks_acknowledged": True},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "INVESTMENT_PLAN_READY"
    before_approve = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/ready",
        headers=auth_header(),
    )
    assert before_approve.json()["status"] == "PENDING"
    original_payload = harness["drive"].payloads[original.file_id]
    saved = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/save-version",
        headers=auth_header(),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["drive_file_id"] != original.file_id
    assert saved.json()["predecessor_source_version_id"] == bound["source"]["source_version_id"]
    assert harness["drive"].payloads[original.file_id] == original_payload
    second = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/validate",
        headers=auth_header(),
        json={"blanks_acknowledged": True},
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "INVESTMENT_PLAN_READY"
    stale_approve = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/approve",
        headers=auth_header(),
        json={"receipt_id": first.json()["receipt_id"]},
    )
    assert stale_approve.status_code == 403
    approved = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/approve",
        headers=auth_header(),
        json={"receipt_id": second.json()["receipt_id"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["active_source_version_id"] == saved.json()["source_version_id"]
    assert harness["drive"].payloads[original.file_id] == original_payload
    assert harness["drive"].payloads[saved.json()["drive_file_id"]] == original_payload
    ready = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/ready",
        headers=auth_header(),
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "INVESTMENT_PLAN_READY"
    mutate = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/save-version",
        headers=auth_header(),
    )
    assert mutate.status_code == 403
    revised = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/revise",
        headers=auth_header(),
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["plan_id"] != plan_id
    assert revised.json()["revision"] == plan["revision"] + 1
    assert revised.json()["predecessor_plan_id"] == plan_id
    assert revised.json()["status"] == "DRAFT"
    assert revised.json()["active_source_version_id"] is None
    still_ready = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/ready",
        headers=auth_header(),
    )
    assert still_ready.json()["status"] == "INVESTMENT_PLAN_READY"
    draft_ready = client.get(
        f"/v1/projects/{project_id}/investment-plans/{revised.json()['plan_id']}/ready",
        headers=auth_header(),
    )
    assert draft_ready.json()["status"] == "PENDING"
    alias = client.get(
        f"/v1/workspaces/{project_id}/investment-plans/{plan_id}/ready",
        headers=auth_header(),
    )
    assert alias.json() == still_ready.json()


def test_investment_plan_http_drive_source_validate_fails_closed_without_canonical_market() -> None:
    harness = google_harness()
    _connection_id, binding = _setup_drive(harness)
    project_id = _create_profile(harness)
    client = harness["client"]
    plan_id = _create_plan(client, project_id)["plan_id"]
    csv_bytes = b"market_id,channel,Q1,Q2,Q3,Q4\nmkt_us,search_paid,250000,0,,100\n"
    _uploaded, bound = _bind_csv(
        harness,
        project_id=project_id,
        plan_id=plan_id,
        binding=binding,
        csv_bytes=csv_bytes,
        name="plan.csv",
    )
    assert "250000" not in str(bound)
    mapping_id = bound["mapping"]["mapping_id"]
    validated = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/validate",
        headers=auth_header(),
        json={"mapping_id": mapping_id, "blanks_acknowledged": True},
    )
    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert body["status"] != "INVESTMENT_PLAN_READY"
    assert "MARKETS_RESOLVED" in body["error_codes"]
    assert "250000" not in validated.text
    approved = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/approve",
        headers=auth_header(),
        json={"receipt_id": body["receipt_id"]},
    )
    assert approved.status_code == 409
    assert approved.json()["code"] == "UNRESOLVED_MARKET_IDENTITY"
    ready = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/ready",
        headers=auth_header(),
    )
    assert ready.json()["status"] == "PENDING"


def test_display_market_label_is_not_join_authority() -> None:
    harness = google_harness()
    _connection_id, binding = _setup_drive(harness)
    project_id = _create_profile(harness)
    _seed_market(harness, project_id=project_id, name="United States")
    plan_id = _create_plan(harness["client"], project_id)["plan_id"]
    _uploaded, bound = _bind_csv(
        harness,
        project_id=project_id,
        plan_id=plan_id,
        binding=binding,
        csv_bytes=b"market_id,channel,Q1,Q2,Q3,Q4\nUnited States,search_paid,1,1,1,1\n",
        name="labels.csv",
    )
    validated = harness["client"].post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/validate",
        headers=auth_header(),
        json={"mapping_id": bound["mapping"]["mapping_id"], "blanks_acknowledged": True},
    )
    assert validated.status_code == 200
    assert "MARKETS_RESOLVED" in validated.json()["error_codes"]
    assert validated.json()["status"] != "INVESTMENT_PLAN_READY"


def test_unknown_channel_id_fails_closed() -> None:
    harness = google_harness()
    _connection_id, binding = _setup_drive(harness)
    project_id = _create_profile(harness)
    market_id = _seed_market(harness, project_id=project_id)
    plan_id = _create_plan(harness["client"], project_id)["plan_id"]
    csv_bytes = (
        f"market_id,channel,Q1,Q2,Q3,Q4\n{market_id},not_a_registry_channel,1,1,1,1\n"
    ).encode()
    _uploaded, bound = _bind_csv(
        harness,
        project_id=project_id,
        plan_id=plan_id,
        binding=binding,
        csv_bytes=csv_bytes,
        name="channel.csv",
    )
    validated = harness["client"].post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/validate",
        headers=auth_header(),
        json={"mapping_id": bound["mapping"]["mapping_id"], "blanks_acknowledged": True},
    )
    assert validated.status_code == 200
    assert "CHANNELS_RESOLVED" in validated.json()["error_codes"]
    assert validated.json()["status"] != "INVESTMENT_PLAN_READY"


def test_cross_project_and_cross_tenant_access_fails() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _setup_drive(harness)
    project_id = _create_profile(harness)
    client = harness["client"]
    plan_id = _create_plan(client, project_id)["plan_id"]
    other = client.post(
        "/v1/workspaces",
        headers=auth_header(),
        json={"name": "Other Project"},
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["workspace_id"]
    for path, method, body in (
        (f"/v1/projects/{other_id}/investment-plans/{plan_id}", "GET", None),
        (f"/v1/projects/{other_id}/investment-plans/{plan_id}/ready", "GET", None),
        (f"/v1/projects/{other_id}/investment-plans/{plan_id}/save-version", "POST", None),
        (f"/v1/projects/{other_id}/investment-plans/{plan_id}/revise", "POST", None),
        (
            f"/v1/projects/{other_id}/investment-plans/{plan_id}/approve",
            "POST",
            {"receipt_id": "rcpt_aaaaaaaaaaaaaaaaaaa"},
        ),
        (f"/v1/projects/{other_id}/investment-plans/{plan_id}/template", "POST", None),
    ):
        kwargs: dict = {"headers": auth_header()}
        if body is not None:
            kwargs["json"] = body
        denied = client.request(method, path, **kwargs)
        assert denied.status_code == 404, (path, denied.status_code, denied.text)
    _tenant, other_identity = seed_tenant(
        harness["repo"],
        provider_org="org_other",
        provider_user="user_other",
        plan_id=PlanId.PROJECT,
    )
    harness["client"].app.state.identity_verifier.identities["other-token"] = other_identity
    foreign = client.get(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}",
        headers=auth_header("other-token"),
    )
    assert foreign.status_code == 404
    body_tenant = client.post(
        f"/v1/projects/{project_id}/investment-plans",
        headers=auth_header(),
        json={"name": "Evil", "fiscal_year": 2027, "tenant_id": "ten_evil"},
    )
    assert body_tenant.status_code == 422


def test_investment_plan_http_rejects_file_outside_budget_tree() -> None:
    harness = google_harness()
    _setup_drive(harness)
    project_id = _create_profile(harness)
    client = harness["client"]
    plan_id = _create_plan(client, project_id)["plan_id"]
    outsider = harness["drive"].upload_file(
        access_token="token",
        name="outside.csv",
        parent_id="folder_unrelated",
        data=b"market_id,channel,Q1,Q2,Q3,Q4\nmkt_us,search_paid,1,1,1,1\n",
        mime_type=CSV_MIME,
    )
    denied = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/sources/drive",
        headers=auth_header(),
        json={"drive_file_id": outsider.file_id},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "PLANNING_AUTHORITY_DENIED"


def test_investment_plan_http_requires_auth() -> None:
    harness = google_harness()
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].get(f"/v1/projects/{project_id}/investment-plans")
    assert response.status_code in {401, 403, 503}


def test_optimization_and_view_routes_remain_absent() -> None:
    harness = google_harness()
    project_id = harness["workspace"]["workspace_id"]
    client = harness["client"]
    for path in (
        f"/v1/projects/{project_id}/investment-optimizations",
        f"/v1/projects/{project_id}/investment-plans/ipln_aaaaaaaaaaaaaaaaaaaa/view",
    ):
        response = client.get(path, headers=auth_header())
        assert response.status_code == 404
    empty = client.get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert empty.status_code == 403
    schema = client.app.openapi()
    for route in schema.get("paths", {}):
        assert "investment-optimization" not in route

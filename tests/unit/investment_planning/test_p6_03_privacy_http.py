"""P6-03 Firestore privacy and HTTP authority/privacy proofs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.control_plane.entitlements import PlanId
from app.identity_graph.contracts import CanonicalMarket
from app.identity_graph.enums import MarketKind, MarketStatus
from app.identity_graph.ids import new_market_id
from app.investment_planning.actuals import RawActualSpendRow, TestOnlyActualSpendAdapter
from app.investment_planning.contracts import (
    ActualSpendAllocation,
    ActualSpendSourceRef,
    PortfolioView,
)
from app.investment_planning.coverage import assemble_evidence_coverage
from app.investment_planning.drive_binding import CSV_MIME
from app.investment_planning.enums import (
    ActualSpendAuthority,
    ActualSpendSourceKind,
    ActualSpendSourceStatus,
    PortfolioBaselineKind,
    PortfolioCoverageState,
    PortfolioObservationType,
)
from app.investment_planning.errors import PersistenceBarrierError
from app.investment_planning.ids import new_actuals_source_id
from app.investment_planning.observations import emit_portfolio_observations
from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore
from tests.unit.api_support import auth_header, seed_tenant
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.google_support import google_harness
from tests.unit.investment_planning.test_p6_00_architecture import _now
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A, _source
from tests.unit.investment_planning.test_p6_03_coverage_observations import _cell, _snapshot
from tests.unit.investment_planning.test_privacy_and_persistence import _view
from tests.unit.test_prem3_drive_governance import _setup_drive


def _seed_market(harness, *, project_id: str) -> str:
    market_id = new_market_id()
    harness["client"].app.state.identity_graph_store.put_market(
        CanonicalMarket(
            market_id=market_id,
            tenant_id=harness["tenant"].tenant_id,
            project_id=project_id,
            name="DACH",
            market_kind=MarketKind.MULTI_COUNTRY_REGION,
            status=MarketStatus.ACTIVE,
            country_codes=("DE", "AT", "CH"),
            created_at=_now(),
            updated_at=_now(),
            created_by="user_acme",
        )
    )
    return market_id


def _approve_plan(harness, *, project_id: str, binding: dict, market_id: str) -> str:
    client = harness["client"]
    profile = client.post(
        f"/v1/workspaces/{project_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert profile.status_code == 200, profile.text
    created = client.post(
        f"/v1/projects/{project_id}/investment-plans",
        headers=auth_header(),
        json={"name": "FY2027", "fiscal_year": 2027},
    )
    plan_id = created.json()["plan_id"]
    csv_bytes = f"market_id,channel,Q1,Q2,Q3,Q4\n{market_id},search_paid,100,50,25,25\n".encode()
    uploaded = harness["drive"].upload_file(
        access_token="token",
        name="plan.csv",
        parent_id=binding["budget_plans_folder_id"],
        data=csv_bytes,
        mime_type=CSV_MIME,
    )
    bound = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/sources/drive",
        headers=auth_header(),
        json={"drive_file_id": uploaded.file_id},
    )
    assert bound.status_code == 200, bound.text
    validated = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/validate",
        headers=auth_header(),
        json={"blanks_acknowledged": True},
    )
    approved = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/approve",
        headers=auth_header(),
        json={"receipt_id": validated.json()["receipt_id"]},
    )
    assert approved.status_code == 200, approved.text
    return plan_id


def _install_actuals(
    harness, *, project_id: str, market_id: str, amount: str = "40.00"
) -> ActualSpendSourceRef:
    source = ActualSpendSourceRef(
        actuals_source_id=new_actuals_source_id(),
        tenant_id=harness["tenant"].tenant_id,
        project_id=project_id,
        workspace_id=project_id,
        source_kind=ActualSpendSourceKind.SYNTHETIC,
        source_ref="synthetic:test",
        currency="USD",
        timezone="UTC",
        authority=ActualSpendAuthority.TEST_ONLY,
        status=ActualSpendSourceStatus.CONFIGURED,
        source_fingerprint="fp_http_actuals",
        created_at=datetime(2027, 2, 1, tzinfo=UTC),
        updated_at=datetime(2027, 2, 1, tzinfo=UTC),
        as_of=datetime(2027, 2, 1, tzinfo=UTC),
    )
    adapter = TestOnlyActualSpendAdapter(
        source=source,
        rows=(
            RawActualSpendRow(
                occurred_at=date(2027, 1, 15),
                market_id=market_id,
                channel_id="search_paid",
                amount=Decimal(amount),
                currency="USD",
                timezone="UTC",
                grain="day",
            ),
        ),
    )
    harness["client"].app.state.investment_planning._actuals = adapter
    return source


def test_portfolio_snapshot_ref_has_no_amounts() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _connection_id, binding = _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    _approve_plan(harness, project_id=project_id, binding=binding, market_id=market_id)
    body = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    ).json()
    snapshot = harness["client"].app.state.investment_planning_store.get_snapshot(
        body["snapshot_id"]
    )
    assert snapshot is not None
    dumped = snapshot.model_dump()
    assert "allocations" not in dumped
    assert snapshot.baseline_kind is PortfolioBaselineKind.APPROVED_PLAN


def test_actuals_source_ref_has_no_raw_rows() -> None:
    source = _source()
    dumped = source.model_dump()
    assert "amount" not in dumped
    assert "allocations" not in dumped
    store = InMemoryInvestmentPlanningMetadataStore()
    stored = store.put(source)
    assert stored.actuals_source_id == source.actuals_source_id


def test_observation_store_has_no_amount_arrays() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved="100.00", actual="140.00"),),
        coverage=assemble_evidence_coverage(snapshot=_snapshot(), actuals_source=_source()),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.PLAN_AND_ACTUALS,
        actuals_error_code=None,
        stale_actuals=False,
    )
    store = InMemoryInvestmentPlanningMetadataStore()
    for item in observations:
        stored = store.put(item)
        dumped = stored.model_dump()
        assert "amounts" not in dumped
        assert "value" not in dumped


def test_firestore_rejects_portfolio_view() -> None:
    store = InMemoryInvestmentPlanningMetadataStore()
    with pytest.raises(PersistenceBarrierError, match="CUSTOMER_AMOUNT_TRANSIENT"):
        store.put(_view())


def test_firestore_rejects_actual_spend_allocation() -> None:
    store = InMemoryInvestmentPlanningMetadataStore()
    row = ActualSpendAllocation(
        fiscal_year=2027,
        quarter=1,
        market_id=MARKET_A,
        channel_id="search_paid",
        amount=Decimal("10.00"),
        currency="USD",
        source_ref="asrc_aaaaaaaaaaaaaaaaaaa",
        missing=False,
    )
    with pytest.raises(PersistenceBarrierError, match="CUSTOMER_AMOUNT_TRANSIENT"):
        store.put(row)
    assert isinstance(_view(), PortfolioView)


def test_portfolio_response_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "private, no-store"
    assert response.headers.get("pragma") == "no-cache"


def test_portfolio_requires_portfolio_view_entitlement() -> None:
    harness = google_harness(plan_id=PlanId.PROJECT)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert response.status_code == 403


def test_client_cannot_supply_tenant_authority() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers={**auth_header(), "X-Tenant-ID": "ten_evil"},
        params={"tenant_id": "ten_evil"},
    )
    assert response.status_code == 200
    assert response.json()["coverage_state"] == "NEITHER"


def test_arbitrary_http_actual_rows_not_authoritative() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    posted = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
        json={"allocations": [{"market_id": MARKET_A, "amount": "999.00"}]},
    )
    assert posted.status_code == 405
    listed = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
        params={"actuals": "999.00"},
    )
    assert listed.status_code == 200
    assert listed.json()["coverage_state"] == "NEITHER"
    assert listed.json()["allocations"] == []


def test_cross_project_portfolio_access_fails() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    _tenant, other_identity = seed_tenant(
        harness["repo"],
        provider_org="org_other",
        provider_user="user_other",
        plan_id=PlanId.PORTFOLIO,
    )
    harness["client"].app.state.identity_verifier.identities["other-token"] = other_identity
    foreign = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header("other-token"),
    )
    assert foreign.status_code == 404


def test_workspace_alias_same_state() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _connection_id, binding = _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    _approve_plan(harness, project_id=project_id, binding=binding, market_id=market_id)
    canonical = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    alias = harness["client"].get(
        f"/v1/workspaces/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert canonical.status_code == 200
    assert alias.status_code == 200
    assert alias.json()["coverage_state"] == canonical.json()["coverage_state"]
    assert alias.json()["summary"] == canonical.json()["summary"]


def test_http_plan_and_actuals_and_actuals_only() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _connection_id, binding = _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    plan_id = _approve_plan(harness, project_id=project_id, binding=binding, market_id=market_id)
    _install_actuals(harness, project_id=project_id, market_id=market_id, amount="40.00")
    both = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert both.status_code == 200, both.text
    body = both.json()
    assert body["coverage_state"] == PortfolioCoverageState.PLAN_AND_ACTUALS.value
    assert body["baseline_kind"] == PortfolioBaselineKind.APPROVED_PLAN.value
    kinds = {item["kind"]: item for item in body["summary"]}
    assert kinds["APPROVED"]["value"] == "200.00"
    assert kinds["ACTUAL"]["value"] == "40.00"
    assert kinds["REMAINING"]["value"] == "60.00"
    assert body["remaining"]["missing"] is False
    assert body["variance"]["missing"] is False
    assert body["actuals_source_id"]
    assert "OPTIMIZATION_READY" not in str(body)
    types = {item["observation_type"] for item in body["observations"]}
    assert PortfolioObservationType.ACTUAL_BELOW_PLAN.value in types
    plan = harness["client"].get(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}",
        headers=auth_header(),
    ).json()
    assert plan["status"] == "APPROVED"
    snapshot = harness["client"].app.state.investment_planning_store.get_snapshot(
        body["snapshot_id"]
    )
    assert snapshot is not None
    assert snapshot.actuals_source_id == body["actuals_source_id"]
    source = harness["client"].app.state.investment_planning_store.get_actuals_source(
        body["actuals_source_id"]
    )
    assert source is not None
    assert source.authority is ActualSpendAuthority.TEST_ONLY

    other = google_harness(plan_id=PlanId.PORTFOLIO)
    _setup_drive(other)
    other_project = other["workspace"]["workspace_id"]
    other_market = _seed_market(other, project_id=other_project)
    other["client"].post(
        f"/v1/workspaces/{other_project}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    _install_actuals(other, project_id=other_project, market_id=other_market, amount="18.00")
    only = other["client"].get(
        f"/v1/projects/{other_project}/investment-portfolio",
        headers=auth_header(),
    )
    assert only.status_code == 200, only.text
    only_body = only.json()
    assert only_body["coverage_state"] == PortfolioCoverageState.ACTUALS_ONLY.value
    assert only_body["baseline_kind"] == PortfolioBaselineKind.ACTUAL_YTD.value
    only_kinds = {item["kind"] for item in only_body["summary"]}
    assert "APPROVED" not in only_kinds
    assert only_body["remaining"]["missing"] is True
    assert only_body["variance"]["missing"] is True
    assert only_body["summary"][0]["value"] == "18.00"

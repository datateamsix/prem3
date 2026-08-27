"""P6-02 portfolio snapshot + transient Drive-backed view."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.control_plane.entitlements import PlanId
from app.identity_graph.contracts import CanonicalMarket
from app.identity_graph.enums import MarketKind, MarketStatus
from app.identity_graph.ids import new_market_id
from app.investment_planning.contracts import (
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioEvidenceCoverage,
    PortfolioSourceFreshness,
)
from app.investment_planning.drive_binding import CSV_MIME
from app.investment_planning.enums import AmountKind, PortfolioBaselineKind, PortfolioCoverageState
from app.investment_planning.portfolio import (
    assemble_portfolio_view,
    baseline_for_coverage,
    coverage_state,
    remaining_amount,
    rollup_by_dimension,
)
from tests.unit.api_support import auth_header
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.google_support import google_harness
from tests.unit.test_prem3_drive_governance import _setup_drive


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def test_coverage_states_and_actuals_only_baseline() -> None:
    assert coverage_state(has_plan=True, has_actuals=True) is PortfolioCoverageState.PLAN_AND_ACTUALS
    assert coverage_state(has_plan=True, has_actuals=False) is PortfolioCoverageState.PLAN_ONLY
    assert coverage_state(has_plan=False, has_actuals=True) is PortfolioCoverageState.ACTUALS_ONLY
    assert coverage_state(has_plan=False, has_actuals=False) is PortfolioCoverageState.NEITHER
    assert baseline_for_coverage(PortfolioCoverageState.ACTUALS_ONLY) is (
        PortfolioBaselineKind.GOVERNED_ACTUALS
    )
    assert baseline_for_coverage(PortfolioCoverageState.ACTUALS_ONLY) is not (
        PortfolioBaselineKind.APPROVED_PLAN
    )


def test_decimal_rollups_and_remaining_do_not_treat_missing_as_zero() -> None:
    approved = MoneyAmount(
        kind=AmountKind.APPROVED, currency="USD", value=Decimal("100.10"), missing=False
    )
    actual = MoneyAmount(
        kind=AmountKind.ACTUAL, currency="USD", value=Decimal("40.05"), missing=False
    )
    missing_actual = MoneyAmount(
        kind=AmountKind.ACTUAL, currency="USD", value=None, missing=True
    )
    rows = (
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=1,
            market_id="mkt_a",
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(approved, actual),
        ),
        PortfolioAllocationView(
            fiscal_year=2027,
            quarter=2,
            market_id="mkt_a",
            channel_id="search_paid",
            channel_registry_version=1,
            amounts=(
                MoneyAmount(
                    kind=AmountKind.APPROVED, currency="USD", value=Decimal("50.20"), missing=False
                ),
                missing_actual,
            ),
        ),
    )
    remaining = remaining_amount(rows, currency="USD")
    assert remaining.missing is False
    assert remaining.value == Decimal("60.05")
    channels = rollup_by_dimension(rows, currency="USD", kind=AmountKind.APPROVED, by="channel")
    assert len(channels) == 1
    assert channels[0].channel_id == "search_paid"
    assert channels[0].amount.value == Decimal("150.30")
    view = assemble_portfolio_view(
        snapshot_id="psnap_aaaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
        fiscal_year=2027,
        currency="USD",
        baseline_kind=PortfolioBaselineKind.GOVERNED_ACTUALS,
        allocations=(),
        coverage=PortfolioEvidenceCoverage(),
        freshness=PortfolioSourceFreshness(),
    )
    assert view.baseline_kind is not PortfolioBaselineKind.APPROVED_PLAN
    assert view.summary.totals[0].kind is AmountKind.ACTUAL
    assert view.summary.totals[0].missing is True


def test_portfolio_http_plan_only_from_approved_drive_source() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _connection_id, binding = _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    profile = harness["client"].post(
        f"/v1/workspaces/{project_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert profile.status_code == 200, profile.text
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
    client = harness["client"]
    empty = client.get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["coverage_state"] == "NEITHER"
    assert empty.headers.get("cache-control") == "private, no-store"
    created = client.post(
        f"/v1/projects/{project_id}/investment-plans",
        headers=auth_header(),
        json={"name": "FY2027", "fiscal_year": 2027},
    )
    plan_id = created.json()["plan_id"]
    csv_bytes = (
        f"market_id,channel,Q1,Q2,Q3,Q4\n{market_id},search_paid,100,50,25,25\n"
    ).encode()
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
    assert validated.status_code == 200, validated.text
    approved = client.post(
        f"/v1/projects/{project_id}/investment-plans/{plan_id}/approve",
        headers=auth_header(),
        json={"receipt_id": validated.json()["receipt_id"]},
    )
    assert approved.status_code == 200, approved.text
    portfolio = client.get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert portfolio.status_code == 200, portfolio.text
    body = portfolio.json()
    assert body["coverage_state"] == "PLAN_ONLY"
    assert body["baseline_kind"] == "APPROVED_PLAN"
    assert body["snapshot_id"]
    assert portfolio.headers.get("cache-control") == "private, no-store"
    totals = {item["kind"]: item for item in body["summary"]}
    assert totals["APPROVED"]["value"] == "200"
    assert totals["APPROVED"]["missing"] is False
    assert body["remaining"]["missing"] is True
    assert body["channel_allocation"][0]["amount"]["value"] == "200"
    assert body["market_allocation"][0]["amount"]["value"] == "200"
    quarters = {item["quarter"]: item for item in body["quarterly"]}
    assert quarters[1]["summary"][0]["value"] == "100"
    assert quarters[2]["summary"][0]["value"] == "50"
    snapshot = client.app.state.investment_planning_store.get_snapshot(body["snapshot_id"])
    assert snapshot is not None
    assert "allocations" not in snapshot.model_dump()
    assert snapshot.baseline_kind is PortfolioBaselineKind.APPROVED_PLAN
    alias = client.get(
        f"/v1/workspaces/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert alias.status_code == 200
    assert alias.json()["coverage_state"] == "PLAN_ONLY"
    assert alias.json()["summary"] == body["summary"]

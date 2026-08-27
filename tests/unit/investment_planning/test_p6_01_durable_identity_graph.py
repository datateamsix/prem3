"""Durable Identity Graph store selection and Planning consumption."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.identity_graph.contracts import CanonicalMarket
from app.identity_graph.enums import MarketKind, MarketStatus
from app.identity_graph.firestore import FirestoreIdentityGraphStore
from app.identity_graph.ids import new_market_id
from app.identity_graph.store import InMemoryIdentityGraphStore
from app.investment_planning.drive_binding import CSV_MIME
from app.investment_planning.enums import InvestmentPlanReadyStatus
from app.investment_planning.markets import IdentityGraphMarketDirectory
from app.investment_planning.service import InvestmentPlanService
from app.service.app import create_app
from app.service.product_stores import build_identity_graph_store
from tests.unit.api_support import auth_header
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.google_support import google_harness
from tests.unit.support.fake_firestore import FakeFirestore
from tests.unit.test_prem3_drive_governance import _setup_drive


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def test_firestore_control_plane_selects_firestore_identity_graph_store() -> None:
    repo = FirestoreControlPlaneRepository(FakeFirestore())
    store = build_identity_graph_store(repo)
    assert isinstance(store, FirestoreIdentityGraphStore)
    app = create_app(control_plane_repository=repo)
    assert isinstance(app.state.identity_graph_store, FirestoreIdentityGraphStore)


def test_inmemory_control_plane_keeps_inmemory_identity_graph_store() -> None:
    store = build_identity_graph_store(InMemoryControlPlaneRepository())
    assert isinstance(store, InMemoryIdentityGraphStore)
    app = create_app()
    assert isinstance(app.state.identity_graph_store, InMemoryIdentityGraphStore)


def test_investment_plan_validates_market_through_durable_identity_graph() -> None:
    harness = google_harness()
    _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    profile = harness["client"].post(
        f"/v1/workspaces/{project_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert profile.status_code == 200, profile.text
    ig_store = FirestoreIdentityGraphStore(FakeFirestore())
    market_id = new_market_id()
    ig_store.put_market(
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
    loaded = ig_store.get_market(
        tenant_id=harness["tenant"].tenant_id,
        project_id=project_id,
        market_id=market_id,
    )
    assert loaded is not None
    assert loaded.market_id == market_id
    service = InvestmentPlanService(
        repo=harness["repo"],
        store=harness["client"].app.state.investment_planning_store,
        drive=harness["drive"],
        connections=harness["client"].app.state.google_connections,
        drive_bindings=harness["client"].app.state.drive_bindings,
        business_iq=harness["client"].app.state.business_iq_store,
        markets=IdentityGraphMarketDirectory(ig_store),
    )
    csv_bytes = (
        f"market_id,channel,Q1,Q2,Q3,Q4\n{market_id},search_paid,100,100,100,100\n"
    ).encode()
    ctx = TenantContext(
        tenant_id=harness["tenant"].tenant_id,
        user_id="user_acme",
        auth_state=AuthState.AUTHENTICATED,
    )
    with bind_tenant(ctx):
        plan = service.create_plan(
            project_id=project_id,
            name="FY2027 durable IG",
            fiscal_year=2027,
            actor_id="user_acme",
        )
        _source, _table, proposal = service.ingest_bytes(
            plan_id=plan.plan_id,
            project_id=project_id,
            file_name="durable_ig.csv",
            mime_type=CSV_MIME,
            data=csv_bytes,
            actor_id="user_acme",
        )
        receipt = service.validate(
            plan_id=plan.plan_id,
            project_id=project_id,
            mapping_id=proposal.mapping.mapping_id,
            blanks_acknowledged=True,
        )
    assert receipt.status is InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY
    assert "MARKETS_RESOLVED" not in receipt.error_codes
    assert market_id not in str(receipt.model_dump().get("flagged_headers", ()))
    assert "100" not in str(receipt.model_dump())

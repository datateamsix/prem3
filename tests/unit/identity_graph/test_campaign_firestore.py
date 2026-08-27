from __future__ import annotations

from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.identity_graph.firestore import FirestoreIdentityGraphStore
from app.identity_graph.service import CampaignIdentityService
from app.identity_graph.store import InMemoryIdentityGraphStore
from app.service.product_stores import build_identity_graph_store
from tests.unit.identity_graph.conftest import PROJECT_ID, REGISTRY_CHANNEL_ID, TENANT_ID
from tests.unit.support.fake_firestore import FakeFirestore


def test_cloud_control_plane_selects_firestore_identity_graph_store() -> None:
    repo = FirestoreControlPlaneRepository(FakeFirestore())
    store = build_identity_graph_store(repo)
    assert isinstance(store, FirestoreIdentityGraphStore)


def test_inmemory_control_plane_keeps_inmemory_identity_graph_store() -> None:
    store = build_identity_graph_store(InMemoryControlPlaneRepository())
    assert isinstance(store, InMemoryIdentityGraphStore)


def test_firestore_campaign_ledger_round_trip(tenant_ctx, biq_store) -> None:
    del tenant_ctx
    service = CampaignIdentityService(
        store=FirestoreIdentityGraphStore(FakeFirestore()),
        business_iq_store=biq_store,
    )
    market = service.create_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="US",
        actor_id="user-a",
    )
    created = service.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Persisted",
        actor_id="user-a",
        market_ids=(market.market_id,),
        channel_ids=(REGISTRY_CHANNEL_ID,),
        planned_start_date="2026-01-01",
        planned_end_date="2026-06-30",
    )
    loaded = service.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert loaded.fingerprint == created.campaign.fingerprint
    instructions = service.tracking_instructions(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert instructions.utm_id == created.campaign.campaign_id
    receipt = service.store.get_campaign_receipt(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert receipt is not None
    assert receipt.state.value == "READY"
    dumped = loaded.model_dump()
    assert "budget" not in dumped
    assert "impressions" not in dumped
    assert "user_id" not in dumped

from datetime import UTC, datetime

from app.business_iq.firestore import FirestoreBusinessIqStore
from app.business_iq.service import BusinessIqService
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.data_foundation.contracts import (
    FoundationPlan,
    FoundationPlanAction,
    MeasurementCycle,
    ResourceIdentity,
    SourceBinding,
    SourceContract,
    SourceFoundationReceipt,
)
from app.data_foundation.enums import (
    CycleCadence,
    FoundationPlanSection,
    LocationType,
    PlanActionKind,
    SourceFoundationStatus,
    TargetWindowStatus,
)
from app.data_foundation.firestore_store import FirestoreDataFoundationStore
from app.service.product_stores import build_product_stores
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.support.fake_firestore import FakeFirestore


def test_cloud_control_plane_selects_firestore_product_stores() -> None:
    repo = FirestoreControlPlaneRepository(FakeFirestore())
    biq, foundation = build_product_stores(repo)
    assert isinstance(biq, FirestoreBusinessIqStore)
    assert isinstance(foundation, FirestoreDataFoundationStore)


def test_inmemory_control_plane_keeps_inmemory_product_stores() -> None:
    biq, foundation = build_product_stores(InMemoryControlPlaneRepository())
    assert type(biq).__name__ == "InMemoryBusinessIqStore"
    assert type(foundation).__name__ == "InMemoryDataFoundationStore"


def test_firestore_business_iq_store_round_trips_profile(tenant_ctx) -> None:
    del tenant_ctx
    store = FirestoreBusinessIqStore(FakeFirestore())
    service = BusinessIqService(store=store)
    created = service.create_profile(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="user-a",
        payload=ready_payload(),
    )
    loaded = store.get_profile(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert loaded is not None
    assert loaded.profile_id == created.profile_id
    assert loaded.fingerprint == created.fingerprint
    versions = store.list_versions(profile_id=created.profile_id)
    assert versions[0].version == 1


def test_firestore_data_foundation_store_persists_cycle_binding_plan_receipt() -> None:
    store = FirestoreDataFoundationStore(FakeFirestore())
    now = datetime.now(UTC)
    cycle = store.put_cycle(
        MeasurementCycle(
            cycle_id="dfcyc_durable0000000001",
            tenant_id="tenant-a",
            workspace_id="wsp_test00000000000001",
            name="Q1",
            cadence=CycleCadence.QUARTERLY,
            data_cutoff="2026-03-31",
            target_window_start="2025-01-01",
            target_window_end="2026-03-31",
            target_window_status=TargetWindowStatus.CONFIRMED_DOWNSTREAM,
            business_profile_snapshot_id="bps_acme00000000000001",
            created_at=now,
            updated_at=now,
            created_by="user-a",
        )
    )
    binding = store.put_binding(
        SourceBinding(
            source_id="dfsrc_durable0000000001",
            tenant_id="tenant-a",
            workspace_id="wsp_test00000000000001",
            requirement_id=None,
            provider_id="google_ads",
            location_type=LocationType.BIGQUERY,
            resource=ResourceIdentity(
                location_type=LocationType.BIGQUERY,
                project_id="acme_analytics",
                dataset_id="marketing",
                table_id="google_ads_campaign_daily",
                logical_path="acme_analytics.marketing.google_ads_campaign_daily",
            ),
            contract=SourceContract(grain="daily"),
            lifecycle_state="BOUND",
            created_at=now,
            updated_at=now,
        )
    )
    plan = store.put_foundation_plan(
        FoundationPlan(
            plan_id="dfplan_durable0000000001",
            version=1,
            tenant_id="tenant-a",
            workspace_id="wsp_test00000000000001",
            fingerprint="a" * 64,
            actions=(
                FoundationPlanAction(
                    action_kind=PlanActionKind.REUSE,
                    section=FoundationPlanSection.INFRASTRUCTURE,
                    resource_type="gcp_project",
                    target="acme_analytics",
                    reason="reuse",
                    validation_method="identity",
                ),
            ),
            created_at=now,
        )
    )
    receipt = store.put_source_receipt(
        SourceFoundationReceipt(
            receipt_id="dfrct_durable0000000001",
            tenant_id="tenant-a",
            workspace_id="wsp_test00000000000001",
            source_ids=(binding.source_id,),
            executed_at=now,
            executed_by="user-a",
            status=SourceFoundationStatus.FOUNDATION_SOURCE_READY.value,
            status_code=SourceFoundationStatus.FOUNDATION_SOURCE_READY,
            governance_import_ready=True,
            premodel_review_remaining=False,
        )
    )
    assert store.get_cycle(cycle.cycle_id).name == "Q1"
    assert store.get_binding(binding.source_id).lifecycle_state == "BOUND"
    assert store.get_foundation_plan(plan.plan_id).fingerprint == plan.fingerprint
    assert store.get_current_source_receipt(binding.source_id).receipt_id == receipt.receipt_id
    listed = store.list_receipts(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert listed

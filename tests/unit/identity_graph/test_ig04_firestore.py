from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.firestore import FirestoreIdentityGraphStore
from app.identity_graph.privacy import PROHIBITED_PERSON_FIELDS
from app.identity_graph.service import CampaignIdentityService
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, seed_ready_property_per_market
from tests.unit.support.fake_firestore import FakeFirestore


def test_firestore_persists_metadata_not_rows(tenant_ctx, biq_store) -> None:
    del tenant_ctx
    client = FakeFirestore()
    service = CampaignIdentityService(
        store=FirestoreIdentityGraphStore(client),
        business_iq_store=biq_store,
    )
    fixture = seed_ready_property_per_market(service)
    service.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
            ),
        ),
    )
    compiled = service.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    loaded = service.store.get_compilation(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        compilation_id=compiled.compilation_id,
    )
    assert loaded is not None
    assert loaded.fingerprint == compiled.fingerprint
    dumped = loaded.model_dump(mode="json")
    person_keys = {key.lower() for key in _walk(dumped)} & PROHIBITED_PERSON_FIELDS
    assert not person_keys
    assert "user_pseudo_id" not in dumped
    assert not hasattr(service.store, "put_events")
    receipt = service.store.get_analytics_receipt(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt is not None
    assert receipt.compilation_id == compiled.compilation_id
    artifacts = service.store.list_analytics_artifacts(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        compilation_id=compiled.compilation_id,
    )
    assert artifacts
    assert all("events" not in item.model_dump() for item in artifacts)


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

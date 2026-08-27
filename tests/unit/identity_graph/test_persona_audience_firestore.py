from __future__ import annotations

from app.identity_graph.enums import AudienceSourceKind, AudienceType
from app.identity_graph.firestore import FirestoreIdentityGraphStore
from app.identity_graph.service import CampaignIdentityService
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID
from tests.unit.support.fake_firestore import FakeFirestore


def test_firestore_persona_and_audience_ledger_round_trip(tenant_ctx, biq_store) -> None:
    del tenant_ctx
    service = CampaignIdentityService(
        store=FirestoreIdentityGraphStore(FakeFirestore()),
        business_iq_store=biq_store,
    )
    persona = service.create_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Persisted persona",
        actor_id="user-a",
    )
    audience = service.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Persisted audience",
        actor_id="user-a",
        audience_type=AudienceType.FIRST_PARTY,
        source_kind=AudienceSourceKind.PREM3_DEFINED,
        persona_ids=(persona.persona_id,),
    )
    loaded_persona = service.get_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    loaded_audience = service.get_audience(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    assert loaded_persona.fingerprint == persona.fingerprint
    assert loaded_audience.fingerprint == audience.fingerprint
    persona_receipt = service.store.get_persona_receipt(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    audience_receipt = service.store.get_audience_receipt(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    assert persona_receipt is not None and persona_receipt.state.value == "READY"
    assert audience_receipt is not None and audience_receipt.state.value == "READY"
    dumped = loaded_audience.model_dump()
    assert "member_list" not in dumped
    assert "estimated_size" not in dumped
    assert "user_id" not in dumped

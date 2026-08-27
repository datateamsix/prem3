from __future__ import annotations

from app.identity_graph.enums import (
    AudienceSourceKind,
    AudienceType,
    ObservationSourceKind,
    ObservedIdentifierKind,
)
from app.identity_graph.firestore import FirestoreIdentityGraphStore
from app.identity_graph.service import CampaignIdentityService
from app.identity_graph.store import InMemoryIdentityGraphStore
from tests.unit.identity_graph.conftest import PROJECT_ID, REGISTRY_CHANNEL_ID, TENANT_ID
from tests.unit.support.fake_firestore import FakeFirestore


def test_firestore_binding_observation_resolution_receipt_coverage_round_trip(
    tenant_ctx, biq_store
) -> None:
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
    binding = service.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-fs",
        actor_id="user-a",
    )
    loaded_binding = service.get_external_binding(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, binding_id=binding.binding_id
    )
    assert loaded_binding.fingerprint == binding.fingerprint
    tracking = service.store.list_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert tracking[0].parameter_value == created.campaign.campaign_id
    observation = service.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=created.campaign.campaign_id,
        candidate_campaign_id=created.campaign.campaign_id,
    )
    loaded_obs = service.store.get_observation(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        observation_id=observation.observation_id,
    )
    assert loaded_obs is not None
    assert loaded_obs.source_ref == "bq://ga4/export"
    assert "event_rows" not in loaded_obs.model_dump()
    resolved = service.resolve_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        observation_id=observation.observation_id,
    )
    loaded_res = service.store.get_resolution(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        resolution_id=resolved.resolution_id,
    )
    assert loaded_res is not None
    assert loaded_res.campaign_id == created.campaign.campaign_id
    receipt = service.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        observation_id=observation.observation_id,
    )
    loaded_receipt = service.store.get_verification_receipt(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, receipt_id=receipt.receipt_id
    )
    assert loaded_receipt is not None
    assert loaded_receipt.status.value == "VERIFIED"
    coverage = service.tracking_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    loaded_coverage = service.store.get_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert loaded_coverage is not None
    assert loaded_coverage.fingerprint == coverage.fingerprint
    audience = service.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="CRM",
        actor_id="user-a",
        audience_type=AudienceType.CRM_SEGMENT,
        source_kind=AudienceSourceKind.CRM_DEFINED,
    )
    aud_bind = service.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="meta_ads",
        external_audience_id="ext_aud_fs",
        actor_id="user-a",
    )
    loaded_aud = service.get_audience_external_binding(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, binding_id=aud_bind.binding_id
    )
    assert loaded_aud.external_audience_id == "ext_aud_fs"
    assert not hasattr(service.store, "put_events")
    assert isinstance(InMemoryIdentityGraphStore(), InMemoryIdentityGraphStore)

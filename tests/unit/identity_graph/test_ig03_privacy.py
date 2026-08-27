from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.contracts import (
    AudienceExternalBinding,
    CampaignExternalBinding,
    TrackingObservation,
)
from app.identity_graph.enums import (
    AudienceSourceKind,
    AudienceType,
    ObservationSourceKind,
    ObservedIdentifierKind,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.privacy import reject_identity_graph_payload
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_audience_binding_contains_no_member_ids(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="CRM",
        actor_id="user-a",
        audience_type=AudienceType.CRM_SEGMENT,
        source_kind=AudienceSourceKind.CRM_DEFINED,
    )
    binding = graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="google_ads",
        external_audience_id="ext_aud_one",
        actor_id="user-a",
    )
    dumped = binding.model_dump()
    assert "member_list" not in dumped
    assert "user_id" not in dumped
    assert "email" not in dumped


def test_provider_binding_does_not_store_member_list() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)):
        AudienceExternalBinding(
            binding_id="igb_aaaaaaaaaaaaaaaaaaaa",
            audience_id="aud_aaaaaaaaaaaaaaaaaaaa",
            provider_id="google_ads",
            external_audience_id="ext_aud_one",
            member_list=["person-1"],  # type: ignore[call-arg]
        )


def test_no_email_phone_hashes_in_bindings() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)):
        CampaignExternalBinding(
            binding_id="igb_aaaaaaaaaaaaaaaaaaaa",
            campaign_id="cmp_aaaaaaaaaaaaaaaaaaaa",
            provider_id="google_ads",
            external_campaign_id="123",
            hashed_email="abc",  # type: ignore[call-arg]
        )


def test_no_user_ids_in_observations() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)):
        TrackingObservation(
            observation_id="igo_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            source_ref="bq://ga4/export",
            source_kind=ObservationSourceKind.GA4_BIGQUERY,
            observed_at="2026-04-01",
            identifier_kind=ObservedIdentifierKind.UTM_ID,
            parameter_value="cmp_aaaaaaaaaaaaaaaaaaaa",
            user_id="person-1",  # type: ignore[call-arg]
        )


def test_no_membership_equivalence_claim() -> None:
    assert "membership_identical" not in AudienceExternalBinding.model_fields
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload({"membership_identical": True})
    assert exc.value.code == "PERFORMANCE_FORBIDDEN"

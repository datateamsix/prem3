from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.contracts import TrackingObservation
from app.identity_graph.enums import (
    ObservationSourceKind,
    ObservationStatus,
    ObservedIdentifierKind,
    TrackingImplementationStatus,
)
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_observation_does_not_store_raw_event(graph) -> None:
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
            event_rows=[{"event_name": "page_view"}],  # type: ignore[call-arg]
        )
    assert not hasattr(graph.store, "put_events")


def test_observed_status_requires_governed_evidence_ref(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.observe_tracking(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            source_ref="  ",
            source_kind=ObservationSourceKind.GA4_BIGQUERY,
            observed_at="2026-04-01",
            identifier_kind=ObservedIdentifierKind.UTM_ID,
            parameter_value="cmp_aaaaaaaaaaaaaaaaaaaa",
        )
    assert exc.value.code == "SOURCE_REF_REQUIRED"


def test_declared_is_not_observed(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Declared", actor_id="user-a"
    )
    assert (
        created.instructions.implementation_status
        == TrackingImplementationStatus.NOT_IMPLEMENTED
    )
    assert created.instructions.implementation_status != TrackingImplementationStatus.OBSERVED


def test_observed_is_not_verified(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Observed", actor_id="user-a"
    )
    observation = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_CAMPAIGN,
        parameter_value="Observed",
        candidate_campaign_id=created.campaign.campaign_id,
    )
    assert observation.observation_status == ObservationStatus.RECORDED
    receipt = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        observation_id=observation.observation_id,
    )
    assert receipt.status.value != "VERIFIED"


def test_observation_preserves_source_provenance(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Provenance", actor_id="user-a"
    )
    observation = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export/sessions",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=created.campaign.campaign_id,
        candidate_campaign_id=created.campaign.campaign_id,
    )
    loaded = graph.store.get_observation(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        observation_id=observation.observation_id,
    )
    assert loaded is not None
    assert loaded.source_ref == "bq://ga4/export/sessions"
    assert loaded.source_kind == ObservationSourceKind.GA4_BIGQUERY
    assert loaded.evidence_fingerprint

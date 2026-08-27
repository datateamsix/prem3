from __future__ import annotations

import pytest

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.enums import BindingStatus, TrackingKind
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_campaign_gets_default_utm_id_binding(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    assert created.tracking.parameter_name == "utm_id"
    assert created.tracking.tracking_kind == TrackingKind.PREM3_UTM_ID
    assert created.tracking.status == BindingStatus.ACTIVE


def test_utm_id_equals_canonical_campaign_id(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    assert created.tracking.parameter_value == created.campaign.campaign_id
    assert created.instructions.utm_id == created.campaign.campaign_id
    assert created.instructions.query_parameters["utm_id"] == created.campaign.campaign_id


def test_campaign_rename_does_not_change_utm_id(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    utm_id = created.instructions.utm_id
    graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        updates={"name": "Always On Renamed"},
    )
    instructions = graph.tracking_instructions(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert instructions.utm_id == utm_id
    assert instructions.parameter_value == created.campaign.campaign_id
    assert instructions.recommended_utm_campaign == "Always On Renamed"
    assert instructions.implementation_status.value == "NOT_IMPLEMENTED"


def test_tracking_instructions_are_fingerprinted(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Tracked", actor_id="user-a"
    )
    assert created.instructions.fingerprint
    assert created.instructions.generation_provenance.value == "GENERATED"
    assert created.instructions.implementation_status.value == "NOT_IMPLEMENTED"
    assert created.instructions.parameter_name == "utm_id"


def test_tracking_not_marked_observed_or_verified(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Honest", actor_id="user-a"
    )
    assert created.instructions.implementation_status.value == "NOT_IMPLEMENTED"
    assert created.instructions.implementation_status.value not in {"OBSERVED", "VERIFIED"}


def test_campaign_name_not_used_as_identity(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(utm_campaign="Always On", fuzzy_name="Always On"),
    )
    assert created.campaign.name == "Always On"
    assert resolved.campaign_id is None
    assert resolved.source.value == "UNRESOLVED"


def test_custom_identifier_requires_explicit_rule(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Custom", actor_id="user-a"
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_custom_identifier(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=created.campaign.campaign_id,
            parameter_name="promo_code",
            parameter_value="SPRING",
            actor_id="user-a",
            status=BindingStatus.ACTIVE,
        )
    assert exc.value.code == "CUSTOM_IDENTIFIER_NOT_APPROVED"

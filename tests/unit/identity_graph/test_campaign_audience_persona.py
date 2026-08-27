from __future__ import annotations

import pytest

from app.identity_graph.enums import AudienceSourceKind, AudienceStatus, AudienceType, PersonaStatus
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_empty_audience_and_persona_ids_are_valid(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Empty scope", actor_id="user-a"
    )
    assert created.campaign.audience_ids == ()
    assert created.campaign.persona_ids == ()


def test_unknown_audience_ids_rejected(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Audience",
            actor_id="user-a",
            audience_ids=("aud_unknown0000000001",),
        )
    assert exc.value.code == "UNKNOWN_AUDIENCE"


def test_unknown_persona_ids_rejected(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Persona",
            actor_id="user-a",
            persona_ids=("per_unknown0000000001",),
        )
    assert exc.value.code == "UNKNOWN_PERSONA"


def test_known_audience_and_persona_ids_are_accepted(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Core buyer", actor_id="user-a"
    )
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="CRM buyers",
        actor_id="user-a",
        audience_type=AudienceType.CRM_SEGMENT,
        source_kind=AudienceSourceKind.CRM_DEFINED,
        persona_ids=(persona.persona_id,),
    )
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Targeted",
        actor_id="user-a",
        persona_ids=(persona.persona_id,),
        audience_ids=(audience.audience_id,),
    )
    assert created.campaign.persona_ids == (persona.persona_id,)
    assert created.campaign.audience_ids == (audience.audience_id,)


def test_campaign_without_audience_or_persona_remains_valid(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="No targeting", actor_id="user-a"
    )
    receipt = graph.validate_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert receipt.state.value == "READY"


def test_archived_target_rejected_on_live_campaign(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Archive me", actor_id="user-a"
    )
    graph.update_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        persona_id=persona.persona_id,
        updates={"status": PersonaStatus.ACTIVE},
    )
    graph.archive_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Live",
            actor_id="user-a",
            persona_ids=(persona.persona_id,),
        )
    assert exc.value.code == "ARCHIVED_TARGET"


def test_archived_campaign_may_keep_archived_audience_refs(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Historical segment",
        actor_id="user-a",
        audience_type=AudienceType.FIRST_PARTY,
        source_kind=AudienceSourceKind.PREM3_DEFINED,
    )
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Historical",
        actor_id="user-a",
        audience_ids=(audience.audience_id,),
    )
    graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        updates={"status": "ARCHIVED"},
    )
    graph.update_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        updates={"status": AudienceStatus.ACTIVE},
    )
    graph.archive_audience(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    updated = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        updates={"name": "Historical renamed"},
    )
    assert updated.audience_ids == (audience.audience_id,)
    assert updated.status.value == "ARCHIVED"


def test_campaign_does_not_store_audience_members(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="No members", actor_id="user-a"
    )
    dumped = created.campaign.model_dump()
    assert "audience_members" not in dumped
    assert "membership" not in dumped
    assert "user_id" not in dumped

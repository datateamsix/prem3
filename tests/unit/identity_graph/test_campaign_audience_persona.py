from __future__ import annotations

import pytest

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


def test_campaign_does_not_store_audience_members(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="No members", actor_id="user-a"
    )
    dumped = created.campaign.model_dump()
    assert "audience_members" not in dumped
    assert "membership" not in dumped
    assert "user_id" not in dumped

from __future__ import annotations

import pytest

from app.identity_graph.enums import CampaignOwnerType
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_owner_and_objective_are_optional(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="No owner", actor_id="user-a"
    )
    assert created.campaign.owner_type is None
    assert created.campaign.owner_ref is None
    assert created.campaign.objective_ref is None


def test_owner_is_metadata_only(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Owned",
        actor_id="user-a",
        owner_type=CampaignOwnerType.USER,
        owner_ref="user-a",
        owner_label="Alex",
    )
    assert created.campaign.owner_type == CampaignOwnerType.USER
    assert created.campaign.owner_ref == "user-a"
    listed = graph.list_campaigns(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, owner_ref="user-a"
    )
    assert [item.campaign_id for item in listed] == [created.campaign.campaign_id]


def test_unknown_objective_ref_fails_closed(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Bad objective",
            actor_id="user-a",
            objective_ref="obj_does_not_exist",
        )
    assert exc.value.code == "UNKNOWN_OBJECTIVE"


def test_known_biq_objective_ref_accepted(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Objective",
        actor_id="user-a",
        objective_ref="obj_allocate",
        objective_label="Allocate budget across channels",
    )
    assert created.campaign.objective_ref == "obj_allocate"

from __future__ import annotations

import pytest

from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_campaign_parent_same_project(graph) -> None:
    parent = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Parent", actor_id="user-a"
    )
    child = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Child",
        actor_id="user-a",
        parent_campaign_id=parent.campaign.campaign_id,
    )
    assert child.campaign.parent_campaign_id == parent.campaign.campaign_id


def test_campaign_cannot_parent_itself(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Solo", actor_id="user-a"
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.set_parent(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=created.campaign.campaign_id,
            parent_campaign_id=created.campaign.campaign_id,
        )
    assert exc.value.code == "SELF_PARENT"


def test_campaign_hierarchy_rejects_cycle(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="A", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="B",
        actor_id="user-a",
        parent_campaign_id=first.campaign.campaign_id,
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.set_parent(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=first.campaign.campaign_id,
            parent_campaign_id=second.campaign.campaign_id,
        )
    assert exc.value.code == "HIERARCHY_CYCLE"


def test_parent_child_identity_is_stable(graph) -> None:
    parent = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Parent", actor_id="user-a"
    )
    child = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Child",
        actor_id="user-a",
        parent_campaign_id=parent.campaign.campaign_id,
    )
    parent_id = parent.campaign.campaign_id
    child_id = child.campaign.campaign_id
    graph.set_parent(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=child_id,
        parent_campaign_id=parent_id,
    )
    found = graph.store.get_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, campaign_id=child_id
    )
    assert found is not None
    assert found.parent_campaign_id == parent_id
    assert found.campaign_id == child_id
    assert parent.campaign.campaign_id == parent_id

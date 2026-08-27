from __future__ import annotations

import pytest

from app.identity_graph.enums import CampaignStatus
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_lifecycle_transitions(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Lifecycle", actor_id="user-a"
    )
    campaign_id = created.campaign.campaign_id
    assert created.campaign.status == CampaignStatus.PLANNED
    active = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=campaign_id,
        updates={"status": CampaignStatus.ACTIVE},
    )
    assert active.status == CampaignStatus.ACTIVE
    paused = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=campaign_id,
        updates={"status": CampaignStatus.PAUSED},
    )
    assert paused.status == CampaignStatus.PAUSED
    resumed = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=campaign_id,
        updates={"status": CampaignStatus.ACTIVE},
    )
    complete = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=campaign_id,
        updates={"status": CampaignStatus.COMPLETE},
    )
    archived = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=campaign_id,
        updates={"status": CampaignStatus.ARCHIVED},
    )
    assert resumed.status == CampaignStatus.ACTIVE
    assert complete.status == CampaignStatus.COMPLETE
    assert archived.status == CampaignStatus.ARCHIVED
    assert archived.campaign_id == campaign_id


def test_invalid_lifecycle_transition_rejected(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Jump", actor_id="user-a"
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.update_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=created.campaign.campaign_id,
            updates={"status": CampaignStatus.COMPLETE},
        )
    assert exc.value.code == "STATUS_TRANSITION"


def test_archived_identity_persists(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Keep id", actor_id="user-a"
    )
    graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        updates={"status": CampaignStatus.ARCHIVED},
    )
    found = graph.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert found.status == CampaignStatus.ARCHIVED
    assert found.campaign_id == created.campaign.campaign_id


def test_referenced_campaign_not_hard_deleted(graph) -> None:
    parent = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Parent", actor_id="user-a"
    )
    graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Child",
        actor_id="user-a",
        parent_campaign_id=parent.campaign.campaign_id,
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.delete_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=parent.campaign.campaign_id,
        )
    assert exc.value.code == "CAMPAIGN_REFERENCED"
    assert (
        graph.get_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=parent.campaign.campaign_id,
        )
        is not None
    )


def test_unreferenced_draft_can_be_hard_deleted(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Draft", actor_id="user-a"
    )
    graph.delete_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.get_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=created.campaign.campaign_id,
        )
    assert exc.value.code == "UNKNOWN_CAMPAIGN"

from __future__ import annotations

import pytest

from app.identity_graph.enums import CampaignStatus
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_planned_dates_valid(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Flight",
        actor_id="user-a",
        planned_start_date="2026-01-01",
        planned_end_date="2026-03-31",
    )
    assert created.campaign.planned_start_date == "2026-01-01"
    assert created.campaign.planned_end_date == "2026-03-31"
    assert created.campaign.status == CampaignStatus.PLANNED


def test_planned_end_before_start_rejected(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Backwards",
            actor_id="user-a",
            planned_start_date="2026-03-31",
            planned_end_date="2026-01-01",
        )
    assert exc.value.code == "DATE_ORDER"


def test_evergreen_campaign_has_no_planned_dates(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    assert created.campaign.planned_start_date is None
    assert created.campaign.planned_end_date is None


def test_planned_date_change_updates_fingerprint(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Dated",
        actor_id="user-a",
        planned_start_date="2026-01-01",
        planned_end_date="2026-06-30",
    )
    original = created.campaign.fingerprint
    updated = graph.update_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        updates={"planned_end_date": "2026-12-31"},
    )
    assert updated.fingerprint != original
    assert updated.planned_end_date == "2026-12-31"
    assert updated.campaign_id == created.campaign.campaign_id

from __future__ import annotations

import re

import pytest

from app.identity_graph.contracts import CanonicalCampaign
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID

_URL_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


def test_campaign_id_is_server_generated(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Summer", actor_id="user-a"
    )
    assert first.campaign.campaign_id.startswith("cmp_")
    assert first.campaign.campaign_id != "Summer"


def test_campaign_id_is_url_safe(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Brand / Search", actor_id="user-a"
    )
    assert _URL_SAFE.fullmatch(created.campaign.campaign_id)


def test_campaign_id_not_derived_from_name(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="summer_sale_brand",
        actor_id="user-a",
    )
    assert "summer" not in created.campaign.campaign_id.lower()
    assert "sale" not in created.campaign.campaign_id.lower()
    assert "brand" not in created.campaign.campaign_id.lower()


def test_campaign_id_never_reused(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="One", actor_id="user-a"
    )
    clone = CanonicalCampaign(
        campaign_id=created.campaign.campaign_id,
        tenant_id=TENANT_ID,
        project_id="wsp_otherproject0000001",
        name="Two",
        created_by="user-a",
    )
    with pytest.raises(IdentityGraphError, match="cannot be reused") as exc:
        graph.store.put_campaign(clone)
    assert exc.value.code == "ID_REUSED"


def test_same_name_campaigns_have_distinct_ids(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    assert first.campaign.campaign_id != second.campaign.campaign_id

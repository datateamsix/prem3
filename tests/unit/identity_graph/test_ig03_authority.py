from __future__ import annotations

import pytest

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_provider_discovery_not_configured(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.discover_campaigns(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            provider_account_ref="acct-1",
        )
    assert exc.value.code == "DISCOVERY_NOT_CONFIGURED"
    with pytest.raises(IdentityGraphError) as exc:
        graph.discover_audiences(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            provider_account_ref="acct-1",
        )
    assert exc.value.code == "DISCOVERY_NOT_CONFIGURED"


def test_client_cannot_supply_tenant_authority(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Auth", actor_id="user-a"
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_external(
            tenant_id="tenant-other",
            project_id=PROJECT_ID,
            campaign_id=created.campaign.campaign_id,
            provider_id="google_ads",
            external_campaign_id="ext-auth",
            actor_id="user-a",
        )
    assert exc.value.code == "TENANT_MISMATCH"


def test_cross_tenant_binding_access_fails(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Auth", actor_id="user-a"
    )
    binding = graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-auth",
        actor_id="user-a",
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.get_external_binding(
            tenant_id="tenant-other",
            project_id=PROJECT_ID,
            binding_id=binding.binding_id,
        )
    assert exc.value.code == "TENANT_MISMATCH"


def test_cross_project_binding_access_fails(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Auth", actor_id="user-a"
    )
    binding = graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-auth",
        actor_id="user-a",
    )
    found = graph.store.get_external(
        tenant_id=TENANT_ID,
        project_id="wsp_projectb000000001",
        binding_id=binding.binding_id,
    )
    assert found is None
    with pytest.raises(IdentityGraphError) as exc:
        graph.get_external_binding(
            tenant_id=TENANT_ID,
            project_id="wsp_projectb000000001",
            binding_id=binding.binding_id,
        )
    assert exc.value.code == "UNKNOWN_BINDING"


def test_cross_project_resolution_fails(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Auth", actor_id="user-a"
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id="wsp_projectb000000001",
        signals=ObservedCampaignSignals(utm_id=created.campaign.campaign_id),
    )
    assert resolved.campaign_id is None
    assert resolved.source.value == "UNRESOLVED"

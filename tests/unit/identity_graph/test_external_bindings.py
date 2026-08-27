from __future__ import annotations

import pytest

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.enums import BindingStatus, ResolutionAuthority
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_campaign_external_binding_uses_canonical_campaign(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Canonical", actor_id="user-a"
    )
    binding = graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-canonical",
        actor_id="user-a",
    )
    assert binding.campaign_id == created.campaign.campaign_id
    assert binding.campaign_id.startswith("cmp_")
    assert binding.external_campaign_id != binding.campaign_id


def test_external_campaign_identity_namespaced_by_provider_account(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Ads A", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Ads B", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        provider_id="google_ads",
        external_account_id="acct_1",
        external_campaign_id="12345",
        actor_id="user-a",
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        provider_id="google_ads",
        external_account_id="acct_2",
        external_campaign_id="12345",
        actor_id="user-a",
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            provider_id="google_ads",
            external_account_id="acct_1",
            external_campaign_id="12345",
        ),
    )
    assert resolved.campaign_id == first.campaign.campaign_id


def test_same_external_id_different_provider_not_collision(graph) -> None:
    google = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Google", actor_id="user-a"
    )
    meta = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Meta", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=google.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="999",
        actor_id="user-a",
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=meta.campaign.campaign_id,
        provider_id="meta_ads",
        external_campaign_id="999",
        actor_id="user-a",
    )
    google_hit = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(provider_id="google_ads", external_campaign_id="999"),
    )
    meta_hit = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(provider_id="meta_ads", external_campaign_id="999"),
    )
    assert google_hit.campaign_id == google.campaign.campaign_id
    assert meta_hit.campaign_id == meta.campaign.campaign_id


def test_conflicting_active_binding_requires_review(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="One", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Two", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="shared",
        actor_id="user-a",
        status=BindingStatus.CONFIRMED,
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="shared",
        actor_id="user-a",
        status=BindingStatus.CONFIRMED,
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            provider_id="google_ads", external_campaign_id="shared"
        ),
    )
    assert resolved.status == ResolutionAuthority.REVIEW_REQUIRED
    assert "CONFLICTING_EXACT_BINDINGS" in resolved.issues


def test_external_name_change_does_not_change_canonical_campaign(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Canonical", actor_id="user-a"
    )
    binding = graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-1",
        external_campaign_name="Old Name",
        actor_id="user-a",
    )
    updated = graph.update_external_name(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        binding_id=binding.binding_id,
        external_campaign_name="New Name",
    )
    assert updated.external_campaign_name == "New Name"
    assert updated.campaign_id == created.campaign.campaign_id
    found = graph.store.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert found is not None
    assert found.campaign_id == created.campaign.campaign_id
    assert found.name == "Canonical"


def test_unknown_campaign_rejected(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_external(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id="cmp_doesnotexist00000000",
            provider_id="google_ads",
            external_campaign_id="ext-missing",
            actor_id="user-a",
        )
    assert exc.value.code == "UNKNOWN_CAMPAIGN"


def test_cross_project_campaign_binding_rejected(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Home", actor_id="user-a"
    )
    other_project = "wsp_projectb000000001"
    graph.create_market(
        tenant_id=TENANT_ID,
        project_id=other_project,
        name="Other market",
        actor_id="user-a",
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_external(
            tenant_id=TENANT_ID,
            project_id=other_project,
            campaign_id=created.campaign.campaign_id,
            provider_id="google_ads",
            external_campaign_id="ext-cross",
            actor_id="user-a",
        )
    assert exc.value.code == "UNKNOWN_CAMPAIGN"


def test_historical_nonoverlapping_binding_preserved(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Past", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Current", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="shared-hist",
        actor_id="user-a",
        effective_start="2025-01-01",
        effective_end="2025-12-31",
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="shared-hist",
        actor_id="user-a",
        effective_start="2026-01-01",
        effective_end="2026-12-31",
    )
    past = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            provider_id="google_ads",
            external_campaign_id="shared-hist",
            observed_at="2025-06-01",
        ),
    )
    current = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            provider_id="google_ads",
            external_campaign_id="shared-hist",
            observed_at="2026-06-01",
        ),
    )
    assert past.campaign_id == first.campaign.campaign_id
    assert current.campaign_id == second.campaign.campaign_id
    assert past.status == ResolutionAuthority.RESOLVED
    assert current.status == ResolutionAuthority.RESOLVED


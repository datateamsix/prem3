from __future__ import annotations

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.enums import (
    BindingStatus,
    CampaignIdentitySource,
    ResolutionAuthority,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_exact_prem3_utm_id_resolves(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Utm", actor_id="user-a"
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(utm_id=created.campaign.campaign_id),
    )
    assert resolved.campaign_id == created.campaign.campaign_id
    assert resolved.source == CampaignIdentitySource.PREM3_UTM_ID
    assert resolved.status == ResolutionAuthority.RESOLVED
    assert resolved.matched_binding_ids


def test_exact_external_binding_resolves(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Ads", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-exact",
        actor_id="user-a",
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            provider_id="google_ads", external_campaign_id="ext-exact"
        ),
    )
    assert resolved.campaign_id == created.campaign.campaign_id
    assert resolved.source == CampaignIdentitySource.EXTERNAL_CAMPAIGN_BINDING


def test_approved_custom_identifier_resolves(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Promo", actor_id="user-a"
    )
    graph.bind_custom_identifier(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        parameter_name="promo_code",
        parameter_value="SPRING",
        actor_id="user-a",
        status=BindingStatus.APPROVED,
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            custom_parameter_name="promo_code", custom_parameter_value="SPRING"
        ),
    )
    assert resolved.campaign_id == created.campaign.campaign_id
    assert resolved.source == CampaignIdentitySource.CUSTOM_IDENTIFIER


def test_user_confirmed_mapping_resolves(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Manual", actor_id="user-a"
    )
    graph.bind_user_confirmed_mapping(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        actor_id="user-a",
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            user_confirmed_campaign_id=created.campaign.campaign_id
        ),
    )
    assert resolved.campaign_id == created.campaign.campaign_id
    assert resolved.source == CampaignIdentitySource.USER_CONFIRMED_MAPPING


def test_unmapped_identifier_unresolved(graph) -> None:
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            utm_id="cmp_doesnotexist00000000",
            provider_id="google_ads",
            external_campaign_id="missing",
        ),
    )
    assert resolved.source == CampaignIdentitySource.UNRESOLVED
    assert resolved.status == ResolutionAuthority.UNRESOLVED
    assert resolved.campaign_id is None


def test_fuzzy_campaign_name_never_deterministically_resolves(graph) -> None:
    graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Lookalike", actor_id="user-a"
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            fuzzy_name="Lookalike", utm_campaign="Lookalike"
        ),
    )
    assert resolved.source == CampaignIdentitySource.UNRESOLVED
    assert resolved.campaign_id is None


def test_conflicting_exact_methods_review_required(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Utm", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Ads", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="ext-conflict",
        actor_id="user-a",
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            utm_id=first.campaign.campaign_id,
            provider_id="google_ads",
            external_campaign_id="ext-conflict",
        ),
    )
    assert resolved.status == ResolutionAuthority.REVIEW_REQUIRED
    assert resolved.campaign_id is None
    assert "BINDING_CONFLICT" in resolved.issues
    assert resolved.conflicting_binding_ids

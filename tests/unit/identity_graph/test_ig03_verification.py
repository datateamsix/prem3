from __future__ import annotations

from app.identity_graph.enums import (
    ObservationSourceKind,
    ObservedIdentifierKind,
    VerificationStatus,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_verified_requires_observation(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Need obs", actor_id="user-a"
    )
    receipt = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert receipt.status == VerificationStatus.NOT_OBSERVED
    assert receipt.status != VerificationStatus.VERIFIED


def test_verified_requires_unique_resolution(graph) -> None:
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
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="shared",
        actor_id="user-a",
    )
    observation = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ads/campaigns",
        source_kind=ObservationSourceKind.GOOGLE_ADS,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.EXTERNAL_CAMPAIGN_ID,
        parameter_value="shared",
        external_provider_id="google_ads",
        external_campaign_id="shared",
        candidate_campaign_id=first.campaign.campaign_id,
    )
    receipt = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        observation_id=observation.observation_id,
    )
    assert receipt.status != VerificationStatus.VERIFIED
    assert receipt.status == VerificationStatus.REVIEW_REQUIRED


def test_expected_identifier_mismatch_review_required(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Expected", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Other", actor_id="user-a"
    )
    observation = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=second.campaign.campaign_id,
        candidate_campaign_id=second.campaign.campaign_id,
    )
    receipt = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        observation_id=observation.observation_id,
    )
    assert receipt.status == VerificationStatus.REVIEW_REQUIRED
    assert "EXPECTED_IDENTIFIER_MISMATCH" in receipt.issues


def test_prior_verified_can_become_review_required(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="First", actor_id="user-a"
    )
    observation = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=first.campaign.campaign_id,
        candidate_campaign_id=first.campaign.campaign_id,
    )
    verified = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        observation_id=observation.observation_id,
    )
    assert verified.status == VerificationStatus.VERIFIED
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Second", actor_id="user-a"
    )
    graph.bind_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        provider_id="google_ads",
        external_campaign_id="later-conflict",
        actor_id="user-a",
    )
    later = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-05-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=first.campaign.campaign_id,
        external_provider_id="google_ads",
        external_campaign_id="later-conflict",
        candidate_campaign_id=first.campaign.campaign_id,
    )
    reviewed = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        observation_id=later.observation_id,
    )
    assert reviewed.status == VerificationStatus.REVIEW_REQUIRED


def test_not_observed_never_verified(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Silent", actor_id="user-a"
    )
    receipt = graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert receipt.status == VerificationStatus.NOT_OBSERVED
    instructions = graph.tracking_instructions(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert instructions.implementation_status.value != "VERIFIED"

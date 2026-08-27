from __future__ import annotations

from app.identity_graph.enums import ObservationSourceKind, ObservedIdentifierKind
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_coverage_denominator_is_explicit(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Covered", actor_id="user-a"
    )
    graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=created.campaign.campaign_id,
        candidate_campaign_id=created.campaign.campaign_id,
    )
    graph.resolve_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=None,
        observation_id=graph.store.list_observations(
            tenant_id=TENANT_ID, project_id=PROJECT_ID
        )[0].observation_id,
    )
    coverage = graph.tracking_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert coverage.observed_identifier_count >= 1
    assert coverage.campaigns_total >= 1
    dumped = coverage.model_dump()
    assert "tracking_score" not in dumped
    assert coverage.resolved_identifier_count <= coverage.observed_identifier_count


def test_unresolved_observations_counted(graph) -> None:
    graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Covered", actor_id="user-a"
    )
    observation = graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value="cmp_doesnotexist00000000",
    )
    graph.resolve_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        observation_id=observation.observation_id,
    )
    coverage = graph.tracking_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert coverage.unresolved_identifier_count >= 1


def test_review_required_observations_counted(graph) -> None:
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
        source_ref="bq://ads",
        source_kind=ObservationSourceKind.GOOGLE_ADS,
        observed_at="2026-04-01",
        identifier_kind=ObservedIdentifierKind.EXTERNAL_CAMPAIGN_ID,
        parameter_value="shared",
        external_provider_id="google_ads",
        external_campaign_id="shared",
    )
    graph.resolve_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        observation_id=observation.observation_id,
    )
    coverage = graph.tracking_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert coverage.review_required_count >= 1


def test_campaign_without_observation_not_verified(graph) -> None:
    graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Quiet", actor_id="user-a"
    )
    coverage = graph.tracking_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert coverage.campaigns_verified == 0
    assert coverage.observed_identifier_count == 0


def test_coverage_has_no_performance_metrics(graph) -> None:
    graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Quiet", actor_id="user-a"
    )
    coverage = graph.tracking_coverage(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    dumped = coverage.model_dump()
    for key in ("impressions", "reach", "match_rate", "tracking_score", "roas"):
        assert key not in dumped

from __future__ import annotations

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.enums import ObservationSourceKind, ObservedIdentifierKind
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def _snapshot(campaign):
    return {
        "name": campaign.name,
        "market_ids": campaign.market_ids,
        "channel_ids": campaign.channel_ids,
        "planned_start_date": campaign.planned_start_date,
        "planned_end_date": campaign.planned_end_date,
        "audience_ids": campaign.audience_ids,
        "persona_ids": campaign.persona_ids,
    }


def test_tracking_observation_does_not_mutate_campaign_markets(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Immutable",
        actor_id="user-a",
        planned_start_date="2026-04-01",
        planned_end_date="2026-06-30",
    )
    before = _snapshot(created.campaign)
    graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-15",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=created.campaign.campaign_id,
    )
    loaded = graph.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert loaded.market_ids == before["market_ids"]


def test_tracking_observation_does_not_mutate_campaign_channels(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Immutable", actor_id="user-a"
    )
    before = created.campaign.channel_ids
    graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-15",
        identifier_kind=ObservedIdentifierKind.UTM_ID,
        parameter_value=created.campaign.campaign_id,
    )
    loaded = graph.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert loaded.channel_ids == before


def test_tracking_observation_does_not_mutate_flight_dates(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Immutable",
        actor_id="user-a",
        planned_start_date="2026-04-01",
        planned_end_date="2026-06-30",
    )
    graph.resolve_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(utm_id=created.campaign.campaign_id),
    )
    loaded = graph.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert loaded.planned_start_date == "2026-04-01"
    assert loaded.planned_end_date == "2026-06-30"


def test_tracking_observation_does_not_mutate_audience_targets(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Immutable", actor_id="user-a"
    )
    before = created.campaign.audience_ids
    graph.verify_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    loaded = graph.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert loaded.audience_ids == before


def test_tracking_observation_does_not_rename_campaign(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Canonical Name", actor_id="user-a"
    )
    graph.observe_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="bq://ga4/export",
        source_kind=ObservationSourceKind.GA4_BIGQUERY,
        observed_at="2026-04-15",
        identifier_kind=ObservedIdentifierKind.UTM_CAMPAIGN,
        parameter_value="Different Observed Name",
        candidate_campaign_id=created.campaign.campaign_id,
    )
    loaded = graph.get_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert loaded.name == "Canonical Name"

from __future__ import annotations

import pytest

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.enums import MarketKind
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def test_campaign_market_refs_use_canonical_market_ids(graph) -> None:
    market = make_canonical_market(graph)
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="US Search",
        actor_id="user-a",
        market_ids=(market.market_id,),
        channel_ids=("search_paid",),
    )
    assert created.campaign.market_ids == (market.market_id,)


def test_campaign_channel_refs_use_channel_registry_ids(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Paid Search",
        actor_id="user-a",
        channel_ids=("search_paid",),
    )
    assert created.campaign.channel_ids == ("search_paid",)


def test_unknown_channel_fails_closed(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Mystery",
            actor_id="user-a",
            channel_ids=("not_a_registry_channel",),
        )
    assert exc.value.code == "UNKNOWN_CHANNEL"


def test_campaign_requires_channel_registry_ids(graph) -> None:
    market = make_canonical_market(graph)
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="No channel",
            actor_id="user-a",
            market_ids=(market.market_id,),
            channel_ids=(),
        )
    assert exc.value.code == "CHANNELS_REQUIRED"


def test_display_names_not_used_as_join_authority(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Brand", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Brand", actor_id="user-a"
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(fuzzy_name="Brand", utm_campaign="Brand"),
    )
    assert first.campaign.campaign_id != second.campaign.campaign_id
    assert resolved.campaign_id is None
    assert resolved.source.value == "UNRESOLVED"


def test_campaign_requires_known_canonical_market(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Missing market",
            actor_id="user-a",
            market_ids=(),
            channel_ids=("search_paid",),
        )
    assert exc.value.code == "MARKETS_REQUIRED"
    with pytest.raises(IdentityGraphError) as missing:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Unknown market",
            actor_id="user-a",
            market_ids=("mkt_bbbbbbbbbbbbbbbbbbbb",),
            channel_ids=("search_paid",),
        )
    assert missing.value.code == "UNKNOWN_MARKET"


def test_campaign_display_string_market_rejected(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_campaign(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Display",
            actor_id="user-a",
            market_ids=("United States",),
            channel_ids=("search_paid",),
        )
    assert exc.value.code == "UNKNOWN_MARKET"


def test_custom_region_market_is_valid_campaign_scope(graph) -> None:
    region = make_canonical_market(
        graph,
        name="DACH",
        market_kind=MarketKind.CUSTOM,
        region_codes=("DE", "AT", "CH"),
    )
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="DACH Brand",
        actor_id="user-a",
        market_ids=(region.market_id,),
        channel_ids=("search_paid",),
    )
    assert created.campaign.market_ids == (region.market_id,)

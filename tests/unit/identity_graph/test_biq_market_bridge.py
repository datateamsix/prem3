from __future__ import annotations

from app.business_iq.service import BusinessIqService
from app.business_iq.store import InMemoryBusinessIqStore
from app.identity_graph.enums import MarketKind, MarketMappingMethod, ResolutionAuthority
from app.identity_graph.service import CampaignIdentityService
from app.identity_graph.store import InMemoryIdentityGraphStore
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def _graph_with_markets(tenant_ctx, markets: list[dict]) -> CampaignIdentityService:
    del tenant_ctx
    store = InMemoryBusinessIqStore()
    payload = ready_payload()
    payload["markets"] = markets
    BusinessIqService(store=store).create_profile(
        tenant_id=TENANT_ID,
        workspace_id=PROJECT_ID,
        actor_id="user-a",
        payload=payload,
    )
    return CampaignIdentityService(
        store=InMemoryIdentityGraphStore(),
        business_iq_store=store,
    )


def test_existing_biq_market_binds_to_canonical_market(graph) -> None:
    profile = graph.business_iq_store.get_profile(
        tenant_id=TENANT_ID, workspace_id=PROJECT_ID
    )
    assert profile is not None
    bindings = graph.bind_business_iq_markets(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, actor_id="user-a"
    )
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.business_market_ref == "mkt_us"
    assert binding.business_profile_snapshot_id == profile.current_snapshot_id
    assert binding.market_id.startswith("mkt_")
    assert binding.market_id != "mkt_us"
    assert binding.mapping_method == MarketMappingMethod.SERVER_CREATED_FROM_BUSINESS_IQ
    canonical = graph.store.get_market(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, market_id=binding.market_id
    )
    assert canonical is not None
    assert canonical.name == "United States"


def test_historical_business_profile_not_mutated(graph) -> None:
    before = graph.business_iq_store.get_profile(
        tenant_id=TENANT_ID, workspace_id=PROJECT_ID
    )
    assert before is not None
    snapshot_before = before.current_snapshot_id
    markets_before = tuple(
        (item.market_id, item.name, item.geo_level) for item in before.markets
    )
    graph.bind_business_iq_markets(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, actor_id="user-a"
    )
    after = graph.business_iq_store.get_profile(
        tenant_id=TENANT_ID, workspace_id=PROJECT_ID
    )
    assert after is not None
    assert after.current_snapshot_id == snapshot_before
    assert tuple((item.market_id, item.name, item.geo_level) for item in after.markets) == (
        markets_before
    )
    assert after.markets[0].market_id == "mkt_us"


def test_binding_is_idempotent(graph) -> None:
    first = graph.bind_business_iq_markets(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, actor_id="user-a"
    )
    second = graph.bind_business_iq_markets(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, actor_id="user-a"
    )
    assert [item.binding_id for item in first] == [item.binding_id for item in second]
    assert [item.market_id for item in first] == [item.market_id for item in second]
    markets = graph.list_markets(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert len(markets) == 1


def test_ambiguous_legacy_market_requires_review(graph) -> None:
    make_canonical_market(graph, name="North America", market_kind=MarketKind.REGION)
    make_canonical_market(graph, name="North America", market_kind=MarketKind.CUSTOM)
    authority = graph.review_legacy_market_name_merge(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        display_name="North America",
    )
    assert authority == ResolutionAuthority.REVIEW_REQUIRED


def test_display_name_only_does_not_silently_merge_markets(tenant_ctx) -> None:
    graph = _graph_with_markets(
        tenant_ctx,
        [
            {
                "market_id": "legacy_us_east",
                "name": "North America",
                "geo_level": "REGION",
            },
            {
                "market_id": "legacy_us_west",
                "name": "North America",
                "geo_level": "REGION",
            },
        ],
    )
    bindings = graph.bind_business_iq_markets(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, actor_id="user-a"
    )
    assert len(bindings) == 2
    assert bindings[0].market_id != bindings[1].market_id
    assert {item.business_market_ref for item in bindings} == {
        "legacy_us_east",
        "legacy_us_west",
    }
    authority = graph.review_legacy_market_name_merge(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        display_name="North America",
    )
    assert authority == ResolutionAuthority.REVIEW_REQUIRED

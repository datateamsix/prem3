from __future__ import annotations

import re

from app.identity_graph.enums import MarketKind
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market

_URL_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")
_OPAQUE_MARKET = re.compile(r"^mkt_[0-9a-f]{20}$")


def test_market_id_is_server_generated(graph) -> None:
    market = make_canonical_market(graph, name="Canada")
    assert market.market_id.startswith("mkt_")
    assert market.market_id != "Canada"
    assert _OPAQUE_MARKET.fullmatch(market.market_id)
    assert _URL_SAFE.fullmatch(market.market_id)


def test_market_id_not_derived_from_name(graph) -> None:
    market = make_canonical_market(
        graph,
        name="United States",
        country_codes=("US",),
    )
    lowered = market.market_id.lower()
    assert "united" not in lowered
    assert "states" not in lowered
    assert market.market_id != "mkt_US"
    assert market.market_id != "mkt_us"
    assert market.market_id != "mkt_united_states"


def test_same_name_can_exist_when_business_semantics_differ(graph) -> None:
    east = make_canonical_market(
        graph,
        name="North America",
        market_kind=MarketKind.SUBNATIONAL,
        region_codes=("US-EAST",),
    )
    enterprise = make_canonical_market(
        graph,
        name="North America",
        market_kind=MarketKind.CUSTOM,
        description="Enterprise North America",
    )
    assert east.name == enterprise.name
    assert east.market_id != enterprise.market_id
    assert east.market_kind != enterprise.market_kind


def test_custom_region_market_supported(graph) -> None:
    dach = make_canonical_market(
        graph,
        name="DACH",
        market_kind=MarketKind.MULTI_COUNTRY_REGION,
        country_codes=("DE", "AT", "CH"),
    )
    global_market = make_canonical_market(
        graph,
        name="Global",
        market_kind=MarketKind.GLOBAL,
    )
    custom = make_canonical_market(
        graph,
        name="Enterprise North America",
        market_kind=MarketKind.CUSTOM,
    )
    assert dach.market_kind == MarketKind.MULTI_COUNTRY_REGION
    assert global_market.market_kind == MarketKind.GLOBAL
    assert custom.market_kind == MarketKind.CUSTOM
    assert dach.country_codes == ("DE", "AT", "CH")


def test_market_id_is_project_scoped(graph) -> None:
    other_project = "wsp_projectb000000001"
    home = make_canonical_market(graph, name="United Kingdom")
    away = make_canonical_market(
        graph,
        name="United Kingdom",
        project_id=other_project,
    )
    home_ids = {
        item.market_id
        for item in graph.list_markets(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    }
    away_ids = {
        item.market_id
        for item in graph.list_markets(tenant_id=TENANT_ID, project_id=other_project)
    }
    assert home.market_id in home_ids
    assert home.market_id not in away_ids
    assert away.market_id in away_ids
    assert away.market_id not in home_ids
    assert graph.store.get_market(
        tenant_id=TENANT_ID, project_id=other_project, market_id=home.market_id
    ) is None


def test_market_id_is_stable(graph) -> None:
    market = make_canonical_market(graph, name="Canada")
    listed = graph.list_markets(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    fetched = graph.store.get_market(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, market_id=market.market_id
    )
    assert fetched is not None
    assert market.market_id in {item.market_id for item in listed}
    assert fetched.market_id == market.market_id
    assert fetched.fingerprint == market.fingerprint

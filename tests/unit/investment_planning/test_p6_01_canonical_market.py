"""P6 consumes Identity Graph CanonicalMarket. Planning does not mint markets."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.identity_graph.contracts import BusinessMarketBinding, CanonicalMarket
from app.identity_graph.enums import BindingStatus, MarketKind, MarketMappingMethod, MarketStatus
from app.identity_graph.ids import new_market_id
from app.identity_graph.store import InMemoryIdentityGraphStore
from app.investment_planning.errors import UnresolvedMarketIdentityError
from app.investment_planning.identity import require_canonical_market_id
from app.investment_planning.markets import (
    IdentityGraphMarketDirectory,
    resolve_planning_market_token,
)

TENANT = "ten_bbbbbbbbbbbbbbbbbbbb"
PROJECT = "wsp_cccccccccccccccccccc"
SNAPSHOT = "bps_dddddddddddddddddddd"


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def _directory_with_market(*, name: str = "DACH", kind: MarketKind = MarketKind.MULTI_COUNTRY_REGION):
    store = InMemoryIdentityGraphStore()
    market = CanonicalMarket(
        market_id=new_market_id(),
        tenant_id=TENANT,
        project_id=PROJECT,
        name=name,
        market_kind=kind,
        status=MarketStatus.ACTIVE,
        country_codes=("DE", "AT", "CH") if kind is MarketKind.MULTI_COUNTRY_REGION else (),
        created_at=_now(),
        updated_at=_now(),
        created_by="user-a",
    )
    store.put_market(market)
    return IdentityGraphMarketDirectory(store), market, store


def test_investment_plan_uses_canonical_market_id() -> None:
    directory, market, _store = _directory_with_market()
    known = directory.known_market_ids(tenant_id=TENANT, project_id=PROJECT)
    assert require_canonical_market_id(market.market_id, known_market_ids=known) == market.market_id
    resolved = resolve_planning_market_token(
        market.market_id,
        directory=directory,
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=SNAPSHOT,
    )
    assert resolved == market.market_id
    assert resolved.startswith("mkt_")
    assert resolved != name_as_id(market.name)


def name_as_id(name: str) -> str:
    return "mkt_" + name.lower().replace(" ", "_")


def test_market_display_label_is_not_join_authority() -> None:
    directory, market, _store = _directory_with_market(name="United States", kind=MarketKind.COUNTRY)
    with pytest.raises(UnresolvedMarketIdentityError):
        resolve_planning_market_token(
            "United States",
            directory=directory,
            tenant_id=TENANT,
            project_id=PROJECT,
            snapshot_id=SNAPSHOT,
        )
    with pytest.raises(UnresolvedMarketIdentityError):
        resolve_planning_market_token(
            "US",
            directory=directory,
            tenant_id=TENANT,
            project_id=PROJECT,
            snapshot_id=SNAPSHOT,
        )
    assert market.name == "United States"


def test_unknown_market_id_fails_closed() -> None:
    directory, _market, _store = _directory_with_market()
    unknown = new_market_id()
    with pytest.raises(UnresolvedMarketIdentityError, match="canonical Identity Graph"):
        resolve_planning_market_token(
            unknown,
            directory=directory,
            tenant_id=TENANT,
            project_id=PROJECT,
            snapshot_id=SNAPSHOT,
        )


def test_custom_region_market_is_valid_for_planning() -> None:
    directory, market, _store = _directory_with_market()
    known = directory.known_market_ids(tenant_id=TENANT, project_id=PROJECT)
    assert market.market_kind is MarketKind.MULTI_COUNTRY_REGION
    assert require_canonical_market_id(market.market_id, known_market_ids=known) == market.market_id


def test_p6_does_not_mint_market_identity() -> None:
    directory, _market, store = _directory_with_market()
    before = store.issued_market_ids()
    with pytest.raises(UnresolvedMarketIdentityError):
        resolve_planning_market_token(
            "North America",
            directory=directory,
            tenant_id=TENANT,
            project_id=PROJECT,
            snapshot_id=SNAPSHOT,
        )
    assert store.issued_market_ids() == before


def test_historical_biq_market_string_not_used_as_portfolio_identity() -> None:
    directory, market, store = _directory_with_market(name="United States", kind=MarketKind.COUNTRY)
    store.put_market_binding(
        BusinessMarketBinding(
            binding_id="igb_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT,
            project_id=PROJECT,
            business_profile_snapshot_id=SNAPSHOT,
            business_market_ref="mkt_us",
            market_id=market.market_id,
            mapping_method=MarketMappingMethod.SERVER_CREATED_FROM_BUSINESS_IQ,
            status=BindingStatus.CONFIRMED,
            created_at=_now(),
        )
    )
    resolved = resolve_planning_market_token(
        "mkt_us",
        directory=directory,
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=SNAPSHOT,
    )
    assert resolved == market.market_id
    assert resolved != "mkt_us"
    with pytest.raises(UnresolvedMarketIdentityError):
        require_canonical_market_id(
            "mkt_us",
            known_market_ids=directory.known_market_ids(tenant_id=TENANT, project_id=PROJECT),
        )

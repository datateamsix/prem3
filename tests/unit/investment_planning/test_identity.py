"""Canonical market_id and channel_id fail closed. No P6 market registry."""

from __future__ import annotations

import pytest

from app.investment_planning.errors import (
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.identity import (
    CANONICAL_MARKET_CONTRACT_INTEGRATED,
    MARKET_IDENTITY_OWNER,
    MARKET_IDENTITY_PENDING_MISSIONS,
    assert_investment_plan_ready_permitted,
    require_canonical_channel_id,
    require_canonical_market_id,
)


def test_market_id_is_required_and_display_strings_are_non_authoritative() -> None:
    known = frozenset({"mkt_aaaaaaaaaaaaaaaaaaaa"})
    assert require_canonical_market_id("mkt_aaaaaaaaaaaaaaaaaaaa", known_market_ids=known) == (
        "mkt_aaaaaaaaaaaaaaaaaaaa"
    )
    with pytest.raises(UnresolvedMarketIdentityError, match="required"):
        require_canonical_market_id(None, known_market_ids=known)
    with pytest.raises(UnresolvedMarketIdentityError, match="required"):
        require_canonical_market_id("  ", known_market_ids=known)
    with pytest.raises(UnresolvedMarketIdentityError, match="canonical identifier"):
        require_canonical_market_id("United States", known_market_ids=known)
    with pytest.raises(UnresolvedMarketIdentityError, match="canonical identifier"):
        require_canonical_market_id("United States / Canada", known_market_ids=known)
    assert MARKET_IDENTITY_OWNER == "FOUNDATION_MARKETING_IDENTITY_GRAPH"
    assert MARKET_IDENTITY_PENDING_MISSIONS == ("IG-00", "IG-01")
    assert CANONICAL_MARKET_CONTRACT_INTEGRATED is True


def test_market_id_is_not_derived_from_iso_or_fuzzy_names() -> None:
    known = frozenset({"mkt_aaaaaaaaaaaaaaaaaaaa"})
    for alias in ("US", "USA", "us", "CA", "CAN", "GB", "GBR"):
        with pytest.raises(UnresolvedMarketIdentityError):
            require_canonical_market_id(alias, known_market_ids=known)
    with pytest.raises(UnresolvedMarketIdentityError, match="canonical Identity Graph"):
        require_canonical_market_id("mkt_uk", known_market_ids=known)


def test_investment_plan_ready_requires_resolved_market_refs() -> None:
    assert_investment_plan_ready_permitted(market_bearing=False)
    assert_investment_plan_ready_permitted(market_bearing=True, markets_resolved=True)
    with pytest.raises(UnresolvedMarketIdentityError, match="canonical Identity Graph"):
        assert_investment_plan_ready_permitted(market_bearing=True, markets_resolved=False)


def test_channel_id_must_be_registry_id_not_profile_local() -> None:
    assert require_canonical_channel_id("search_paid") == "search_paid"
    with pytest.raises(UnresolvedChannelIdentityError):
        require_canonical_channel_id("bch_localprofilechannel")
    with pytest.raises(UnresolvedChannelIdentityError):
        require_canonical_channel_id("planning_channel_id")

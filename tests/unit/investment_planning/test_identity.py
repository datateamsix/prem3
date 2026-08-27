"""Canonical market_id and channel_id fail closed. No P6 market registry."""

from __future__ import annotations

import pytest

from app.investment_planning.errors import (
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.identity import (
    MARKET_IDENTITY_OWNER,
    MARKET_IDENTITY_PENDING_MISSIONS,
    require_canonical_channel_id,
    require_canonical_market_id,
)


def test_market_id_fails_closed_on_display_strings() -> None:
    known = frozenset({"mkt_us"})
    assert require_canonical_market_id("mkt_us", known_market_ids=known) == "mkt_us"
    with pytest.raises(UnresolvedMarketIdentityError, match="display string"):
        require_canonical_market_id("United States", known_market_ids=known)
    with pytest.raises(UnresolvedMarketIdentityError, match="Unknown market_id"):
        require_canonical_market_id("mkt_uk", known_market_ids=known)
    assert MARKET_IDENTITY_OWNER == "FOUNDATION_MARKETING_IDENTITY_GRAPH"
    assert "IG-00" in MARKET_IDENTITY_PENDING_MISSIONS


def test_channel_id_must_be_registry_id_not_profile_local() -> None:
    assert require_canonical_channel_id("search_paid") == "search_paid"
    with pytest.raises(UnresolvedChannelIdentityError):
        require_canonical_channel_id("bch_localprofilechannel")
    with pytest.raises(UnresolvedChannelIdentityError):
        require_canonical_channel_id("planning_channel_id")

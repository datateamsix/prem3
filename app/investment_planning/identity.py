"""Canonical Planning market and channel identity. Fail closed. No P6 registry."""

from __future__ import annotations

from app.core.errors import InvalidResourceIdentifierError
from app.core.identifiers import validate_resource_identifier
from app.domain.channels.registry import cached_channel_registry
from app.domain.channels.validation import ChannelValidationError, assert_channel_id_in_registry
from app.identity_graph.ids import assert_market_id_shape
from app.investment_planning.errors import (
    CanonicalMarketContractPendingError,
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)

# Planning never invents a market registry. Identity Graph owns durable market identity.
MARKET_IDENTITY_OWNER = "FOUNDATION_MARKETING_IDENTITY_GRAPH"
MARKET_IDENTITY_PENDING_MISSIONS = ("IG-00", "IG-01")
CANONICAL_MARKET_CONTRACT_INTEGRATED = True


def require_canonical_market_id(
    market_id: str | None,
    *,
    known_market_ids: frozenset[str] | set[str],
) -> str:
    """Join key is Identity Graph CanonicalMarket.market_id.

    Display names, ISO codes, and invented IDs fail closed. Planning does not
    map names or ISO 3166 tokens onto a market_id.
    """
    if market_id is None or not str(market_id).strip():
        raise UnresolvedMarketIdentityError(
            "Planning market_id is required.",
            code="UNRESOLVED_MARKET_IDENTITY",
        )
    try:
        validated = assert_market_id_shape(market_id)
        validate_resource_identifier(validated, field="market_id")
    except (InvalidResourceIdentifierError, ValueError) as exc:
        raise UnresolvedMarketIdentityError(
            "Planning market_id must be a canonical identifier, not a display string.",
            code="UNRESOLVED_MARKET_IDENTITY",
        ) from exc
    if validated not in known_market_ids:
        raise UnresolvedMarketIdentityError(
            f"Unknown market_id {validated!r} is not a canonical Identity Graph market.",
            code="UNRESOLVED_MARKET_IDENTITY",
        )
    return validated


def assert_investment_plan_ready_permitted(
    *,
    market_bearing: bool,
    markets_resolved: bool = True,
) -> None:
    """INVESTMENT_PLAN_READY requires the IG-01 contract and resolved market_id refs."""
    if not CANONICAL_MARKET_CONTRACT_INTEGRATED and market_bearing:
        raise CanonicalMarketContractPendingError(
            "INVESTMENT_PLAN_READY cannot be declared for a market-bearing plan until "
            "the IG-01 canonical-market contract is integrated.",
            code="CANONICAL_MARKET_CONTRACT_PENDING",
        )
    if market_bearing and not markets_resolved:
        raise UnresolvedMarketIdentityError(
            "INVESTMENT_PLAN_READY requires every market reference to resolve to a "
            "canonical Identity Graph market_id.",
            code="UNRESOLVED_MARKET_IDENTITY",
        )


def require_canonical_channel_id(channel_id: str) -> str:
    """Planning joins on Channel Registry channel_id, never planning_channel_id."""
    registry = cached_channel_registry()
    try:
        assert_channel_id_in_registry(channel_id, registry)
    except ChannelValidationError as exc:
        raise UnresolvedChannelIdentityError(
            f"Unknown channel_id {channel_id!r} is not in the Channel Registry.",
            code="UNRESOLVED_CHANNEL_IDENTITY",
        ) from exc
    return channel_id

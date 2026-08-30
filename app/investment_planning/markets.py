"""External market identity directory. P6 does not own or mint market IDs."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.identity_graph.enums import BindingStatus, MarketStatus
from app.identity_graph.ids import assert_market_id_shape
from app.identity_graph.store import IdentityGraphStore, InMemoryIdentityGraphStore
from app.investment_planning.errors import UnresolvedMarketIdentityError


@runtime_checkable
class MarketIdentityDirectory(Protocol):
    def known_market_ids(self, *, tenant_id: str, project_id: str) -> frozenset[str]: ...

    def canonical_id_for_business_ref(
        self,
        business_market_ref: str,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
    ) -> str | None: ...


class PendingIdentityGraphMarketDirectory:
    """Kept for tests of the pre-integration seam. Production uses IdentityGraphMarketDirectory."""

    def known_market_ids(self, *, tenant_id: str, project_id: str) -> frozenset[str]:
        del tenant_id, project_id
        return frozenset()

    def canonical_id_for_business_ref(
        self,
        business_market_ref: str,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
    ) -> str | None:
        del business_market_ref, tenant_id, project_id, snapshot_id
        return None


class IdentityGraphMarketDirectory:
    """Read-only Planning consumer of IG CanonicalMarket + BusinessMarketBinding."""

    def __init__(self, store: IdentityGraphStore) -> None:
        self._store = store

    def known_market_ids(self, *, tenant_id: str, project_id: str) -> frozenset[str]:
        return frozenset(
            market.market_id
            for market in self._store.list_canonical_markets(
                tenant_id=tenant_id, project_id=project_id
            )
            if market.status is MarketStatus.ACTIVE
        )

    def canonical_id_for_business_ref(
        self,
        business_market_ref: str,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
    ) -> str | None:
        binding = self._store.get_market_binding(
            tenant_id=tenant_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            business_market_ref=business_market_ref,
        )
        if binding is None or binding.status is BindingStatus.REVIEW_REQUIRED:
            return None
        if binding.status not in {BindingStatus.CONFIRMED, BindingStatus.ACTIVE, BindingStatus.APPROVED}:
            return None
        return binding.market_id


def resolve_planning_market_token(
    token: str | None,
    *,
    directory: MarketIdentityDirectory,
    tenant_id: str,
    project_id: str,
    snapshot_id: str,
) -> str:
    """Resolve a budget cell to CanonicalMarket.market_id. No name/ISO minting."""
    if token is None or not str(token).strip():
        raise UnresolvedMarketIdentityError(
            "Planning market_id is required.",
            code="UNRESOLVED_MARKET_IDENTITY",
        )
    raw = str(token).strip()
    known = directory.known_market_ids(tenant_id=tenant_id, project_id=project_id)
    try:
        shaped = assert_market_id_shape(raw)
    except ValueError:
        shaped = None
    if shaped is not None and shaped in known:
        return shaped
    bound = directory.canonical_id_for_business_ref(
        raw,
        tenant_id=tenant_id,
        project_id=project_id,
        snapshot_id=snapshot_id,
    )
    if bound is not None and bound in known:
        return bound
    raise UnresolvedMarketIdentityError(
        f"Unknown market_id {raw!r} is not a canonical Identity Graph market.",
        code="UNRESOLVED_MARKET_IDENTITY",
    )


def default_market_directory() -> IdentityGraphMarketDirectory:
    return IdentityGraphMarketDirectory(InMemoryIdentityGraphStore())

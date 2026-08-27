"""Provider discovery seam. Live Ads/Meta clients are out of IG-03 authority."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.identity_graph.errors import IdentityGraphError


@runtime_checkable
class ProviderDiscovery(Protocol):
    def discover_campaigns(self, provider_account_ref: str) -> list[dict[str, str]]: ...

    def discover_audiences(self, provider_account_ref: str) -> list[dict[str, str]]: ...


class UnconfiguredProviderDiscovery:
    """V1 workflow is manual bind/confirm. Discovery is interface-only."""

    def discover_campaigns(self, provider_account_ref: str) -> list[dict[str, str]]:
        del provider_account_ref
        raise IdentityGraphError(
            "Provider campaign discovery is not configured.",
            code="DISCOVERY_NOT_CONFIGURED",
        )

    def discover_audiences(self, provider_account_ref: str) -> list[dict[str, str]]:
        del provider_account_ref
        raise IdentityGraphError(
            "Provider audience discovery is not configured.",
            code="DISCOVERY_NOT_CONFIGURED",
        )

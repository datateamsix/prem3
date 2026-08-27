"""Identity Graph persistence port. In-memory for IG-00; Firestore paths reserved."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.identity_graph.contracts import (
    BusinessMarketBinding,
    CampaignExternalBinding,
    CampaignTrackingBinding,
    CanonicalCampaign,
    CanonicalMarket,
    GA4PropertySourceBinding,
    GA4SourceTopology,
    GA4TopologyReadinessReceipt,
    MarketResolutionPolicy,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.relationships import MarketingIdentityEdge

FIRESTORE_GRAPH_COLLECTION = "identity_graph"


def firestore_graph_path(*, tenant_id: str, workspace_id: str) -> str:
    """Reserved control-plane path. IG-00 does not write Firestore documents."""
    return f"tenants/{tenant_id}/workspaces/{workspace_id}/{FIRESTORE_GRAPH_COLLECTION}"


def _scope(tenant_id: str, project_id: str) -> tuple[str, str]:
    return (tenant_id, project_id)


@runtime_checkable
class IdentityGraphStore(Protocol):
    def issued_campaign_ids(self) -> set[str]: ...

    def issued_market_ids(self) -> set[str]: ...

    def put_market(self, value: CanonicalMarket) -> CanonicalMarket: ...

    def get_market(
        self, *, tenant_id: str, project_id: str, market_id: str
    ) -> CanonicalMarket | None: ...

    def list_canonical_markets(
        self, *, tenant_id: str, project_id: str
    ) -> list[CanonicalMarket]: ...

    def put_market_binding(self, value: BusinessMarketBinding) -> BusinessMarketBinding: ...

    def get_market_binding(
        self,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
        business_market_ref: str,
    ) -> BusinessMarketBinding | None: ...

    def list_market_bindings(
        self, *, tenant_id: str, project_id: str
    ) -> list[BusinessMarketBinding]: ...

    def put_campaign(self, value: CanonicalCampaign) -> CanonicalCampaign: ...

    def get_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign | None: ...

    def list_campaigns(self, *, tenant_id: str, project_id: str) -> list[CanonicalCampaign]: ...

    def put_tracking(self, value: CampaignTrackingBinding) -> CampaignTrackingBinding: ...

    def list_tracking(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignTrackingBinding]: ...

    def put_external(self, value: CampaignExternalBinding) -> CampaignExternalBinding: ...

    def list_external(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignExternalBinding]: ...

    def put_source(self, value: GA4PropertySourceBinding) -> GA4PropertySourceBinding: ...

    def list_sources(
        self, *, tenant_id: str, project_id: str
    ) -> list[GA4PropertySourceBinding]: ...

    def get_source(
        self, *, tenant_id: str, project_id: str, ga4_source_binding_id: str
    ) -> GA4PropertySourceBinding | None: ...

    def put_topology(self, value: GA4SourceTopology) -> GA4SourceTopology: ...

    def get_topology(self, *, tenant_id: str, project_id: str) -> GA4SourceTopology | None: ...

    def put_policy(self, value: MarketResolutionPolicy) -> MarketResolutionPolicy: ...

    def get_policy(
        self, *, tenant_id: str, project_id: str, policy_id: str | None = None
    ) -> MarketResolutionPolicy | None: ...

    def put_edge(self, value: MarketingIdentityEdge) -> MarketingIdentityEdge: ...

    def list_edges(self, *, tenant_id: str, project_id: str) -> list[MarketingIdentityEdge]: ...

    def put_topology_receipt(
        self, value: GA4TopologyReadinessReceipt
    ) -> GA4TopologyReadinessReceipt: ...

    def get_topology_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt | None: ...


class InMemoryIdentityGraphStore:
    """Test/local store. Cloud persistence is IG-02."""

    def __init__(self) -> None:
        self._issued_campaign_ids: set[str] = set()
        self._issued_market_ids: set[str] = set()
        self.campaigns: dict[tuple[str, str, str], CanonicalCampaign] = {}
        self.markets: dict[tuple[str, str, str], CanonicalMarket] = {}
        self.market_bindings: dict[tuple[str, str, str, str], BusinessMarketBinding] = {}
        self.tracking: dict[tuple[str, str], list[CampaignTrackingBinding]] = {}
        self.external: dict[tuple[str, str], list[CampaignExternalBinding]] = {}
        self.sources: dict[tuple[str, str], dict[str, GA4PropertySourceBinding]] = {}
        self.topologies: dict[tuple[str, str], GA4SourceTopology] = {}
        self.receipts: dict[tuple[str, str], GA4TopologyReadinessReceipt] = {}
        self.policies: dict[tuple[str, str], dict[str, MarketResolutionPolicy]] = {}
        self.edges: dict[tuple[str, str], list[MarketingIdentityEdge]] = {}
        self.campaign_scope: dict[str, tuple[str, str]] = {}

    def issued_campaign_ids(self) -> set[str]:
        return set(self._issued_campaign_ids)

    def issued_market_ids(self) -> set[str]:
        return set(self._issued_market_ids)

    def put_market(self, value: CanonicalMarket) -> CanonicalMarket:
        key = (value.tenant_id, value.project_id, value.market_id)
        existing = self.markets.get(key)
        if existing is None and value.market_id in self._issued_market_ids:
            raise IdentityGraphError(
                f"market_id {value.market_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._issued_market_ids.add(value.market_id)
        self.markets[key] = value
        return value

    def get_market(
        self, *, tenant_id: str, project_id: str, market_id: str
    ) -> CanonicalMarket | None:
        return self.markets.get((tenant_id, project_id, market_id))

    def list_canonical_markets(
        self, *, tenant_id: str, project_id: str
    ) -> list[CanonicalMarket]:
        return [
            market
            for (tid, pid, _), market in self.markets.items()
            if tid == tenant_id and pid == project_id
        ]

    def put_market_binding(self, value: BusinessMarketBinding) -> BusinessMarketBinding:
        key = (
            value.tenant_id,
            value.project_id,
            value.business_profile_snapshot_id,
            value.business_market_ref,
        )
        self.market_bindings[key] = value
        return value

    def get_market_binding(
        self,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
        business_market_ref: str,
    ) -> BusinessMarketBinding | None:
        return self.market_bindings.get((tenant_id, project_id, snapshot_id, business_market_ref))

    def list_market_bindings(
        self, *, tenant_id: str, project_id: str
    ) -> list[BusinessMarketBinding]:
        return [
            binding
            for (tid, pid, _, _), binding in self.market_bindings.items()
            if tid == tenant_id and pid == project_id
        ]

    def put_campaign(self, value: CanonicalCampaign) -> CanonicalCampaign:
        key = (value.tenant_id, value.project_id, value.campaign_id)
        existing = self.campaigns.get(key)
        if existing is None and value.campaign_id in self._issued_campaign_ids:
            raise IdentityGraphError(
                f"campaign_id {value.campaign_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._issued_campaign_ids.add(value.campaign_id)
        self.campaigns[key] = value
        self.campaign_scope[value.campaign_id] = _scope(value.tenant_id, value.project_id)
        return value

    def get_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign | None:
        return self.campaigns.get((tenant_id, project_id, campaign_id))

    def list_campaigns(self, *, tenant_id: str, project_id: str) -> list[CanonicalCampaign]:
        return [
            campaign
            for (tid, pid, _), campaign in self.campaigns.items()
            if tid == tenant_id and pid == project_id
        ]

    def put_tracking(self, value: CampaignTrackingBinding) -> CampaignTrackingBinding:
        scope = self.campaign_scope.get(value.campaign_id)
        if scope is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {value.campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        bucket = self.tracking.setdefault(scope, [])
        bucket[:] = [
            item for item in bucket if item.tracking_binding_id != value.tracking_binding_id
        ]
        bucket.append(value)
        return value

    def list_tracking(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignTrackingBinding]:
        rows = list(self.tracking.get(_scope(tenant_id, project_id), []))
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_external(self, value: CampaignExternalBinding) -> CampaignExternalBinding:
        scope = self.campaign_scope.get(value.campaign_id)
        if scope is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {value.campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        bucket = self.external.setdefault(scope, [])
        bucket[:] = [item for item in bucket if item.binding_id != value.binding_id]
        bucket.append(value)
        return value

    def list_external(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignExternalBinding]:
        rows = list(self.external.get(_scope(tenant_id, project_id), []))
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_source(self, value: GA4PropertySourceBinding) -> GA4PropertySourceBinding:
        bucket = self.sources.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.ga4_source_binding_id] = value
        return value

    def list_sources(self, *, tenant_id: str, project_id: str) -> list[GA4PropertySourceBinding]:
        return list(self.sources.get(_scope(tenant_id, project_id), {}).values())

    def get_source(
        self, *, tenant_id: str, project_id: str, ga4_source_binding_id: str
    ) -> GA4PropertySourceBinding | None:
        return self.sources.get(_scope(tenant_id, project_id), {}).get(ga4_source_binding_id)

    def put_topology(self, value: GA4SourceTopology) -> GA4SourceTopology:
        self.topologies[_scope(value.tenant_id, value.project_id)] = value
        return value

    def get_topology(self, *, tenant_id: str, project_id: str) -> GA4SourceTopology | None:
        return self.topologies.get(_scope(tenant_id, project_id))

    def put_policy(self, value: MarketResolutionPolicy) -> MarketResolutionPolicy:
        bucket = self.policies.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.policy_id] = value
        return value

    def get_policy(
        self, *, tenant_id: str, project_id: str, policy_id: str | None = None
    ) -> MarketResolutionPolicy | None:
        bucket = self.policies.get(_scope(tenant_id, project_id), {})
        if policy_id is not None:
            return bucket.get(policy_id)
        if len(bucket) == 1:
            return next(iter(bucket.values()))
        return None

    def put_edge(self, value: MarketingIdentityEdge) -> MarketingIdentityEdge:
        bucket = self.edges.setdefault(_scope(value.tenant_id, value.project_id), [])
        bucket[:] = [item for item in bucket if item.edge_id != value.edge_id]
        bucket.append(value)
        return value

    def list_edges(self, *, tenant_id: str, project_id: str) -> list[MarketingIdentityEdge]:
        return list(self.edges.get(_scope(tenant_id, project_id), []))

    def put_topology_receipt(
        self, value: GA4TopologyReadinessReceipt
    ) -> GA4TopologyReadinessReceipt:
        self.receipts[_scope(value.tenant_id, value.project_id)] = value
        return value

    def get_topology_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt | None:
        return self.receipts.get(_scope(tenant_id, project_id))

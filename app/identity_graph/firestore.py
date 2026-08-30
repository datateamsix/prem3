"""Production Firestore backing for Identity Graph. In-memory remains CI/local."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
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
from app.identity_graph.store import FIRESTORE_GRAPH_COLLECTION

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_ISSUED = "identity_graph_issued"
KIND_MARKETS = "markets"
KIND_BINDINGS = "market_bindings"
KIND_CAMPAIGNS = "campaigns"
KIND_TRACKING = "tracking"
KIND_EXTERNAL = "external"
KIND_SOURCES = "sources"
KIND_TOPOLOGY = "topology"
KIND_POLICIES = "policies"
KIND_EDGES = "edges"
KIND_RECEIPT = "topology_receipt"


class FirestoreIdentityGraphStore:
    """Durable Identity Graph store. Planning consumes it; it does not own CanonicalMarket."""

    def __init__(self, client: Any) -> None:
        self._db = client

    def _workspace(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COLLECTION_TENANTS)
            .document(tenant_id)
            .collection(COLLECTION_WORKSPACES)
            .document(workspace_id)
        )

    def _items(self, tenant_id: str, workspace_id: str, kind: str):
        return (
            self._workspace(tenant_id, workspace_id)
            .collection(FIRESTORE_GRAPH_COLLECTION)
            .document(kind)
            .collection("items")
        )

    def _issued(self, kind: str, resource_id: str):
        return self._db.collection(COL_ISSUED).document(f"{kind}__{resource_id}")

    def _put_model(
        self, tenant_id: str, workspace_id: str, kind: str, resource_id: str, model: Any
    ) -> None:
        self._items(tenant_id, workspace_id, kind).document(resource_id).set(
            model_to_document(model)
        )

    def _get_model(
        self, tenant_id: str, workspace_id: str, kind: str, resource_id: str, model_type: Any
    ):
        snap = self._items(tenant_id, workspace_id, kind).document(resource_id).get()
        if not snap.exists:
            return None
        return document_to_model(model_type, snap.to_dict())

    def _list_models(self, tenant_id: str, workspace_id: str, kind: str, model_type: Any) -> list:
        rows = []
        for snap in self._items(tenant_id, workspace_id, kind).stream():
            rows.append(document_to_model(model_type, snap.to_dict()))
        return rows

    def _claim_id(self, *, kind: str, resource_id: str, tenant_id: str, project_id: str) -> None:
        ref = self._issued(kind, resource_id)
        snap = ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            if str(data.get("tenant_id")) != tenant_id or str(data.get("workspace_id")) != project_id:
                raise IdentityGraphError(
                    f"{kind.rstrip('s')}_id {resource_id} was already issued and cannot be reused.",
                    code="ID_REUSED",
                )
            return
        ref.set({"tenant_id": tenant_id, "workspace_id": project_id})

    def _issued_ids(self, kind: str) -> set[str]:
        prefix = f"{kind}__"
        found: set[str] = set()
        for snap in self._db.collection(COL_ISSUED).stream():
            if snap.id.startswith(prefix):
                found.add(snap.id[len(prefix) :])
        return found

    def _campaign_scope(self, campaign_id: str) -> tuple[str, str] | None:
        snap = self._issued("campaign", campaign_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return str(data["tenant_id"]), str(data["workspace_id"])

    def issued_campaign_ids(self) -> set[str]:
        return self._issued_ids("campaign")

    def issued_market_ids(self) -> set[str]:
        return self._issued_ids("market")

    def put_market(self, value: CanonicalMarket) -> CanonicalMarket:
        self._claim_id(
            kind="market",
            resource_id=value.market_id,
            tenant_id=value.tenant_id,
            project_id=value.project_id,
        )
        self._put_model(
            value.tenant_id, value.project_id, KIND_MARKETS, value.market_id, value
        )
        return value

    def get_market(
        self, *, tenant_id: str, project_id: str, market_id: str
    ) -> CanonicalMarket | None:
        return self._get_model(tenant_id, project_id, KIND_MARKETS, market_id, CanonicalMarket)

    def list_canonical_markets(
        self, *, tenant_id: str, project_id: str
    ) -> list[CanonicalMarket]:
        return self._list_models(tenant_id, project_id, KIND_MARKETS, CanonicalMarket)

    def put_market_binding(self, value: BusinessMarketBinding) -> BusinessMarketBinding:
        self._put_model(
            value.tenant_id,
            value.project_id,
            KIND_BINDINGS,
            value.binding_id,
            value,
        )
        return value

    def get_market_binding(
        self,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
        business_market_ref: str,
    ) -> BusinessMarketBinding | None:
        for binding in self.list_market_bindings(tenant_id=tenant_id, project_id=project_id):
            if (
                binding.business_profile_snapshot_id == snapshot_id
                and binding.business_market_ref == business_market_ref
            ):
                return binding
        return None

    def list_market_bindings(
        self, *, tenant_id: str, project_id: str
    ) -> list[BusinessMarketBinding]:
        return self._list_models(tenant_id, project_id, KIND_BINDINGS, BusinessMarketBinding)

    def put_campaign(self, value: CanonicalCampaign) -> CanonicalCampaign:
        self._claim_id(
            kind="campaign",
            resource_id=value.campaign_id,
            tenant_id=value.tenant_id,
            project_id=value.project_id,
        )
        self._put_model(
            value.tenant_id, value.project_id, KIND_CAMPAIGNS, value.campaign_id, value
        )
        return value

    def get_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign | None:
        return self._get_model(
            tenant_id, project_id, KIND_CAMPAIGNS, campaign_id, CanonicalCampaign
        )

    def list_campaigns(self, *, tenant_id: str, project_id: str) -> list[CanonicalCampaign]:
        return self._list_models(tenant_id, project_id, KIND_CAMPAIGNS, CanonicalCampaign)

    def put_tracking(self, value: CampaignTrackingBinding) -> CampaignTrackingBinding:
        scope = self._campaign_scope(value.campaign_id)
        if scope is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {value.campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        self._put_model(scope[0], scope[1], KIND_TRACKING, value.tracking_binding_id, value)
        return value

    def list_tracking(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignTrackingBinding]:
        rows = self._list_models(tenant_id, project_id, KIND_TRACKING, CampaignTrackingBinding)
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_external(self, value: CampaignExternalBinding) -> CampaignExternalBinding:
        scope = self._campaign_scope(value.campaign_id)
        if scope is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {value.campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        self._put_model(scope[0], scope[1], KIND_EXTERNAL, value.binding_id, value)
        return value

    def list_external(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignExternalBinding]:
        rows = self._list_models(tenant_id, project_id, KIND_EXTERNAL, CampaignExternalBinding)
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_source(self, value: GA4PropertySourceBinding) -> GA4PropertySourceBinding:
        self._put_model(
            value.tenant_id,
            value.project_id,
            KIND_SOURCES,
            value.ga4_source_binding_id,
            value,
        )
        return value

    def list_sources(
        self, *, tenant_id: str, project_id: str
    ) -> list[GA4PropertySourceBinding]:
        return self._list_models(tenant_id, project_id, KIND_SOURCES, GA4PropertySourceBinding)

    def get_source(
        self, *, tenant_id: str, project_id: str, ga4_source_binding_id: str
    ) -> GA4PropertySourceBinding | None:
        return self._get_model(
            tenant_id, project_id, KIND_SOURCES, ga4_source_binding_id, GA4PropertySourceBinding
        )

    def put_topology(self, value: GA4SourceTopology) -> GA4SourceTopology:
        self._put_model(value.tenant_id, value.project_id, KIND_TOPOLOGY, "current", value)
        return value

    def get_topology(self, *, tenant_id: str, project_id: str) -> GA4SourceTopology | None:
        return self._get_model(tenant_id, project_id, KIND_TOPOLOGY, "current", GA4SourceTopology)

    def put_policy(self, value: MarketResolutionPolicy) -> MarketResolutionPolicy:
        self._put_model(
            value.tenant_id, value.project_id, KIND_POLICIES, value.policy_id, value
        )
        return value

    def get_policy(
        self, *, tenant_id: str, project_id: str, policy_id: str | None = None
    ) -> MarketResolutionPolicy | None:
        if policy_id is not None:
            return self._get_model(
                tenant_id, project_id, KIND_POLICIES, policy_id, MarketResolutionPolicy
            )
        rows = self._list_models(tenant_id, project_id, KIND_POLICIES, MarketResolutionPolicy)
        if len(rows) == 1:
            return rows[0]
        return None

    def put_edge(self, value: MarketingIdentityEdge) -> MarketingIdentityEdge:
        self._put_model(value.tenant_id, value.project_id, KIND_EDGES, value.edge_id, value)
        return value

    def list_edges(self, *, tenant_id: str, project_id: str) -> list[MarketingIdentityEdge]:
        return self._list_models(tenant_id, project_id, KIND_EDGES, MarketingIdentityEdge)

    def put_topology_receipt(
        self, value: GA4TopologyReadinessReceipt
    ) -> GA4TopologyReadinessReceipt:
        self._put_model(value.tenant_id, value.project_id, KIND_RECEIPT, "current", value)
        return value

    def get_topology_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt | None:
        return self._get_model(
            tenant_id, project_id, KIND_RECEIPT, "current", GA4TopologyReadinessReceipt
        )

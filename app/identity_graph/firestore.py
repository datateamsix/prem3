"""Production Firestore backing for Marketing Identity Graph. InMemory remains CI/local."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
from app.identity_graph.contracts import (
    AudienceExternalBinding,
    AudienceLedgerValidationReceipt,
    BusinessMarketBinding,
    CampaignExternalBinding,
    CampaignIdentityResolution,
    CampaignLedgerValidationReceipt,
    CampaignTrackingBinding,
    CampaignTrackingInstructions,
    CanonicalAudience,
    CanonicalCampaign,
    CanonicalMarket,
    CanonicalPersona,
    CustomCampaignIdentifierRule,
    GA4PropertySourceBinding,
    GA4SourceTopology,
    GA4TopologyReadinessReceipt,
    IdentityCoverageReadModel,
    MarketResolutionPolicy,
    PersonaLedgerValidationReceipt,
    TrackingObservation,
    TrackingVerificationReceipt,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.relationships import MarketingIdentityEdge
from app.identity_graph.store import FIRESTORE_GRAPH_COLLECTION

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_INDEX = "identity_graph_index"
COL_CAMPAIGNS = "campaigns"
COL_MARKETS = "markets"
COL_MARKET_BINDINGS = "market_bindings"
COL_TRACKING = "campaign_tracking"
COL_INSTRUCTIONS = "campaign_tracking_instructions"
COL_RECEIPTS = "campaign_receipts"
COL_EXTERNAL = "campaign_external"
COL_AUDIENCE_EXTERNAL = "audience_external"
COL_CUSTOM_RULES = "custom_identifier_rules"
COL_OBSERVATIONS = "tracking_observations"
COL_RESOLUTIONS = "identity_resolutions"
COL_VERIFICATION = "tracking_verification_receipts"
COL_COVERAGE = "identity_coverage"
COL_SOURCES = "ga4_sources"
COL_TOPOLOGY = "ga4_topology"
COL_TOPOLOGY_RECEIPTS = "ga4_topology_receipts"
COL_POLICIES = "market_policies"
COL_EDGES = "edges"
COL_PERSONAS = "personas"
COL_AUDIENCES = "audiences"
COL_PERSONA_RECEIPTS = "persona_receipts"
COL_AUDIENCE_RECEIPTS = "audience_receipts"


class FirestoreIdentityGraphStore:
    def __init__(self, client: Any) -> None:
        self._db = client

    def _workspace(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COLLECTION_TENANTS)
            .document(tenant_id)
            .collection(COLLECTION_WORKSPACES)
            .document(workspace_id)
        )

    def _graph(self, tenant_id: str, workspace_id: str):
        return self._workspace(tenant_id, workspace_id).collection(
            FIRESTORE_GRAPH_COLLECTION
        ).document("current")

    def _col(self, tenant_id: str, workspace_id: str, collection: str):
        return self._graph(tenant_id, workspace_id).collection(collection)

    def _index_campaign(self, campaign_id: str, tenant_id: str, project_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"campaign__{campaign_id}").set(
            {"tenant_id": tenant_id, "workspace_id": project_id, "kind": "campaign"}
        )

    def _index_market(self, market_id: str, tenant_id: str, project_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"market__{market_id}").set(
            {"tenant_id": tenant_id, "workspace_id": project_id, "kind": "market"}
        )

    def _index_persona(self, persona_id: str, tenant_id: str, project_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"persona__{persona_id}").set(
            {"tenant_id": tenant_id, "workspace_id": project_id, "kind": "persona"}
        )

    def _index_audience(self, audience_id: str, tenant_id: str, project_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"audience__{audience_id}").set(
            {"tenant_id": tenant_id, "workspace_id": project_id, "kind": "audience"}
        )

    def _index_campaign_binding(self, binding_id: str, tenant_id: str, project_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"campaign_binding__{binding_id}").set(
            {"tenant_id": tenant_id, "workspace_id": project_id, "kind": "campaign_binding"}
        )

    def _index_audience_binding(self, binding_id: str, tenant_id: str, project_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"audience_binding__{binding_id}").set(
            {"tenant_id": tenant_id, "workspace_id": project_id, "kind": "audience_binding"}
        )

    def _lookup(self, kind: str, key: str) -> tuple[str, str] | None:
        snap = self._db.collection(COL_INDEX).document(f"{kind}__{key}").get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return str(data["tenant_id"]), str(data["workspace_id"])

    def _put(
        self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model: Any
    ) -> None:
        self._col(tenant_id, workspace_id, collection).document(doc_id).set(
            model_to_document(model)
        )

    def _get(
        self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model_type: Any
    ):
        snap = self._col(tenant_id, workspace_id, collection).document(doc_id).get()
        if not snap.exists:
            return None
        return document_to_model(model_type, snap.to_dict())

    def _list(
        self, tenant_id: str, workspace_id: str, collection: str, model_type: Any
    ) -> list[Any]:
        rows = []
        for snap in self._col(tenant_id, workspace_id, collection).stream():
            rows.append(document_to_model(model_type, snap.to_dict()))
        return rows

    def _delete_doc(self, tenant_id: str, workspace_id: str, collection: str, doc_id: str) -> None:
        self._col(tenant_id, workspace_id, collection).document(doc_id).delete()

    def issued_campaign_ids(self) -> set[str]:
        ids: set[str] = set()
        for snap in self._db.collection(COL_INDEX).stream():
            if str(snap.id).startswith("campaign__"):
                ids.add(str(snap.id).removeprefix("campaign__"))
        return ids

    def issued_market_ids(self) -> set[str]:
        ids: set[str] = set()
        for snap in self._db.collection(COL_INDEX).stream():
            if str(snap.id).startswith("market__"):
                ids.add(str(snap.id).removeprefix("market__"))
        return ids

    def issued_persona_ids(self) -> set[str]:
        ids: set[str] = set()
        for snap in self._db.collection(COL_INDEX).stream():
            if str(snap.id).startswith("persona__"):
                ids.add(str(snap.id).removeprefix("persona__"))
        return ids

    def issued_audience_ids(self) -> set[str]:
        ids: set[str] = set()
        for snap in self._db.collection(COL_INDEX).stream():
            if str(snap.id).startswith("audience__"):
                ids.add(str(snap.id).removeprefix("audience__"))
        return ids

    def put_market(self, value: CanonicalMarket) -> CanonicalMarket:
        existing = self.get_market(
            tenant_id=value.tenant_id, project_id=value.project_id, market_id=value.market_id
        )
        loc = self._lookup("market", value.market_id)
        if existing is None and loc is not None:
            raise IdentityGraphError(
                f"market_id {value.market_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._put(value.tenant_id, value.project_id, COL_MARKETS, value.market_id, value)
        self._index_market(value.market_id, value.tenant_id, value.project_id)
        return value

    def get_market(
        self, *, tenant_id: str, project_id: str, market_id: str
    ) -> CanonicalMarket | None:
        return self._get(tenant_id, project_id, COL_MARKETS, market_id, CanonicalMarket)

    def list_canonical_markets(
        self, *, tenant_id: str, project_id: str
    ) -> list[CanonicalMarket]:
        return self._list(tenant_id, project_id, COL_MARKETS, CanonicalMarket)

    def put_market_binding(self, value: BusinessMarketBinding) -> BusinessMarketBinding:
        doc_id = f"{value.business_profile_snapshot_id}__{value.business_market_ref}"
        self._put(value.tenant_id, value.project_id, COL_MARKET_BINDINGS, doc_id, value)
        return value

    def get_market_binding(
        self,
        *,
        tenant_id: str,
        project_id: str,
        snapshot_id: str,
        business_market_ref: str,
    ) -> BusinessMarketBinding | None:
        doc_id = f"{snapshot_id}__{business_market_ref}"
        return self._get(tenant_id, project_id, COL_MARKET_BINDINGS, doc_id, BusinessMarketBinding)

    def list_market_bindings(
        self, *, tenant_id: str, project_id: str
    ) -> list[BusinessMarketBinding]:
        return self._list(tenant_id, project_id, COL_MARKET_BINDINGS, BusinessMarketBinding)

    def put_campaign(self, value: CanonicalCampaign) -> CanonicalCampaign:
        existing = self.get_campaign(
            tenant_id=value.tenant_id, project_id=value.project_id, campaign_id=value.campaign_id
        )
        loc = self._lookup("campaign", value.campaign_id)
        if existing is None and loc is not None:
            raise IdentityGraphError(
                f"campaign_id {value.campaign_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._put(value.tenant_id, value.project_id, COL_CAMPAIGNS, value.campaign_id, value)
        self._index_campaign(value.campaign_id, value.tenant_id, value.project_id)
        return value

    def get_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign | None:
        return self._get(tenant_id, project_id, COL_CAMPAIGNS, campaign_id, CanonicalCampaign)

    def list_campaigns(self, *, tenant_id: str, project_id: str) -> list[CanonicalCampaign]:
        return self._list(tenant_id, project_id, COL_CAMPAIGNS, CanonicalCampaign)

    def delete_campaign(self, *, tenant_id: str, project_id: str, campaign_id: str) -> None:
        found = self.get_campaign(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        self._delete_doc(tenant_id, project_id, COL_CAMPAIGNS, campaign_id)
        self._delete_doc(tenant_id, project_id, COL_INSTRUCTIONS, campaign_id)
        self._delete_doc(tenant_id, project_id, COL_RECEIPTS, campaign_id)
        for item in self.list_tracking(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        ):
            self._delete_doc(tenant_id, project_id, COL_TRACKING, item.tracking_binding_id)
        for item in self.list_external(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        ):
            self._delete_doc(tenant_id, project_id, COL_EXTERNAL, item.binding_id)
        for edge in self.list_edges(tenant_id=tenant_id, project_id=project_id):
            if edge.from_node_id == campaign_id or edge.to_node_id == campaign_id:
                self._delete_doc(tenant_id, project_id, COL_EDGES, edge.edge_id)

    def put_persona(self, value: CanonicalPersona) -> CanonicalPersona:
        existing = self.get_persona(
            tenant_id=value.tenant_id, project_id=value.project_id, persona_id=value.persona_id
        )
        loc = self._lookup("persona", value.persona_id)
        if existing is None and loc is not None:
            raise IdentityGraphError(
                f"persona_id {value.persona_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._put(value.tenant_id, value.project_id, COL_PERSONAS, value.persona_id, value)
        self._index_persona(value.persona_id, value.tenant_id, value.project_id)
        return value

    def get_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> CanonicalPersona | None:
        return self._get(tenant_id, project_id, COL_PERSONAS, persona_id, CanonicalPersona)

    def list_personas(self, *, tenant_id: str, project_id: str) -> list[CanonicalPersona]:
        return self._list(tenant_id, project_id, COL_PERSONAS, CanonicalPersona)

    def delete_persona(self, *, tenant_id: str, project_id: str, persona_id: str) -> None:
        found = self.get_persona(tenant_id=tenant_id, project_id=project_id, persona_id=persona_id)
        if found is None:
            raise IdentityGraphError(
                f"Unknown persona_id {persona_id}.",
                code="UNKNOWN_PERSONA",
            )
        self._delete_doc(tenant_id, project_id, COL_PERSONAS, persona_id)
        self._delete_doc(tenant_id, project_id, COL_PERSONA_RECEIPTS, persona_id)
        for edge in self.list_edges(tenant_id=tenant_id, project_id=project_id):
            if edge.from_node_id == persona_id or edge.to_node_id == persona_id:
                self._delete_doc(tenant_id, project_id, COL_EDGES, edge.edge_id)

    def put_persona_receipt(
        self, value: PersonaLedgerValidationReceipt
    ) -> PersonaLedgerValidationReceipt:
        self._put(value.tenant_id, value.project_id, COL_PERSONA_RECEIPTS, value.persona_id, value)
        return value

    def get_persona_receipt(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> PersonaLedgerValidationReceipt | None:
        return self._get(
            tenant_id, project_id, COL_PERSONA_RECEIPTS, persona_id, PersonaLedgerValidationReceipt
        )

    def put_audience(self, value: CanonicalAudience) -> CanonicalAudience:
        existing = self.get_audience(
            tenant_id=value.tenant_id, project_id=value.project_id, audience_id=value.audience_id
        )
        loc = self._lookup("audience", value.audience_id)
        if existing is None and loc is not None:
            raise IdentityGraphError(
                f"audience_id {value.audience_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._put(value.tenant_id, value.project_id, COL_AUDIENCES, value.audience_id, value)
        self._index_audience(value.audience_id, value.tenant_id, value.project_id)
        return value

    def get_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> CanonicalAudience | None:
        return self._get(tenant_id, project_id, COL_AUDIENCES, audience_id, CanonicalAudience)

    def list_audiences(self, *, tenant_id: str, project_id: str) -> list[CanonicalAudience]:
        return self._list(tenant_id, project_id, COL_AUDIENCES, CanonicalAudience)

    def delete_audience(self, *, tenant_id: str, project_id: str, audience_id: str) -> None:
        found = self.get_audience(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Unknown audience_id {audience_id}.",
                code="UNKNOWN_AUDIENCE",
            )
        self._delete_doc(tenant_id, project_id, COL_AUDIENCES, audience_id)
        self._delete_doc(tenant_id, project_id, COL_AUDIENCE_RECEIPTS, audience_id)
        for edge in self.list_edges(tenant_id=tenant_id, project_id=project_id):
            if edge.from_node_id == audience_id or edge.to_node_id == audience_id:
                self._delete_doc(tenant_id, project_id, COL_EDGES, edge.edge_id)

    def put_audience_receipt(
        self, value: AudienceLedgerValidationReceipt
    ) -> AudienceLedgerValidationReceipt:
        self._put(
            value.tenant_id, value.project_id, COL_AUDIENCE_RECEIPTS, value.audience_id, value
        )
        return value

    def get_audience_receipt(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> AudienceLedgerValidationReceipt | None:
        return self._get(
            tenant_id,
            project_id,
            COL_AUDIENCE_RECEIPTS,
            audience_id,
            AudienceLedgerValidationReceipt,
        )

    def put_tracking(self, value: CampaignTrackingBinding) -> CampaignTrackingBinding:
        loc = self._lookup("campaign", value.campaign_id)
        if loc is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {value.campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        self._put(loc[0], loc[1], COL_TRACKING, value.tracking_binding_id, value)
        return value

    def list_tracking(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignTrackingBinding]:
        rows = self._list(tenant_id, project_id, COL_TRACKING, CampaignTrackingBinding)
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_tracking_instructions(
        self, value: CampaignTrackingInstructions
    ) -> CampaignTrackingInstructions:
        self._put(
            value.tenant_id, value.project_id, COL_INSTRUCTIONS, value.campaign_id, value
        )
        return value

    def get_tracking_instructions(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignTrackingInstructions | None:
        return self._get(
            tenant_id, project_id, COL_INSTRUCTIONS, campaign_id, CampaignTrackingInstructions
        )

    def put_campaign_receipt(
        self, value: CampaignLedgerValidationReceipt
    ) -> CampaignLedgerValidationReceipt:
        self._put(value.tenant_id, value.project_id, COL_RECEIPTS, value.campaign_id, value)
        return value

    def get_campaign_receipt(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignLedgerValidationReceipt | None:
        return self._get(
            tenant_id, project_id, COL_RECEIPTS, campaign_id, CampaignLedgerValidationReceipt
        )

    def put_external(self, value: CampaignExternalBinding) -> CampaignExternalBinding:
        loc = self._lookup("campaign", value.campaign_id)
        if loc is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {value.campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        self._put(loc[0], loc[1], COL_EXTERNAL, value.binding_id, value)
        self._index_campaign_binding(value.binding_id, loc[0], loc[1])
        return value

    def get_external(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> CampaignExternalBinding | None:
        return self._get(tenant_id, project_id, COL_EXTERNAL, binding_id, CampaignExternalBinding)

    def list_external(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignExternalBinding]:
        rows = self._list(tenant_id, project_id, COL_EXTERNAL, CampaignExternalBinding)
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_audience_external(self, value: AudienceExternalBinding) -> AudienceExternalBinding:
        loc = self._lookup("audience", value.audience_id)
        if loc is None:
            raise IdentityGraphError(
                f"Unknown audience_id {value.audience_id}.",
                code="UNKNOWN_AUDIENCE",
            )
        self._put(loc[0], loc[1], COL_AUDIENCE_EXTERNAL, value.binding_id, value)
        self._index_audience_binding(value.binding_id, loc[0], loc[1])
        return value

    def get_audience_external(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> AudienceExternalBinding | None:
        return self._get(
            tenant_id, project_id, COL_AUDIENCE_EXTERNAL, binding_id, AudienceExternalBinding
        )

    def list_audience_external(
        self, *, tenant_id: str, project_id: str, audience_id: str | None = None
    ) -> list[AudienceExternalBinding]:
        rows = self._list(tenant_id, project_id, COL_AUDIENCE_EXTERNAL, AudienceExternalBinding)
        if audience_id is not None:
            return [item for item in rows if item.audience_id == audience_id]
        return rows

    def put_custom_rule(self, value: CustomCampaignIdentifierRule) -> CustomCampaignIdentifierRule:
        self._put(value.tenant_id, value.project_id, COL_CUSTOM_RULES, value.rule_id, value)
        return value

    def get_custom_rule(
        self, *, tenant_id: str, project_id: str, rule_id: str
    ) -> CustomCampaignIdentifierRule | None:
        return self._get(
            tenant_id,
            project_id,
            COL_CUSTOM_RULES,
            rule_id,
            CustomCampaignIdentifierRule,
        )

    def list_custom_rules(
        self, *, tenant_id: str, project_id: str
    ) -> list[CustomCampaignIdentifierRule]:
        return self._list(tenant_id, project_id, COL_CUSTOM_RULES, CustomCampaignIdentifierRule)

    def put_observation(self, value: TrackingObservation) -> TrackingObservation:
        self._put(value.tenant_id, value.project_id, COL_OBSERVATIONS, value.observation_id, value)
        return value

    def get_observation(
        self, *, tenant_id: str, project_id: str, observation_id: str
    ) -> TrackingObservation | None:
        return self._get(
            tenant_id, project_id, COL_OBSERVATIONS, observation_id, TrackingObservation
        )

    def list_observations(
        self, *, tenant_id: str, project_id: str
    ) -> list[TrackingObservation]:
        return self._list(tenant_id, project_id, COL_OBSERVATIONS, TrackingObservation)

    def put_resolution(self, value: CampaignIdentityResolution) -> CampaignIdentityResolution:
        self._put(value.tenant_id, value.project_id, COL_RESOLUTIONS, value.resolution_id, value)
        return value

    def get_resolution(
        self, *, tenant_id: str, project_id: str, resolution_id: str
    ) -> CampaignIdentityResolution | None:
        return self._get(
            tenant_id, project_id, COL_RESOLUTIONS, resolution_id, CampaignIdentityResolution
        )

    def list_resolutions(
        self, *, tenant_id: str, project_id: str
    ) -> list[CampaignIdentityResolution]:
        return self._list(tenant_id, project_id, COL_RESOLUTIONS, CampaignIdentityResolution)

    def put_verification_receipt(
        self, value: TrackingVerificationReceipt
    ) -> TrackingVerificationReceipt:
        self._put(value.tenant_id, value.project_id, COL_VERIFICATION, value.receipt_id, value)
        return value

    def get_verification_receipt(
        self, *, tenant_id: str, project_id: str, receipt_id: str
    ) -> TrackingVerificationReceipt | None:
        return self._get(
            tenant_id, project_id, COL_VERIFICATION, receipt_id, TrackingVerificationReceipt
        )

    def list_verification_receipts(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[TrackingVerificationReceipt]:
        rows = self._list(tenant_id, project_id, COL_VERIFICATION, TrackingVerificationReceipt)
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_coverage(self, value: IdentityCoverageReadModel) -> IdentityCoverageReadModel:
        self._put(value.tenant_id, value.project_id, COL_COVERAGE, "current", value)
        return value

    def get_coverage(
        self, *, tenant_id: str, project_id: str
    ) -> IdentityCoverageReadModel | None:
        return self._get(tenant_id, project_id, COL_COVERAGE, "current", IdentityCoverageReadModel)

    def put_source(self, value: GA4PropertySourceBinding) -> GA4PropertySourceBinding:
        self._put(
            value.tenant_id,
            value.project_id,
            COL_SOURCES,
            value.ga4_source_binding_id,
            value,
        )
        return value

    def list_sources(self, *, tenant_id: str, project_id: str) -> list[GA4PropertySourceBinding]:
        return self._list(tenant_id, project_id, COL_SOURCES, GA4PropertySourceBinding)

    def get_source(
        self, *, tenant_id: str, project_id: str, ga4_source_binding_id: str
    ) -> GA4PropertySourceBinding | None:
        return self._get(
            tenant_id, project_id, COL_SOURCES, ga4_source_binding_id, GA4PropertySourceBinding
        )

    def put_topology(self, value: GA4SourceTopology) -> GA4SourceTopology:
        self._put(value.tenant_id, value.project_id, COL_TOPOLOGY, "current", value)
        return value

    def get_topology(self, *, tenant_id: str, project_id: str) -> GA4SourceTopology | None:
        return self._get(tenant_id, project_id, COL_TOPOLOGY, "current", GA4SourceTopology)

    def put_policy(self, value: MarketResolutionPolicy) -> MarketResolutionPolicy:
        self._put(value.tenant_id, value.project_id, COL_POLICIES, value.policy_id, value)
        return value

    def get_policy(
        self, *, tenant_id: str, project_id: str, policy_id: str | None = None
    ) -> MarketResolutionPolicy | None:
        if policy_id is not None:
            return self._get(tenant_id, project_id, COL_POLICIES, policy_id, MarketResolutionPolicy)
        rows = self._list(tenant_id, project_id, COL_POLICIES, MarketResolutionPolicy)
        if len(rows) == 1:
            return rows[0]
        return None

    def put_edge(self, value: MarketingIdentityEdge) -> MarketingIdentityEdge:
        self._put(value.tenant_id, value.project_id, COL_EDGES, value.edge_id, value)
        return value

    def list_edges(self, *, tenant_id: str, project_id: str) -> list[MarketingIdentityEdge]:
        return self._list(tenant_id, project_id, COL_EDGES, MarketingIdentityEdge)

    def delete_edge(self, *, tenant_id: str, project_id: str, edge_id: str) -> None:
        self._delete_doc(tenant_id, project_id, COL_EDGES, edge_id)

    def put_topology_receipt(
        self, value: GA4TopologyReadinessReceipt
    ) -> GA4TopologyReadinessReceipt:
        self._put(value.tenant_id, value.project_id, COL_TOPOLOGY_RECEIPTS, "current", value)
        return value

    def get_topology_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt | None:
        return self._get(
            tenant_id, project_id, COL_TOPOLOGY_RECEIPTS, "current", GA4TopologyReadinessReceipt
        )

"""Identity Graph persistence port. In-memory for tests; Firestore for cloud."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.identity_graph.analytics.contracts import (
    AnalyticalArtifactRef,
    UnifiedAnalyticsCompilation,
    UnifiedAnalyticsReadinessReceipt,
)
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

FIRESTORE_GRAPH_COLLECTION = "identity_graph"


def firestore_graph_path(*, tenant_id: str, workspace_id: str) -> str:
    """Workspace-scoped Identity Graph metadata root. No people, budget, or events."""
    return f"tenants/{tenant_id}/workspaces/{workspace_id}/{FIRESTORE_GRAPH_COLLECTION}"


def _scope(tenant_id: str, project_id: str) -> tuple[str, str]:
    return (tenant_id, project_id)


@runtime_checkable
class IdentityGraphStore(Protocol):
    def issued_campaign_ids(self) -> set[str]: ...

    def issued_market_ids(self) -> set[str]: ...

    def issued_persona_ids(self) -> set[str]: ...

    def issued_audience_ids(self) -> set[str]: ...

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

    def delete_campaign(self, *, tenant_id: str, project_id: str, campaign_id: str) -> None: ...

    def put_persona(self, value: CanonicalPersona) -> CanonicalPersona: ...

    def get_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> CanonicalPersona | None: ...

    def list_personas(self, *, tenant_id: str, project_id: str) -> list[CanonicalPersona]: ...

    def delete_persona(self, *, tenant_id: str, project_id: str, persona_id: str) -> None: ...

    def put_persona_receipt(
        self, value: PersonaLedgerValidationReceipt
    ) -> PersonaLedgerValidationReceipt: ...

    def get_persona_receipt(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> PersonaLedgerValidationReceipt | None: ...

    def put_audience(self, value: CanonicalAudience) -> CanonicalAudience: ...

    def get_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> CanonicalAudience | None: ...

    def list_audiences(self, *, tenant_id: str, project_id: str) -> list[CanonicalAudience]: ...

    def delete_audience(self, *, tenant_id: str, project_id: str, audience_id: str) -> None: ...

    def put_audience_receipt(
        self, value: AudienceLedgerValidationReceipt
    ) -> AudienceLedgerValidationReceipt: ...

    def get_audience_receipt(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> AudienceLedgerValidationReceipt | None: ...

    def put_tracking(self, value: CampaignTrackingBinding) -> CampaignTrackingBinding: ...

    def list_tracking(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignTrackingBinding]: ...

    def put_tracking_instructions(
        self, value: CampaignTrackingInstructions
    ) -> CampaignTrackingInstructions: ...

    def get_tracking_instructions(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignTrackingInstructions | None: ...

    def put_campaign_receipt(
        self, value: CampaignLedgerValidationReceipt
    ) -> CampaignLedgerValidationReceipt: ...

    def get_campaign_receipt(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignLedgerValidationReceipt | None: ...

    def put_external(self, value: CampaignExternalBinding) -> CampaignExternalBinding: ...

    def get_external(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> CampaignExternalBinding | None: ...

    def list_external(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignExternalBinding]: ...

    def put_audience_external(self, value: AudienceExternalBinding) -> AudienceExternalBinding: ...

    def get_audience_external(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> AudienceExternalBinding | None: ...

    def list_audience_external(
        self, *, tenant_id: str, project_id: str, audience_id: str | None = None
    ) -> list[AudienceExternalBinding]: ...

    def put_custom_rule(
        self, value: CustomCampaignIdentifierRule
    ) -> CustomCampaignIdentifierRule: ...

    def get_custom_rule(
        self, *, tenant_id: str, project_id: str, rule_id: str
    ) -> CustomCampaignIdentifierRule | None: ...

    def list_custom_rules(
        self, *, tenant_id: str, project_id: str
    ) -> list[CustomCampaignIdentifierRule]: ...

    def put_observation(self, value: TrackingObservation) -> TrackingObservation: ...

    def get_observation(
        self, *, tenant_id: str, project_id: str, observation_id: str
    ) -> TrackingObservation | None: ...

    def list_observations(
        self, *, tenant_id: str, project_id: str
    ) -> list[TrackingObservation]: ...

    def put_resolution(self, value: CampaignIdentityResolution) -> CampaignIdentityResolution: ...

    def get_resolution(
        self, *, tenant_id: str, project_id: str, resolution_id: str
    ) -> CampaignIdentityResolution | None: ...

    def list_resolutions(
        self, *, tenant_id: str, project_id: str
    ) -> list[CampaignIdentityResolution]: ...

    def put_verification_receipt(
        self, value: TrackingVerificationReceipt
    ) -> TrackingVerificationReceipt: ...

    def get_verification_receipt(
        self, *, tenant_id: str, project_id: str, receipt_id: str
    ) -> TrackingVerificationReceipt | None: ...

    def list_verification_receipts(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[TrackingVerificationReceipt]: ...

    def put_coverage(self, value: IdentityCoverageReadModel) -> IdentityCoverageReadModel: ...

    def get_coverage(
        self, *, tenant_id: str, project_id: str
    ) -> IdentityCoverageReadModel | None: ...

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

    def delete_edge(self, *, tenant_id: str, project_id: str, edge_id: str) -> None: ...

    def put_topology_receipt(
        self, value: GA4TopologyReadinessReceipt
    ) -> GA4TopologyReadinessReceipt: ...

    def get_topology_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt | None: ...

    def put_compilation(
        self, value: UnifiedAnalyticsCompilation
    ) -> UnifiedAnalyticsCompilation: ...

    def get_compilation(
        self, *, tenant_id: str, project_id: str, compilation_id: str
    ) -> UnifiedAnalyticsCompilation | None: ...

    def get_compilation_by_fingerprint(
        self, *, tenant_id: str, project_id: str, fingerprint: str
    ) -> UnifiedAnalyticsCompilation | None: ...

    def list_compilations(
        self, *, tenant_id: str, project_id: str
    ) -> list[UnifiedAnalyticsCompilation]: ...

    def put_analytics_receipt(
        self, value: UnifiedAnalyticsReadinessReceipt
    ) -> UnifiedAnalyticsReadinessReceipt: ...

    def get_analytics_receipt(
        self, *, tenant_id: str, project_id: str, receipt_id: str | None = None
    ) -> UnifiedAnalyticsReadinessReceipt | None: ...

    def list_analytics_receipts(
        self, *, tenant_id: str, project_id: str
    ) -> list[UnifiedAnalyticsReadinessReceipt]: ...

    def put_analytics_artifact(self, value: AnalyticalArtifactRef) -> AnalyticalArtifactRef: ...

    def list_analytics_artifacts(
        self, *, tenant_id: str, project_id: str, compilation_id: str | None = None
    ) -> list[AnalyticalArtifactRef]: ...


class InMemoryIdentityGraphStore:
    """Test/local store. Cloud persistence is FirestoreIdentityGraphStore."""

    def __init__(self) -> None:
        self._issued_campaign_ids: set[str] = set()
        self._issued_market_ids: set[str] = set()
        self._issued_persona_ids: set[str] = set()
        self._issued_audience_ids: set[str] = set()
        self.campaigns: dict[tuple[str, str, str], CanonicalCampaign] = {}
        self.markets: dict[tuple[str, str, str], CanonicalMarket] = {}
        self.personas: dict[tuple[str, str, str], CanonicalPersona] = {}
        self.audiences: dict[tuple[str, str, str], CanonicalAudience] = {}
        self.persona_receipts: dict[tuple[str, str, str], PersonaLedgerValidationReceipt] = {}
        self.audience_receipts: dict[tuple[str, str, str], AudienceLedgerValidationReceipt] = {}
        self.market_bindings: dict[tuple[str, str, str, str], BusinessMarketBinding] = {}
        self.tracking: dict[tuple[str, str], list[CampaignTrackingBinding]] = {}
        self.tracking_instructions: dict[tuple[str, str, str], CampaignTrackingInstructions] = {}
        self.campaign_receipts: dict[tuple[str, str, str], CampaignLedgerValidationReceipt] = {}
        self.external: dict[tuple[str, str], list[CampaignExternalBinding]] = {}
        self.audience_external: dict[tuple[str, str], list[AudienceExternalBinding]] = {}
        self.custom_rules: dict[tuple[str, str], dict[str, CustomCampaignIdentifierRule]] = {}
        self.observations: dict[tuple[str, str], dict[str, TrackingObservation]] = {}
        self.resolutions: dict[tuple[str, str], dict[str, CampaignIdentityResolution]] = {}
        self.verification_receipts: dict[
            tuple[str, str], dict[str, TrackingVerificationReceipt]
        ] = {}
        self.coverage: dict[tuple[str, str], IdentityCoverageReadModel] = {}
        self.sources: dict[tuple[str, str], dict[str, GA4PropertySourceBinding]] = {}
        self.topologies: dict[tuple[str, str], GA4SourceTopology] = {}
        self.receipts: dict[tuple[str, str], GA4TopologyReadinessReceipt] = {}
        self.policies: dict[tuple[str, str], dict[str, MarketResolutionPolicy]] = {}
        self.edges: dict[tuple[str, str], list[MarketingIdentityEdge]] = {}
        self.campaign_scope: dict[str, tuple[str, str]] = {}
        self.compilations: dict[tuple[str, str], dict[str, UnifiedAnalyticsCompilation]] = {}
        self.analytics_receipts: dict[
            tuple[str, str], dict[str, UnifiedAnalyticsReadinessReceipt]
        ] = {}
        self.analytics_current_receipt: dict[tuple[str, str], str] = {}
        self.analytics_artifacts: dict[tuple[str, str], dict[str, AnalyticalArtifactRef]] = {}
        self.compilation_fingerprints: dict[tuple[str, str, str], str] = {}

    def issued_campaign_ids(self) -> set[str]:
        return set(self._issued_campaign_ids)

    def issued_market_ids(self) -> set[str]:
        return set(self._issued_market_ids)

    def issued_persona_ids(self) -> set[str]:
        return set(self._issued_persona_ids)

    def issued_audience_ids(self) -> set[str]:
        return set(self._issued_audience_ids)

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

    def delete_campaign(self, *, tenant_id: str, project_id: str, campaign_id: str) -> None:
        key = (tenant_id, project_id, campaign_id)
        if key not in self.campaigns:
            raise IdentityGraphError(
                f"Unknown campaign_id {campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        del self.campaigns[key]
        self.tracking_instructions.pop(key, None)
        self.campaign_receipts.pop(key, None)
        scope = _scope(tenant_id, project_id)
        bucket = self.tracking.get(scope, [])
        self.tracking[scope] = [item for item in bucket if item.campaign_id != campaign_id]
        externals = self.external.get(scope, [])
        self.external[scope] = [item for item in externals if item.campaign_id != campaign_id]
        edges = self.edges.get(scope, [])
        self.edges[scope] = [
            item
            for item in edges
            if item.from_node_id != campaign_id and item.to_node_id != campaign_id
        ]

    def put_persona(self, value: CanonicalPersona) -> CanonicalPersona:
        key = (value.tenant_id, value.project_id, value.persona_id)
        existing = self.personas.get(key)
        if existing is None and value.persona_id in self._issued_persona_ids:
            raise IdentityGraphError(
                f"persona_id {value.persona_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._issued_persona_ids.add(value.persona_id)
        self.personas[key] = value
        return value

    def get_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> CanonicalPersona | None:
        return self.personas.get((tenant_id, project_id, persona_id))

    def list_personas(self, *, tenant_id: str, project_id: str) -> list[CanonicalPersona]:
        return [
            persona
            for (tid, pid, _), persona in self.personas.items()
            if tid == tenant_id and pid == project_id
        ]

    def delete_persona(self, *, tenant_id: str, project_id: str, persona_id: str) -> None:
        key = (tenant_id, project_id, persona_id)
        if key not in self.personas:
            raise IdentityGraphError(
                f"Unknown persona_id {persona_id}.",
                code="UNKNOWN_PERSONA",
            )
        del self.personas[key]
        self.persona_receipts.pop(key, None)
        scope = _scope(tenant_id, project_id)
        edges = self.edges.get(scope, [])
        self.edges[scope] = [
            item
            for item in edges
            if item.from_node_id != persona_id and item.to_node_id != persona_id
        ]

    def put_persona_receipt(
        self, value: PersonaLedgerValidationReceipt
    ) -> PersonaLedgerValidationReceipt:
        key = (value.tenant_id, value.project_id, value.persona_id)
        self.persona_receipts[key] = value
        return value

    def get_persona_receipt(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> PersonaLedgerValidationReceipt | None:
        return self.persona_receipts.get((tenant_id, project_id, persona_id))

    def put_audience(self, value: CanonicalAudience) -> CanonicalAudience:
        key = (value.tenant_id, value.project_id, value.audience_id)
        existing = self.audiences.get(key)
        if existing is None and value.audience_id in self._issued_audience_ids:
            raise IdentityGraphError(
                f"audience_id {value.audience_id} was already issued and cannot be reused.",
                code="ID_REUSED",
            )
        self._issued_audience_ids.add(value.audience_id)
        self.audiences[key] = value
        self.campaign_scope[value.audience_id] = _scope(value.tenant_id, value.project_id)
        return value

    def get_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> CanonicalAudience | None:
        return self.audiences.get((tenant_id, project_id, audience_id))

    def list_audiences(self, *, tenant_id: str, project_id: str) -> list[CanonicalAudience]:
        return [
            audience
            for (tid, pid, _), audience in self.audiences.items()
            if tid == tenant_id and pid == project_id
        ]

    def delete_audience(self, *, tenant_id: str, project_id: str, audience_id: str) -> None:
        key = (tenant_id, project_id, audience_id)
        if key not in self.audiences:
            raise IdentityGraphError(
                f"Unknown audience_id {audience_id}.",
                code="UNKNOWN_AUDIENCE",
            )
        del self.audiences[key]
        self.audience_receipts.pop(key, None)
        scope = _scope(tenant_id, project_id)
        edges = self.edges.get(scope, [])
        self.edges[scope] = [
            item
            for item in edges
            if item.from_node_id != audience_id and item.to_node_id != audience_id
        ]

    def put_audience_receipt(
        self, value: AudienceLedgerValidationReceipt
    ) -> AudienceLedgerValidationReceipt:
        key = (value.tenant_id, value.project_id, value.audience_id)
        self.audience_receipts[key] = value
        return value

    def get_audience_receipt(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> AudienceLedgerValidationReceipt | None:
        return self.audience_receipts.get((tenant_id, project_id, audience_id))

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

    def put_tracking_instructions(
        self, value: CampaignTrackingInstructions
    ) -> CampaignTrackingInstructions:
        key = (value.tenant_id, value.project_id, value.campaign_id)
        self.tracking_instructions[key] = value
        return value

    def get_tracking_instructions(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignTrackingInstructions | None:
        return self.tracking_instructions.get((tenant_id, project_id, campaign_id))

    def put_campaign_receipt(
        self, value: CampaignLedgerValidationReceipt
    ) -> CampaignLedgerValidationReceipt:
        key = (value.tenant_id, value.project_id, value.campaign_id)
        self.campaign_receipts[key] = value
        return value

    def get_campaign_receipt(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignLedgerValidationReceipt | None:
        return self.campaign_receipts.get((tenant_id, project_id, campaign_id))

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

    def get_external(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> CampaignExternalBinding | None:
        for item in self.external.get(_scope(tenant_id, project_id), []):
            if item.binding_id == binding_id:
                return item
        return None

    def list_external(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[CampaignExternalBinding]:
        rows = list(self.external.get(_scope(tenant_id, project_id), []))
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_audience_external(self, value: AudienceExternalBinding) -> AudienceExternalBinding:
        scope = self.campaign_scope.get(value.audience_id)
        if scope is None:
            raise IdentityGraphError(
                f"Unknown audience_id {value.audience_id}.",
                code="UNKNOWN_AUDIENCE",
            )
        bucket = self.audience_external.setdefault(scope, [])
        bucket[:] = [item for item in bucket if item.binding_id != value.binding_id]
        bucket.append(value)
        return value

    def get_audience_external(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> AudienceExternalBinding | None:
        for item in self.audience_external.get(_scope(tenant_id, project_id), []):
            if item.binding_id == binding_id:
                return item
        return None

    def list_audience_external(
        self, *, tenant_id: str, project_id: str, audience_id: str | None = None
    ) -> list[AudienceExternalBinding]:
        rows = list(self.audience_external.get(_scope(tenant_id, project_id), []))
        if audience_id is not None:
            return [item for item in rows if item.audience_id == audience_id]
        return rows

    def put_custom_rule(self, value: CustomCampaignIdentifierRule) -> CustomCampaignIdentifierRule:
        bucket = self.custom_rules.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.rule_id] = value
        return value

    def get_custom_rule(
        self, *, tenant_id: str, project_id: str, rule_id: str
    ) -> CustomCampaignIdentifierRule | None:
        return self.custom_rules.get(_scope(tenant_id, project_id), {}).get(rule_id)

    def list_custom_rules(
        self, *, tenant_id: str, project_id: str
    ) -> list[CustomCampaignIdentifierRule]:
        return list(self.custom_rules.get(_scope(tenant_id, project_id), {}).values())

    def put_observation(self, value: TrackingObservation) -> TrackingObservation:
        bucket = self.observations.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.observation_id] = value
        return value

    def get_observation(
        self, *, tenant_id: str, project_id: str, observation_id: str
    ) -> TrackingObservation | None:
        return self.observations.get(_scope(tenant_id, project_id), {}).get(observation_id)

    def list_observations(
        self, *, tenant_id: str, project_id: str
    ) -> list[TrackingObservation]:
        return list(self.observations.get(_scope(tenant_id, project_id), {}).values())

    def put_resolution(self, value: CampaignIdentityResolution) -> CampaignIdentityResolution:
        bucket = self.resolutions.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.resolution_id] = value
        return value

    def get_resolution(
        self, *, tenant_id: str, project_id: str, resolution_id: str
    ) -> CampaignIdentityResolution | None:
        return self.resolutions.get(_scope(tenant_id, project_id), {}).get(resolution_id)

    def list_resolutions(
        self, *, tenant_id: str, project_id: str
    ) -> list[CampaignIdentityResolution]:
        return list(self.resolutions.get(_scope(tenant_id, project_id), {}).values())

    def put_verification_receipt(
        self, value: TrackingVerificationReceipt
    ) -> TrackingVerificationReceipt:
        bucket = self.verification_receipts.setdefault(
            _scope(value.tenant_id, value.project_id), {}
        )
        bucket[value.receipt_id] = value
        return value

    def get_verification_receipt(
        self, *, tenant_id: str, project_id: str, receipt_id: str
    ) -> TrackingVerificationReceipt | None:
        return self.verification_receipts.get(_scope(tenant_id, project_id), {}).get(receipt_id)

    def list_verification_receipts(
        self, *, tenant_id: str, project_id: str, campaign_id: str | None = None
    ) -> list[TrackingVerificationReceipt]:
        rows = list(self.verification_receipts.get(_scope(tenant_id, project_id), {}).values())
        if campaign_id is not None:
            return [item for item in rows if item.campaign_id == campaign_id]
        return rows

    def put_coverage(self, value: IdentityCoverageReadModel) -> IdentityCoverageReadModel:
        self.coverage[_scope(value.tenant_id, value.project_id)] = value
        return value

    def get_coverage(
        self, *, tenant_id: str, project_id: str
    ) -> IdentityCoverageReadModel | None:
        return self.coverage.get(_scope(tenant_id, project_id))

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

    def delete_edge(self, *, tenant_id: str, project_id: str, edge_id: str) -> None:
        scope = _scope(tenant_id, project_id)
        bucket = self.edges.get(scope, [])
        self.edges[scope] = [item for item in bucket if item.edge_id != edge_id]

    def put_topology_receipt(
        self, value: GA4TopologyReadinessReceipt
    ) -> GA4TopologyReadinessReceipt:
        self.receipts[_scope(value.tenant_id, value.project_id)] = value
        return value

    def get_topology_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt | None:
        return self.receipts.get(_scope(tenant_id, project_id))

    def put_compilation(
        self, value: UnifiedAnalyticsCompilation
    ) -> UnifiedAnalyticsCompilation:
        bucket = self.compilations.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.compilation_id] = value
        self.compilation_fingerprints[
            (value.tenant_id, value.project_id, value.fingerprint)
        ] = value.compilation_id
        return value

    def get_compilation(
        self, *, tenant_id: str, project_id: str, compilation_id: str
    ) -> UnifiedAnalyticsCompilation | None:
        return self.compilations.get(_scope(tenant_id, project_id), {}).get(compilation_id)

    def get_compilation_by_fingerprint(
        self, *, tenant_id: str, project_id: str, fingerprint: str
    ) -> UnifiedAnalyticsCompilation | None:
        compilation_id = self.compilation_fingerprints.get((tenant_id, project_id, fingerprint))
        if compilation_id is None:
            return None
        return self.get_compilation(
            tenant_id=tenant_id, project_id=project_id, compilation_id=compilation_id
        )

    def list_compilations(
        self, *, tenant_id: str, project_id: str
    ) -> list[UnifiedAnalyticsCompilation]:
        return list(self.compilations.get(_scope(tenant_id, project_id), {}).values())

    def put_analytics_receipt(
        self, value: UnifiedAnalyticsReadinessReceipt
    ) -> UnifiedAnalyticsReadinessReceipt:
        scope = _scope(value.tenant_id, value.project_id)
        bucket = self.analytics_receipts.setdefault(scope, {})
        bucket[value.receipt_id] = value
        self.analytics_current_receipt[scope] = value.receipt_id
        return value

    def get_analytics_receipt(
        self, *, tenant_id: str, project_id: str, receipt_id: str | None = None
    ) -> UnifiedAnalyticsReadinessReceipt | None:
        scope = _scope(tenant_id, project_id)
        bucket = self.analytics_receipts.get(scope, {})
        if receipt_id is not None:
            return bucket.get(receipt_id)
        current = self.analytics_current_receipt.get(scope)
        if current is None:
            return None
        return bucket.get(current)

    def list_analytics_receipts(
        self, *, tenant_id: str, project_id: str
    ) -> list[UnifiedAnalyticsReadinessReceipt]:
        return list(self.analytics_receipts.get(_scope(tenant_id, project_id), {}).values())

    def put_analytics_artifact(self, value: AnalyticalArtifactRef) -> AnalyticalArtifactRef:
        bucket = self.analytics_artifacts.setdefault(_scope(value.tenant_id, value.project_id), {})
        bucket[value.artifact_id] = value
        return value

    def list_analytics_artifacts(
        self, *, tenant_id: str, project_id: str, compilation_id: str | None = None
    ) -> list[AnalyticalArtifactRef]:
        rows = list(self.analytics_artifacts.get(_scope(tenant_id, project_id), {}).values())
        if compilation_id is not None:
            return [item for item in rows if item.compilation_id == compilation_id]
        return rows

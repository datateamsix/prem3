"""Project-scoped Marketing Identity Graph service. In-memory contract behavior for IG-00."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.business_iq.store import BusinessIqStore
from app.core.errors import InvalidResourceIdentifierError
from app.core.tenancy import require_tenant
from app.domain.channels.registry import cached_channel_registry
from app.domain.channels.validation import ChannelValidationError, assert_channel_id_in_registry
from app.identity_graph.contracts import (
    BusinessMarketBinding,
    CampaignCreateResult,
    CampaignExternalBinding,
    CampaignIdentityResolution,
    CampaignTrackingBinding,
    CampaignTrackingInstructions,
    CanonicalCampaign,
    CanonicalMarket,
    GA4MarketCoverage,
    GA4PropertySourceBinding,
    GA4SourceTopology,
    GA4TopologyDiscoveryResult,
    GA4TopologyReadinessReceipt,
    IdentityGraphOverview,
    MarketResolutionEvidence,
    MarketResolutionPolicy,
    MTAIdentityTouchpointRefs,
    ObservedCampaignSignals,
)
from app.identity_graph.enums import (
    BindingStatus,
    BqLocationClass,
    CampaignIdentitySource,
    CampaignStatus,
    GA4TopologyKind,
    GA4TopologyReadinessState,
    IdentityGraphCapabilityState,
    IdentityGraphComponentState,
    IdentitySourceAuthority,
    MappingMethod,
    MarketCoverageStatus,
    MarketingIdentityEdgeType,
    MarketingIdentityNodeType,
    MarketKind,
    MarketMappingMethod,
    MarketResolutionMethod,
    MarketStatus,
    ResolutionAuthority,
    SourceOverlapPolicy,
    TopologyStatus,
    TrackingImplementationStatus,
    TrackingKind,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.fingerprint import identity_fingerprint
from app.identity_graph.ids import (
    assert_market_id_shape,
    new_binding_id,
    new_campaign_id,
    new_edge_id,
    new_ga4_source_binding_id,
    new_market_id,
    new_policy_id,
    new_topology_id,
    new_tracking_binding_id,
)
from app.identity_graph.relationships import MarketingIdentityEdge
from app.identity_graph.resolution import (
    assert_not_self_parent,
    assert_parent_same_project,
    resolve_campaign_identity,
    would_create_cycle,
)
from app.identity_graph.store import IdentityGraphStore, InMemoryIdentityGraphStore
from app.registry.loader import load_registry


def require_canonical_provider_id(provider_id: str) -> None:
    catalog = load_registry()
    if not any(entry.provider_id == provider_id for entry in catalog.providers):
        raise IdentityGraphError(
            f"Unknown provider_id {provider_id!r} is not in the provider registry.",
            code="UNKNOWN_PROVIDER",
        )


def assert_authority_not_silently_verified(
    current: IdentitySourceAuthority, proposed: IdentitySourceAuthority
) -> None:
    if (
        current == IdentitySourceAuthority.PROVIDER_DISCOVERED
        and proposed == IdentitySourceAuthority.SYSTEM_VERIFIED
    ):
        raise IdentityGraphError(
            "PROVIDER_DISCOVERED cannot become SYSTEM_VERIFIED without confirmation.",
            code="AUTHORITY_PROMOTION_FORBIDDEN",
        )


_GEO_LEVEL_TO_KIND = {
    "COUNTRY": MarketKind.COUNTRY,
    "REGION": MarketKind.REGION,
    "MULTI_COUNTRY_REGION": MarketKind.MULTI_COUNTRY_REGION,
    "SUBNATIONAL": MarketKind.SUBNATIONAL,
    "GLOBAL": MarketKind.GLOBAL,
    "CUSTOM": MarketKind.CUSTOM,
}


def _market_kind_from_biq(geo_level: str | None) -> MarketKind:
    if geo_level is None:
        return MarketKind.CUSTOM
    return _GEO_LEVEL_TO_KIND.get(geo_level.upper(), MarketKind.CUSTOM)


class CampaignIdentityService:
    def __init__(
        self,
        *,
        store: IdentityGraphStore | None = None,
        business_iq_store: BusinessIqStore | None = None,
    ) -> None:
        self.store = store or InMemoryIdentityGraphStore()
        self.business_iq_store = business_iq_store

    def create_campaign(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        actor_id: str,
        description: str | None = None,
        status: CampaignStatus = CampaignStatus.PLANNED,
        market_ids: tuple[str, ...] = (),
        channel_ids: tuple[str, ...] = (),
        parent_campaign_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        utm_campaign: str | None = None,
        campaign_name_raw: str | None = None,
    ) -> CampaignCreateResult:
        self._authorize(tenant_id)
        campaign_id = new_campaign_id(issued=self.store.issued_campaign_ids())
        now = datetime.now(UTC)
        campaign = CanonicalCampaign(
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            project_id=project_id,
            parent_campaign_id=None,
            name=name,
            campaign_name_raw=campaign_name_raw or name,
            description=description,
            status=status,
            market_ids=market_ids,
            channel_ids=channel_ids,
            start_date=start_date,
            end_date=end_date,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        self._validate_scope(campaign)
        if parent_campaign_id is not None:
            campaign = campaign.model_copy(update={"parent_campaign_id": parent_campaign_id})
            self._validate_parent(campaign)
        campaign = campaign.model_copy(update={"fingerprint": identity_fingerprint(campaign)})
        self.store.put_campaign(campaign)
        tracking = self._default_utm_binding(campaign, actor_id=actor_id)
        self.store.put_tracking(tracking)
        self._write_campaign_edges(campaign, tracking)
        display = utm_campaign or name
        instructions = CampaignTrackingInstructions(
            campaign_id=campaign_id,
            utm_id=campaign_id,
            utm_campaign=display,
            query_parameters={"utm_id": campaign_id, "utm_campaign": display},
            implementation_status=TrackingImplementationStatus.GENERATED,
        )
        return CampaignCreateResult(
            campaign=campaign, tracking=tracking, instructions=instructions
        )

    def list_campaigns(self, *, tenant_id: str, project_id: str) -> list[CanonicalCampaign]:
        self._authorize(tenant_id)
        return self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)

    def create_market(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        actor_id: str,
        description: str | None = None,
        market_kind: MarketKind = MarketKind.CUSTOM,
        country_codes: tuple[str, ...] = (),
        region_codes: tuple[str, ...] = (),
        status: MarketStatus = MarketStatus.ACTIVE,
    ) -> CanonicalMarket:
        self._authorize(tenant_id)
        now = datetime.now(UTC)
        market = CanonicalMarket(
            market_id=new_market_id(issued=self.store.issued_market_ids()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            market_kind=market_kind,
            status=status,
            country_codes=country_codes,
            region_codes=region_codes,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        market = market.model_copy(update={"fingerprint": identity_fingerprint(market)})
        return self.store.put_market(market)

    def bind_business_iq_markets(
        self, *, tenant_id: str, project_id: str, actor_id: str
    ) -> list[BusinessMarketBinding]:
        self._authorize(tenant_id)
        if self.business_iq_store is None:
            raise IdentityGraphError(
                "Business IQ store is required to bind markets.",
                code="UNKNOWN_MARKET",
            )
        profile = self.business_iq_store.get_profile(
            tenant_id=tenant_id, workspace_id=project_id
        )
        if profile is None:
            raise IdentityGraphError(
                "Business profile not found.",
                code="UNKNOWN_MARKET",
            )
        snapshot_id = profile.current_snapshot_id
        created: list[BusinessMarketBinding] = []
        for market in profile.markets:
            existing = self.store.get_market_binding(
                tenant_id=tenant_id,
                project_id=project_id,
                snapshot_id=snapshot_id,
                business_market_ref=market.market_id,
            )
            if existing is not None:
                created.append(existing)
                continue
            reused_id = self._canonical_id_for_legacy_ref(
                tenant_id=tenant_id,
                project_id=project_id,
                business_market_ref=market.market_id,
            )
            if reused_id is not None:
                mapping_method = MarketMappingMethod.EXACT_EXISTING_BINDING
                canonical_id = reused_id
            else:
                canonical = self.create_market(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    name=market.name,
                    actor_id=actor_id,
                    market_kind=_market_kind_from_biq(market.geo_level),
                    description=market.custom_text,
                )
                mapping_method = MarketMappingMethod.SERVER_CREATED_FROM_BUSINESS_IQ
                canonical_id = canonical.market_id
            binding = BusinessMarketBinding(
                binding_id=new_binding_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                business_profile_snapshot_id=snapshot_id,
                business_market_ref=market.market_id,
                market_id=canonical_id,
                mapping_method=mapping_method,
                status=BindingStatus.CONFIRMED,
                confirmed_by=actor_id,
                confirmed_at=datetime.now(UTC),
            )
            binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
            created.append(self.store.put_market_binding(binding))
        return created

    def review_legacy_market_name_merge(
        self, *, tenant_id: str, project_id: str, display_name: str
    ) -> ResolutionAuthority:
        self._authorize(tenant_id)
        canonical_matches = [
            market
            for market in self.store.list_canonical_markets(
                tenant_id=tenant_id, project_id=project_id
            )
            if market.name == display_name
        ]
        biq_matches: list[str] = []
        if self.business_iq_store is not None:
            profile = self.business_iq_store.get_profile(
                tenant_id=tenant_id, workspace_id=project_id
            )
            if profile is not None:
                biq_matches = [
                    item.market_id for item in profile.markets if item.name == display_name
                ]
        if len(canonical_matches) > 1 or len(set(biq_matches)) > 1:
            return ResolutionAuthority.REVIEW_REQUIRED
        return ResolutionAuthority.UNRESOLVED

    def list_market_bindings(
        self, *, tenant_id: str, project_id: str
    ) -> list[BusinessMarketBinding]:
        self._authorize(tenant_id)
        return self.store.list_market_bindings(tenant_id=tenant_id, project_id=project_id)

    def list_markets(self, *, tenant_id: str, project_id: str) -> list[CanonicalMarket]:
        self._authorize(tenant_id)
        return self.store.list_canonical_markets(tenant_id=tenant_id, project_id=project_id)

    def set_parent(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        parent_campaign_id: str | None,
    ) -> CanonicalCampaign:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        updated = campaign.model_copy(
            update={"parent_campaign_id": parent_campaign_id, "updated_at": datetime.now(UTC)}
        )
        if parent_campaign_id is not None:
            self._validate_parent(updated)
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_campaign(updated)
        self._replace_child_edge(updated)
        return updated

    def bind_external(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        provider_id: str,
        external_campaign_id: str,
        external_account_id: str | None = None,
        external_campaign_name: str | None = None,
        mapping_method: MappingMethod = MappingMethod.PROVIDER_ID_EXACT,
        status: BindingStatus = BindingStatus.CONFIRMED,
        actor_id: str = "",
    ) -> CampaignExternalBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        require_canonical_provider_id(provider_id)
        binding = CampaignExternalBinding(
            binding_id=new_binding_id(),
            campaign_id=campaign.campaign_id,
            provider_id=provider_id,
            external_account_id=external_account_id,
            external_campaign_id=external_campaign_id,
            external_campaign_name=external_campaign_name,
            mapping_method=mapping_method,
            status=status,
            confirmed_by=actor_id or None,
            confirmed_at=datetime.now(UTC) if status == BindingStatus.CONFIRMED else None,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_external(binding)
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_BOUND_TO_EXTERNAL,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign_id,
                to_node_type=MarketingIdentityNodeType.EXTERNAL_CAMPAIGN,
                to_node_id=external_campaign_id,
            )
        )
        return binding

    def update_external_name(
        self,
        *,
        tenant_id: str,
        project_id: str,
        binding_id: str,
        external_campaign_name: str,
    ) -> CampaignExternalBinding:
        self._authorize(tenant_id)
        for binding in self.store.list_external(tenant_id=tenant_id, project_id=project_id):
            if binding.binding_id != binding_id:
                continue
            updated = binding.model_copy(
                update={"external_campaign_name": external_campaign_name}
            )
            updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
            self.store.put_external(updated)
            return updated
        raise IdentityGraphError("External binding not found.", code="UNKNOWN_BINDING")

    def bind_custom_identifier(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        parameter_name: str,
        parameter_value: str,
        actor_id: str,
        status: BindingStatus = BindingStatus.APPROVED,
    ) -> CampaignTrackingBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        if status != BindingStatus.APPROVED:
            raise IdentityGraphError(
                "Custom identifier bindings require an explicit APPROVED rule.",
                code="CUSTOM_IDENTIFIER_NOT_APPROVED",
            )
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            campaign_id=campaign.campaign_id,
            parameter_name=parameter_name,
            parameter_value=parameter_value,
            tracking_kind=TrackingKind.CUSTOM_EVENT_PARAM,
            status=status,
            created_by=actor_id,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_tracking(binding)
        return binding

    def bind_user_confirmed_mapping(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        actor_id: str,
    ) -> CampaignTrackingBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            campaign_id=campaign.campaign_id,
            parameter_name="user_confirmed",
            parameter_value=campaign.campaign_id,
            tracking_kind=TrackingKind.MANUAL_MAPPING,
            status=BindingStatus.CONFIRMED,
            created_by=actor_id,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_tracking(binding)
        return binding

    def resolve_observed(
        self,
        *,
        tenant_id: str,
        project_id: str,
        signals: ObservedCampaignSignals,
    ) -> CampaignIdentityResolution:
        self._authorize(tenant_id)
        return resolve_campaign_identity(
            campaigns=self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id),
            tracking=self.store.list_tracking(tenant_id=tenant_id, project_id=project_id),
            external=self.store.list_external(tenant_id=tenant_id, project_id=project_id),
            signals=signals,
        )

    def upsert_ga4_source(
        self,
        *,
        tenant_id: str,
        project_id: str,
        ga4_property_id: str,
        bq_project_id: str,
        bq_dataset_id: str,
        bq_location: str = "",
        stream_ids: tuple[str, ...] = (),
        declared_market_ids: tuple[str, ...] = (),
        coverage_start: str | None = None,
        coverage_end: str | None = None,
        traffic_source_capability: bool | None = None,
        freshness_state: str | None = None,
        source_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED,
        overlap_policy: SourceOverlapPolicy | None = None,
        ga4_source_binding_id: str | None = None,
    ) -> GA4PropertySourceBinding:
        self._authorize(tenant_id)
        if declared_market_ids:
            self._validate_markets(tenant_id, project_id, declared_market_ids)
        now = datetime.now(UTC)
        existing = None
        if ga4_source_binding_id is not None:
            existing = self.store.get_source(
                tenant_id=tenant_id,
                project_id=project_id,
                ga4_source_binding_id=ga4_source_binding_id,
            )
            if existing is not None:
                assert_authority_not_silently_verified(existing.source_authority, source_authority)
        binding = GA4PropertySourceBinding(
            ga4_source_binding_id=ga4_source_binding_id or new_ga4_source_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            ga4_property_id=ga4_property_id,
            bq_project_id=bq_project_id,
            bq_dataset_id=bq_dataset_id,
            bq_location=bq_location,
            stream_ids=stream_ids,
            declared_market_ids=declared_market_ids,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            traffic_source_capability=traffic_source_capability,
            freshness_state=freshness_state,
            source_authority=source_authority,
            overlap_policy=overlap_policy,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_source(binding)
        for stream_id in stream_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    edge_type=MarketingIdentityEdgeType.GA4_STREAM_BELONGS_TO_PROPERTY,
                    from_node_type=MarketingIdentityNodeType.GA4_STREAM,
                    from_node_id=stream_id,
                    to_node_type=MarketingIdentityNodeType.GA4_PROPERTY,
                    to_node_id=ga4_property_id,
                )
            )
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=MarketingIdentityEdgeType.BIGQUERY_SOURCE_EXPORTS_PROPERTY,
                from_node_type=MarketingIdentityNodeType.BIGQUERY_GA4_SOURCE,
                from_node_id=binding.ga4_source_binding_id,
                to_node_type=MarketingIdentityNodeType.GA4_PROPERTY,
                to_node_id=ga4_property_id,
            )
        )
        for market_id in declared_market_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    edge_type=MarketingIdentityEdgeType.GA4_PROPERTY_COVERS_MARKET,
                    from_node_type=MarketingIdentityNodeType.GA4_PROPERTY,
                    from_node_id=ga4_property_id,
                    to_node_type=MarketingIdentityNodeType.MARKET,
                    to_node_id=market_id,
                )
            )
        return binding

    def upsert_topology(
        self,
        *,
        tenant_id: str,
        project_id: str,
        topology_kind: GA4TopologyKind,
        source_binding_ids: tuple[str, ...] = (),
        overlap_policy: SourceOverlapPolicy | None = None,
        market_resolution_policy_id: str | None = None,
        topology_id: str | None = None,
    ) -> GA4SourceTopology:
        self._authorize(tenant_id)
        sources = [
            self.store.get_source(
                tenant_id=tenant_id, project_id=project_id, ga4_source_binding_id=item
            )
            for item in source_binding_ids
        ]
        if any(item is None for item in sources):
            raise IdentityGraphError(
                "Topology referenced an unknown GA4 source binding.",
                code="UNKNOWN_GA4_SOURCE",
            )
        issues, status, direct_union_ready, location_class = self._assess_topology(
            topology_kind=topology_kind,
            overlap_policy=overlap_policy,
            sources=tuple(item for item in sources if item is not None),
            market_resolution_policy_id=market_resolution_policy_id,
        )
        topology = GA4SourceTopology(
            topology_id=topology_id or new_topology_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            source_binding_ids=source_binding_ids,
            topology_kind=topology_kind,
            market_resolution_policy_id=market_resolution_policy_id,
            overlap_policy=overlap_policy,
            status=status,
            issues=issues,
            direct_union_ready=direct_union_ready,
            location_class=location_class,
        )
        topology = topology.model_copy(update={"fingerprint": identity_fingerprint(topology)})
        return self.store.put_topology(topology)

    def upsert_market_policy(
        self,
        *,
        tenant_id: str,
        project_id: str,
        allowed_methods: tuple[MarketResolutionMethod, ...],
        policy_id: str | None = None,
    ) -> MarketResolutionPolicy:
        self._authorize(tenant_id)
        if not allowed_methods:
            raise IdentityGraphError(
                "MarketResolutionPolicy must declare allowed methods.",
                code="MARKET_POLICY_EMPTY",
            )
        policy = MarketResolutionPolicy(
            policy_id=policy_id or new_policy_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            allowed_methods=allowed_methods,
        )
        policy = policy.model_copy(update={"fingerprint": identity_fingerprint(policy)})
        return self.store.put_policy(policy)

    def resolve_market(
        self,
        *,
        tenant_id: str,
        project_id: str,
        source_ref: str,
        method: MarketResolutionMethod,
        market_id: str | None,
        policy_id: str | None = None,
        rule_ref: str | None = None,
    ) -> MarketResolutionEvidence:
        self._authorize(tenant_id)
        policy = self.store.get_policy(
            tenant_id=tenant_id, project_id=project_id, policy_id=policy_id
        )
        if policy is None:
            if method == MarketResolutionMethod.GEO_MAPPING:
                return MarketResolutionEvidence(
                    market_id=None,
                    method=MarketResolutionMethod.UNRESOLVED,
                    source_ref=source_ref,
                    authority=ResolutionAuthority.UNRESOLVED,
                    issues=("GEO_MAPPING_NOT_IMPLICIT_DEFAULT",),
                )
            if method == MarketResolutionMethod.UNRESOLVED or market_id is None:
                return MarketResolutionEvidence(
                    market_id=None,
                    method=MarketResolutionMethod.UNRESOLVED,
                    source_ref=source_ref,
                    authority=ResolutionAuthority.UNRESOLVED,
                    issues=("MARKET_UNRESOLVED",),
                )
            return MarketResolutionEvidence(
                market_id=None,
                method=MarketResolutionMethod.UNRESOLVED,
                source_ref=source_ref,
                authority=ResolutionAuthority.UNRESOLVED,
                issues=("MARKET_POLICY_MISSING",),
            )
        if method not in policy.allowed_methods:
            return MarketResolutionEvidence(
                market_id=None,
                method=MarketResolutionMethod.UNRESOLVED,
                source_ref=source_ref,
                rule_ref=rule_ref,
                authority=ResolutionAuthority.UNRESOLVED,
                issues=("METHOD_NOT_ALLOWED",),
            )
        if market_id is None:
            return MarketResolutionEvidence(
                market_id=None,
                method=method,
                source_ref=source_ref,
                rule_ref=rule_ref,
                authority=ResolutionAuthority.UNRESOLVED,
                issues=("MARKET_UNRESOLVED",),
            )
        self._validate_markets(tenant_id, project_id, (market_id,))
        return MarketResolutionEvidence(
            market_id=market_id,
            method=method,
            source_ref=source_ref,
            rule_ref=rule_ref,
            authority=ResolutionAuthority.RESOLVED,
        )

    def overview(self, *, tenant_id: str, project_id: str) -> IdentityGraphOverview:
        self._authorize(tenant_id)
        campaigns = self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
        sources = self.store.list_sources(tenant_id=tenant_id, project_id=project_id)
        mappings = self.store.list_external(tenant_id=tenant_id, project_id=project_id)
        tracking = self.store.list_tracking(tenant_id=tenant_id, project_id=project_id)
        topology = self.store.get_topology(tenant_id=tenant_id, project_id=project_id)
        components: list[IdentityGraphComponentState] = []
        issues: list[str] = []
        ledger_ready = any(
            item.tracking_kind == TrackingKind.PREM3_UTM_ID
            and item.parameter_name == "utm_id"
            and item.parameter_value == item.campaign_id
            for item in tracking
        )
        if ledger_ready:
            components.append(IdentityGraphComponentState.CAMPAIGN_LEDGER_READY)
        canonical_markets = self.store.list_canonical_markets(
            tenant_id=tenant_id, project_id=project_id
        )
        topology_ready = (
            topology is not None
            and topology.status == TopologyStatus.READY
            and bool(canonical_markets)
            and topology.location_class != BqLocationClass.UNKNOWN_LOCATION
            and "MARKET_RESOLUTION_REQUIRED" not in topology.issues
            and "CROSS_LOCATION_REVIEW_REQUIRED" not in topology.issues
        )
        if topology_ready:
            components.append(IdentityGraphComponentState.GA4_TOPOLOGY_READY)
        if topology is not None:
            issues.extend(topology.issues)
        review = any(
            item.status == BindingStatus.REVIEW_REQUIRED for item in mappings
        ) or (topology is not None and topology.status == TopologyStatus.REVIEW_REQUIRED)
        if review:
            state = IdentityGraphCapabilityState.REVIEW_REQUIRED
        elif not campaigns and not sources:
            state = IdentityGraphCapabilityState.NOT_CONFIGURED
        elif ledger_ready and (topology is None or topology_ready):
            state = IdentityGraphCapabilityState.READY
        else:
            state = IdentityGraphCapabilityState.PARTIAL
        return IdentityGraphOverview(
            tenant_id=tenant_id,
            project_id=project_id,
            capability_state=state,
            component_states=tuple(components),
            campaign_count=len(campaigns),
            source_count=len(sources),
            mapping_count=len(mappings),
            issues=tuple(issues),
        )

    def mta_touchpoint_refs(
        self,
        *,
        campaign_id: str | None,
        parent_campaign_id: str | None,
        market_id: str,
        campaign_identity_source: CampaignIdentitySource,
        market_resolution_method: MarketResolutionMethod,
        ga4_source_binding_id: str | None,
    ) -> MTAIdentityTouchpointRefs:
        return MTAIdentityTouchpointRefs(
            campaign_id=campaign_id,
            parent_campaign_id=parent_campaign_id,
            market_id=market_id,
            campaign_identity_source=campaign_identity_source,
            market_resolution_method=market_resolution_method,
            ga4_source_binding_id=ga4_source_binding_id,
        )

    def list_sources(self, *, tenant_id: str, project_id: str) -> list[GA4PropertySourceBinding]:
        self._authorize(tenant_id)
        return self.store.list_sources(tenant_id=tenant_id, project_id=project_id)

    def list_mappings(self, *, tenant_id: str, project_id: str) -> list[CampaignExternalBinding]:
        self._authorize(tenant_id)
        return self.store.list_external(tenant_id=tenant_id, project_id=project_id)

    def discover_ga4_sources(
        self,
        *,
        tenant_id: str,
        project_id: str,
        tables: tuple[dict[str, Any], ...] = (),
    ) -> GA4TopologyDiscoveryResult:
        self._authorize(tenant_id)
        if not tables:
            return GA4TopologyDiscoveryResult(
                tenant_id=tenant_id,
                project_id=project_id,
                location_class=BqLocationClass.UNKNOWN_LOCATION,
                issues=("DISCOVERY_NOT_CONFIGURED",),
            )
        binding_ids: list[str] = []
        locations: list[str] = []
        issues: list[str] = []
        for table in tables:
            project = table.get("bq_project_id")
            dataset = table.get("bq_dataset_id")
            if not project or not dataset:
                issues.append("DISCOVERY_TABLE_INCOMPLETE")
                continue
            location = table.get("bq_location") or ""
            capability = table.get("traffic_source_capability")
            if isinstance(capability, bool):
                traffic_capability: bool | None = capability
            elif isinstance(capability, str):
                traffic_capability = capability.lower() == "true"
            else:
                traffic_capability = None
            source = self.upsert_ga4_source(
                tenant_id=tenant_id,
                project_id=project_id,
                ga4_property_id=str(table.get("ga4_property_id") or dataset),
                bq_project_id=str(project),
                bq_dataset_id=str(dataset),
                bq_location=str(location),
                coverage_start=table.get("coverage_start") or None,
                coverage_end=table.get("coverage_end") or None,
                traffic_source_capability=traffic_capability,
                freshness_state=table.get("freshness_state") or None,
                source_authority=IdentitySourceAuthority.DATA_FOUNDATION_DISCOVERED,
            )
            binding_ids.append(source.ga4_source_binding_id)
            locations.append(location)
        known = {item for item in locations if item}
        if not known:
            location_class = BqLocationClass.UNKNOWN_LOCATION
            issues.append("UNKNOWN_LOCATION")
        elif len(known) == 1:
            location_class = BqLocationClass.SAME_LOCATION
        else:
            location_class = BqLocationClass.CROSS_LOCATION
            issues.append("CROSS_LOCATION_REVIEW_REQUIRED")
        return GA4TopologyDiscoveryResult(
            tenant_id=tenant_id,
            project_id=project_id,
            discovered_source_binding_ids=tuple(binding_ids),
            bq_locations=tuple(sorted(known)),
            location_class=location_class,
            issues=tuple(dict.fromkeys(issues)),
        )

    def validate_ga4_topology(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt:
        self._authorize(tenant_id)
        markets = self.store.list_canonical_markets(tenant_id=tenant_id, project_id=project_id)
        topology = self.store.get_topology(tenant_id=tenant_id, project_id=project_id)
        sources = self.store.list_sources(tenant_id=tenant_id, project_id=project_id)
        issues: list[str] = []
        if not markets:
            issues.append("CANONICAL_MARKETS_REQUIRED")
        if topology is None:
            issues.append("TOPOLOGY_NOT_CONFIGURED")
            location_class = BqLocationClass.UNKNOWN_LOCATION
        else:
            issues.extend(topology.issues)
            location_class = topology.location_class
            if topology.location_class == BqLocationClass.UNKNOWN_LOCATION:
                issues.append("UNKNOWN_LOCATION_NOT_READY_FOR_UNIFIED_COMPILATION")
            if (
                topology.topology_kind
                in {GA4TopologyKind.SINGLE_MASTER_PROPERTY, GA4TopologyKind.MASTER_PLUS_REGIONAL}
                and topology.market_resolution_policy_id is None
                and len(markets) > 1
            ):
                issues.append("MARKET_RESOLUTION_REQUIRED")
        coverage: list[GA4MarketCoverage] = []
        for market in markets:
            bound = [
                source.ga4_source_binding_id
                for source in sources
                if market.market_id in source.declared_market_ids
            ]
            if bound:
                status = MarketCoverageStatus.COMPLETE
            elif sources:
                status = MarketCoverageStatus.MISSING
            else:
                status = MarketCoverageStatus.UNKNOWN
            coverage.append(
                GA4MarketCoverage(
                    market_id=market.market_id,
                    source_binding_ids=tuple(bound),
                    coverage_status=status,
                    issues=() if bound else ("MARKET_COVERAGE_MISSING",),
                )
            )
        if "CANONICAL_MARKETS_REQUIRED" in issues or "TOPOLOGY_NOT_CONFIGURED" in issues:
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_INCOMPLETE
        elif any(
            item in issues
            for item in (
                "CROSS_LOCATION_REVIEW_REQUIRED",
                "OVERLAP_POLICY_REQUIRED",
                "OVERLAP_REVIEW_REQUIRED",
                "MARKET_RESOLUTION_REQUIRED",
                "DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY",
            )
        ) or (topology is not None and topology.status == TopologyStatus.REVIEW_REQUIRED):
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_REVIEW_REQUIRED
        elif issues or any(
            item.coverage_status != MarketCoverageStatus.COMPLETE for item in coverage
        ):
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_INCOMPLETE
        else:
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_READY
        receipt = GA4TopologyReadinessReceipt(
            tenant_id=tenant_id,
            project_id=project_id,
            topology_id=topology.topology_id if topology is not None else None,
            state=state,
            location_class=location_class,
            coverage=tuple(coverage),
            issues=tuple(dict.fromkeys(issues)),
        )
        receipt = receipt.model_copy(update={"fingerprint": identity_fingerprint(receipt)})
        return self.store.put_topology_receipt(receipt)

    def get_ga4_topology(self, *, tenant_id: str, project_id: str) -> GA4SourceTopology | None:
        self._authorize(tenant_id)
        return self.store.get_topology(tenant_id=tenant_id, project_id=project_id)

    def _authorize(self, tenant_id: str) -> None:
        bound = require_tenant()
        if bound.tenant_id != tenant_id:
            raise IdentityGraphError(
                "Caller cannot choose arbitrary tenant authority.",
                code="TENANT_MISMATCH",
            )

    def _require_campaign(
        self, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign:
        found = self.store.get_campaign(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        return found

    def _canonical_id_for_legacy_ref(
        self, *, tenant_id: str, project_id: str, business_market_ref: str
    ) -> str | None:
        for binding in self.store.list_market_bindings(
            tenant_id=tenant_id, project_id=project_id
        ):
            if binding.business_market_ref == business_market_ref:
                return binding.market_id
        return None

    def _validate_scope(self, campaign: CanonicalCampaign) -> None:
        registry = cached_channel_registry()
        for channel_id in campaign.channel_ids:
            try:
                assert_channel_id_in_registry(channel_id, registry)
            except ChannelValidationError as exc:
                raise IdentityGraphError(str(exc), code="UNKNOWN_CHANNEL") from exc
        if campaign.market_ids:
            self._validate_markets(campaign.tenant_id, campaign.project_id, campaign.market_ids)

    def _validate_markets(
        self, tenant_id: str, project_id: str, market_ids: tuple[str, ...]
    ) -> None:
        unknown: list[str] = []
        for market_id in market_ids:
            try:
                assert_market_id_shape(market_id)
            except (ValueError, InvalidResourceIdentifierError) as exc:
                raise IdentityGraphError(str(exc), code="UNKNOWN_MARKET") from exc
            found = self.store.get_market(
                tenant_id=tenant_id, project_id=project_id, market_id=market_id
            )
            if found is None:
                unknown.append(market_id)
        if unknown:
            raise IdentityGraphError(
                f"Unknown canonical market_id values: {', '.join(unknown)}.",
                code="UNKNOWN_MARKET",
            )

    def _validate_parent(self, campaign: CanonicalCampaign) -> None:
        parent_id = campaign.parent_campaign_id
        if parent_id is None:
            return
        assert_not_self_parent(campaign.campaign_id, parent_id)
        parent = self.store.get_campaign(
            tenant_id=campaign.tenant_id,
            project_id=campaign.project_id,
            campaign_id=parent_id,
        )
        assert_parent_same_project(campaign, parent)
        indexed = {
            item.campaign_id: item
            for item in self.store.list_campaigns(
                tenant_id=campaign.tenant_id, project_id=campaign.project_id
            )
        }
        indexed[campaign.campaign_id] = campaign
        if would_create_cycle(
            campaign_id=campaign.campaign_id, new_parent_id=parent_id, campaigns=indexed
        ):
            raise IdentityGraphError(
                "Campaign hierarchy rejects cycles.",
                code="HIERARCHY_CYCLE",
            )

    def _default_utm_binding(
        self, campaign: CanonicalCampaign, *, actor_id: str
    ) -> CampaignTrackingBinding:
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            campaign_id=campaign.campaign_id,
            parameter_name="utm_id",
            parameter_value=campaign.campaign_id,
            tracking_kind=TrackingKind.PREM3_UTM_ID,
            status=BindingStatus.ACTIVE,
            created_by=actor_id,
        )
        return binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})

    def _write_campaign_edges(
        self, campaign: CanonicalCampaign, tracking: CampaignTrackingBinding
    ) -> None:
        if campaign.parent_campaign_id:
            self._replace_child_edge(campaign)
        for market_id in campaign.market_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=campaign.tenant_id,
                    project_id=campaign.project_id,
                    edge_type=MarketingIdentityEdgeType.CAMPAIGN_TARGETS_MARKET,
                    from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                    from_node_id=campaign.campaign_id,
                    to_node_type=MarketingIdentityNodeType.MARKET,
                    to_node_id=market_id,
                )
            )
        for channel_id in campaign.channel_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=campaign.tenant_id,
                    project_id=campaign.project_id,
                    edge_type=MarketingIdentityEdgeType.CAMPAIGN_USES_CHANNEL,
                    from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                    from_node_id=campaign.campaign_id,
                    to_node_type=MarketingIdentityNodeType.CHANNEL,
                    to_node_id=channel_id,
                )
            )
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=campaign.tenant_id,
                project_id=campaign.project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_TRACKED_BY,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign.campaign_id,
                to_node_type=MarketingIdentityNodeType.CAMPAIGN,
                to_node_id=tracking.tracking_binding_id,
            )
        )

    def _replace_child_edge(self, campaign: CanonicalCampaign) -> None:
        if campaign.parent_campaign_id is None:
            return
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=campaign.tenant_id,
                project_id=campaign.project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_CHILD_OF,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign.campaign_id,
                to_node_type=MarketingIdentityNodeType.CAMPAIGN,
                to_node_id=campaign.parent_campaign_id,
            )
        )

    def _assess_topology(
        self,
        *,
        topology_kind: GA4TopologyKind,
        overlap_policy: SourceOverlapPolicy | None,
        sources: tuple[GA4PropertySourceBinding, ...],
        market_resolution_policy_id: str | None = None,
    ) -> tuple[tuple[str, ...], TopologyStatus, bool, BqLocationClass]:
        issues: list[str] = []
        locations = {item.bq_location for item in sources if item.bq_location}
        missing_location = any(not item.bq_location for item in sources)
        if missing_location or not locations:
            issues.append("BQ_LOCATION_MISSING")
            location_class = BqLocationClass.UNKNOWN_LOCATION
        elif len(locations) > 1:
            issues.append("CROSS_LOCATION_REVIEW_REQUIRED")
            location_class = BqLocationClass.CROSS_LOCATION
        else:
            location_class = BqLocationClass.SAME_LOCATION
        if topology_kind == GA4TopologyKind.MASTER_PLUS_REGIONAL and overlap_policy is None:
            issues.append("OVERLAP_POLICY_REQUIRED")
        declared = {market_id for source in sources for market_id in source.declared_market_ids}
        if (
            topology_kind
            in {GA4TopologyKind.SINGLE_MASTER_PROPERTY, GA4TopologyKind.MASTER_PLUS_REGIONAL}
            and len(declared) > 1
            and market_resolution_policy_id is None
        ):
            issues.append("MARKET_RESOLUTION_REQUIRED")
        if overlap_policy == SourceOverlapPolicy.DEDUPE_REQUIRED:
            issues.append("DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY")
        if overlap_policy == SourceOverlapPolicy.REVIEW_REQUIRED:
            issues.append("OVERLAP_REVIEW_REQUIRED")
        direct_union_ready = (
            location_class == BqLocationClass.SAME_LOCATION
            and overlap_policy
            not in {
                None,
                SourceOverlapPolicy.DEDUPE_REQUIRED,
                SourceOverlapPolicy.REVIEW_REQUIRED,
            }
            and "OVERLAP_POLICY_REQUIRED" not in issues
        )
        if "OVERLAP_POLICY_REQUIRED" in issues or overlap_policy in {
            SourceOverlapPolicy.DEDUPE_REQUIRED,
            SourceOverlapPolicy.REVIEW_REQUIRED,
        }:
            status = TopologyStatus.REVIEW_REQUIRED
        elif issues:
            status = TopologyStatus.PARTIAL
        else:
            status = TopologyStatus.READY
        return tuple(issues), status, direct_union_ready, location_class

"""Typed Marketing Identity Graph contracts. Metadata only; no people, budget, or events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.contracts import utc_now
from app.identity_graph.enums import (
    AudienceRefreshCadence,
    AudienceSourceKind,
    AudienceStatus,
    AudienceType,
    BindingStatus,
    BqLocationClass,
    CampaignIdentitySource,
    CampaignOwnerType,
    CampaignStatus,
    GA4TopologyKind,
    GA4TopologyReadinessState,
    IdentityGraphCapabilityState,
    IdentityGraphComponentState,
    IdentitySourceAuthority,
    MappingMethod,
    MarketCoverageStatus,
    MarketKind,
    MarketMappingMethod,
    MarketResolutionMethod,
    MarketStatus,
    PersonaStatus,
    ResolutionAuthority,
    SourceOverlapPolicy,
    TopologyStatus,
    TrackingImplementationStatus,
    TrackingInstructionProvenance,
    TrackingKind,
)
from app.identity_graph.privacy import reject_identity_graph_payload


class IdentityGraphModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_prohibited(cls, data: Any) -> Any:
        reject_identity_graph_payload(data)
        return data


class CanonicalMarket(IdentityGraphModel):
    market_id: str
    tenant_id: str
    project_id: str
    name: str
    description: str | None = None
    market_kind: MarketKind = MarketKind.CUSTOM
    status: MarketStatus = MarketStatus.ACTIVE
    country_codes: tuple[str, ...] = ()
    region_codes: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = ""


class BusinessMarketBinding(IdentityGraphModel):
    binding_id: str
    tenant_id: str
    project_id: str
    business_profile_snapshot_id: str
    business_market_ref: str
    market_id: str
    mapping_method: MarketMappingMethod
    status: BindingStatus = BindingStatus.CONFIRMED
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class CanonicalPersona(IdentityGraphModel):
    """Durable business archetype. Not a person and not a membership list."""

    persona_id: str
    tenant_id: str
    project_id: str
    name: str
    description: str | None = None
    status: PersonaStatus = PersonaStatus.DRAFT
    market_ids: tuple[str, ...] = ()
    lifecycle_stage_refs: tuple[str, ...] = ()
    business_segment_ref: str | None = None
    business_profile_snapshot_id: str | None = None
    owner_type: CampaignOwnerType | None = None
    owner_ref: str | None = None
    owner_label: str | None = None
    persona_id_authority: IdentitySourceAuthority = IdentitySourceAuthority.PREM3_GENERATED
    market_scope_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED
    definition_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = ""


class CanonicalAudience(IdentityGraphModel):
    """Operational segment definition. Not members, size, or match rate."""

    audience_id: str
    tenant_id: str
    project_id: str
    name: str
    description: str | None = None
    status: AudienceStatus = AudienceStatus.DRAFT
    audience_type: AudienceType
    source_kind: AudienceSourceKind
    source_ref: str | None = None
    market_ids: tuple[str, ...] = ()
    persona_ids: tuple[str, ...] = ()
    parent_audience_id: str | None = None
    definition_summary: str | None = None
    criteria_summary: str | None = None
    effective_start_date: str | None = None
    effective_end_date: str | None = None
    refresh_cadence: AudienceRefreshCadence | None = None
    owner_type: CampaignOwnerType | None = None
    owner_ref: str | None = None
    owner_label: str | None = None
    audience_id_authority: IdentitySourceAuthority = IdentitySourceAuthority.PREM3_GENERATED
    market_scope_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED
    source_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = ""


class AudienceExternalBinding(IdentityGraphModel):
    """IG-03 seam only. Provider IDs never replace audience_id. No CRUD in IG-02A."""

    binding_id: str
    audience_id: str
    provider_id: str
    external_account_id: str | None = None
    external_audience_id: str
    external_audience_name: str | None = None
    mapping_method: MappingMethod = MappingMethod.PROVIDER_ID_EXACT
    status: BindingStatus = BindingStatus.CONFIRMED
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class CanonicalCampaign(IdentityGraphModel):
    campaign_id: str
    tenant_id: str
    project_id: str
    parent_campaign_id: str | None = None
    name: str
    campaign_name_raw: str | None = None
    description: str | None = None
    status: CampaignStatus = CampaignStatus.PLANNED
    market_ids: tuple[str, ...] = ()
    channel_ids: tuple[str, ...] = ()
    persona_ids: tuple[str, ...] = ()
    audience_ids: tuple[str, ...] = ()
    planned_start_date: str | None = None
    planned_end_date: str | None = None
    objective_ref: str | None = None
    objective_label: str | None = None
    owner_type: CampaignOwnerType | None = None
    owner_ref: str | None = None
    owner_label: str | None = None
    campaign_id_authority: IdentitySourceAuthority = IdentitySourceAuthority.PREM3_GENERATED
    market_scope_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED
    tracking_policy_id: str | None = None
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = ""


class CampaignExternalBinding(IdentityGraphModel):
    binding_id: str
    campaign_id: str
    provider_id: str
    external_account_id: str | None = None
    external_campaign_id: str
    external_campaign_name: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    mapping_method: MappingMethod = MappingMethod.PROVIDER_ID_EXACT
    status: BindingStatus = BindingStatus.CONFIRMED
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class CampaignTrackingBinding(IdentityGraphModel):
    tracking_binding_id: str
    campaign_id: str
    parameter_name: str
    parameter_value: str
    tracking_kind: TrackingKind
    status: BindingStatus = BindingStatus.ACTIVE
    effective_start: str | None = None
    effective_end: str | None = None
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = ""


class CampaignTrackingInstructions(IdentityGraphModel):
    campaign_id: str
    tenant_id: str = ""
    project_id: str = ""
    utm_id: str
    parameter_name: str = "utm_id"
    parameter_value: str = ""
    utm_campaign: str | None = None
    recommended_utm_campaign: str | None = None
    query_parameters: dict[str, str] = Field(default_factory=dict)
    implementation_status: TrackingImplementationStatus = (
        TrackingImplementationStatus.NOT_IMPLEMENTED
    )
    generation_provenance: TrackingInstructionProvenance = (
        TrackingInstructionProvenance.GENERATED
    )
    instruction_authority: IdentitySourceAuthority = IdentitySourceAuthority.PREM3_GENERATED
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str = ""


class CampaignCreateResult(IdentityGraphModel):
    campaign: CanonicalCampaign
    tracking: CampaignTrackingBinding
    instructions: CampaignTrackingInstructions


class CampaignLedgerValidationReceipt(IdentityGraphModel):
    tenant_id: str
    project_id: str
    campaign_id: str
    state: IdentityGraphCapabilityState
    campaign_id_valid: bool = False
    project_scoped: bool = False
    markets_known: bool = False
    channels_known: bool = False
    dates_valid: bool = False
    hierarchy_valid: bool = False
    status_valid: bool = False
    tracking_instruction_present: bool = False
    prohibited_fields_absent: bool = True
    issues: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class PersonaLedgerValidationReceipt(IdentityGraphModel):
    tenant_id: str
    project_id: str
    persona_id: str
    state: IdentityGraphCapabilityState
    persona_id_valid: bool = False
    project_scoped: bool = False
    markets_known: bool = False
    snapshot_valid: bool = True
    status_valid: bool = False
    prohibited_fields_absent: bool = True
    issues: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class AudienceLedgerValidationReceipt(IdentityGraphModel):
    tenant_id: str
    project_id: str
    audience_id: str
    state: IdentityGraphCapabilityState
    audience_id_valid: bool = False
    project_scoped: bool = False
    markets_known: bool = False
    personas_known: bool = False
    type_valid: bool = False
    source_valid: bool = False
    dates_valid: bool = False
    hierarchy_valid: bool = False
    status_valid: bool = False
    prohibited_fields_absent: bool = True
    issues: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class CampaignLineage(IdentityGraphModel):
    campaign_id: str
    parent_campaign_id: str | None = None
    ancestors: tuple[str, ...] = ()
    children: tuple[str, ...] = ()


class AudienceLineage(IdentityGraphModel):
    audience_id: str
    parent_audience_id: str | None = None
    ancestors: tuple[str, ...] = ()
    children: tuple[str, ...] = ()


class CampaignIdentityResolution(IdentityGraphModel):
    campaign_id: str | None
    source: CampaignIdentitySource
    status: ResolutionAuthority
    issues: tuple[str, ...] = ()
    campaign_name_raw: str | None = None
    external_campaign_name: str | None = None
    utm_campaign: str | None = None


class GA4PropertySourceBinding(IdentityGraphModel):
    ga4_source_binding_id: str
    tenant_id: str
    project_id: str
    ga4_property_id: str
    bq_project_id: str
    bq_dataset_id: str
    bq_location: str
    stream_ids: tuple[str, ...] = ()
    declared_market_ids: tuple[str, ...] = ()
    coverage_start: str | None = None
    coverage_end: str | None = None
    traffic_source_capability: bool | None = None
    freshness_state: str | None = None
    source_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED
    overlap_policy: SourceOverlapPolicy | None = None
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GA4SourceTopology(IdentityGraphModel):
    topology_id: str
    project_id: str
    tenant_id: str
    source_binding_ids: tuple[str, ...] = ()
    topology_kind: GA4TopologyKind
    market_resolution_policy_id: str | None = None
    overlap_policy: SourceOverlapPolicy | None = None
    status: TopologyStatus = TopologyStatus.PARTIAL
    issues: tuple[str, ...] = ()
    direct_union_ready: bool = False
    location_class: BqLocationClass = BqLocationClass.UNKNOWN_LOCATION
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class GA4MarketCoverage(IdentityGraphModel):
    market_id: str
    source_binding_ids: tuple[str, ...] = ()
    coverage_status: MarketCoverageStatus
    date_start: str | None = None
    date_end: str | None = None
    freshness_state: str | None = None
    resolution_method: MarketResolutionMethod | None = None
    issues: tuple[str, ...] = ()


class GA4TopologyReadinessReceipt(IdentityGraphModel):
    tenant_id: str
    project_id: str
    topology_id: str | None
    state: GA4TopologyReadinessState
    location_class: BqLocationClass = BqLocationClass.UNKNOWN_LOCATION
    coverage: tuple[GA4MarketCoverage, ...] = ()
    issues: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class MarketResolutionPolicy(IdentityGraphModel):
    policy_id: str
    tenant_id: str
    project_id: str
    allowed_methods: tuple[MarketResolutionMethod, ...]
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class MarketResolutionEvidence(IdentityGraphModel):
    market_id: str | None
    method: MarketResolutionMethod
    source_ref: str
    rule_ref: str | None = None
    authority: ResolutionAuthority
    issues: tuple[str, ...] = ()


class GA4TopologyDiscoveryResult(IdentityGraphModel):
    """Data Foundation discovery consumed by Identity Graph. No invented READY state."""

    project_id: str
    tenant_id: str
    discovered_source_binding_ids: tuple[str, ...] = ()
    topology_kind: GA4TopologyKind | None = None
    bq_locations: tuple[str, ...] = ()
    location_class: BqLocationClass = BqLocationClass.UNKNOWN_LOCATION
    coverage_notes: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class MTAIdentityTouchpointRefs(IdentityGraphModel):
    """M5-03 handoff refs. Do not mutate mta_touchpoints in IG-00."""

    campaign_id: str | None = None
    parent_campaign_id: str | None = None
    market_id: str
    campaign_identity_source: CampaignIdentitySource
    market_resolution_method: MarketResolutionMethod
    ga4_source_binding_id: str | None = None


class IdentityGraphOverview(IdentityGraphModel):
    tenant_id: str
    project_id: str
    capability_state: IdentityGraphCapabilityState
    campaign_ledger_state: IdentityGraphCapabilityState = (
        IdentityGraphCapabilityState.NOT_CONFIGURED
    )
    persona_ledger_state: IdentityGraphCapabilityState = (
        IdentityGraphCapabilityState.NOT_CONFIGURED
    )
    audience_ledger_state: IdentityGraphCapabilityState = (
        IdentityGraphCapabilityState.NOT_CONFIGURED
    )
    component_states: tuple[IdentityGraphComponentState, ...] = ()
    campaign_count: int = 0
    persona_count: int = 0
    audience_count: int = 0
    source_count: int = 0
    mapping_count: int = 0
    issues: tuple[str, ...] = ()


class ObservedCampaignSignals(IdentityGraphModel):
    utm_id: str | None = None
    utm_campaign: str | None = None
    provider_id: str | None = None
    external_account_id: str | None = None
    external_campaign_id: str | None = None
    external_campaign_name: str | None = None
    custom_parameter_name: str | None = None
    custom_parameter_value: str | None = None
    user_confirmed_campaign_id: str | None = None
    fuzzy_name: str | None = None

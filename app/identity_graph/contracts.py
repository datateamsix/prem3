"""Typed Marketing Identity Graph contracts. Metadata only; no people, budget, or events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.contracts import utc_now
from app.identity_graph.enums import (
    BindingStatus,
    CampaignIdentitySource,
    CampaignStatus,
    GA4TopologyKind,
    IdentityGraphCapabilityState,
    IdentityGraphComponentState,
    IdentitySourceAuthority,
    MappingMethod,
    MarketResolutionMethod,
    ResolutionAuthority,
    SourceOverlapPolicy,
    TopologyStatus,
    TrackingImplementationStatus,
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
    start_date: str | None = None
    end_date: str | None = None
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
    utm_id: str
    utm_campaign: str | None = None
    query_parameters: dict[str, str] = Field(default_factory=dict)
    implementation_status: TrackingImplementationStatus = TrackingImplementationStatus.GENERATED


class CampaignCreateResult(IdentityGraphModel):
    campaign: CanonicalCampaign
    tracking: CampaignTrackingBinding
    instructions: CampaignTrackingInstructions


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
    """IG-01 / Data Foundation seam. Identity Graph does not discover GA4 itself."""

    project_id: str
    discovered_source_binding_ids: tuple[str, ...] = ()
    topology_kind: GA4TopologyKind | None = None
    bq_locations: tuple[str, ...] = ()
    coverage_notes: tuple[str, ...] = ()


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
    component_states: tuple[IdentityGraphComponentState, ...] = ()
    campaign_count: int = 0
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

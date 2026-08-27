"""Presentation-safe Marketing Identity Graph API contracts."""

from __future__ import annotations

from app.service.models import ApiModel


class CreateIdentityGraphCampaignRequest(ApiModel):
    name: str
    description: str | None = None
    status: str | None = None
    market_ids: list[str] = []
    channel_ids: list[str] = []
    parent_campaign_id: str | None = None
    planned_start_date: str | None = None
    planned_end_date: str | None = None
    utm_campaign: str | None = None
    owner_type: str | None = None
    owner_ref: str | None = None
    owner_label: str | None = None
    objective_ref: str | None = None
    objective_label: str | None = None
    persona_ids: list[str] = []
    audience_ids: list[str] = []


class PatchIdentityGraphCampaignRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    market_ids: list[str] | None = None
    channel_ids: list[str] | None = None
    parent_campaign_id: str | None = None
    planned_start_date: str | None = None
    planned_end_date: str | None = None
    utm_campaign: str | None = None
    owner_type: str | None = None
    owner_ref: str | None = None
    owner_label: str | None = None
    objective_ref: str | None = None
    objective_label: str | None = None
    persona_ids: list[str] | None = None
    audience_ids: list[str] | None = None


class CreateIdentityGraphPersonaRequest(ApiModel):
    name: str
    description: str | None = None
    status: str | None = None
    market_ids: list[str] = []
    lifecycle_stage_refs: list[str] = []
    business_segment_ref: str | None = None
    business_profile_snapshot_id: str | None = None
    owner_type: str | None = None
    owner_ref: str | None = None
    owner_label: str | None = None


class PatchIdentityGraphPersonaRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    market_ids: list[str] | None = None
    lifecycle_stage_refs: list[str] | None = None
    business_segment_ref: str | None = None
    business_profile_snapshot_id: str | None = None
    owner_type: str | None = None
    owner_ref: str | None = None
    owner_label: str | None = None


class CreateIdentityGraphAudienceRequest(ApiModel):
    name: str
    audience_type: str
    source_kind: str
    description: str | None = None
    status: str | None = None
    source_ref: str | None = None
    market_ids: list[str] = []
    persona_ids: list[str] = []
    parent_audience_id: str | None = None
    definition_summary: str | None = None
    criteria_summary: str | None = None
    effective_start_date: str | None = None
    effective_end_date: str | None = None
    refresh_cadence: str | None = None
    owner_type: str | None = None
    owner_ref: str | None = None
    owner_label: str | None = None


class PatchIdentityGraphAudienceRequest(ApiModel):
    name: str | None = None
    audience_type: str | None = None
    source_kind: str | None = None
    description: str | None = None
    status: str | None = None
    source_ref: str | None = None
    market_ids: list[str] | None = None
    persona_ids: list[str] | None = None
    parent_audience_id: str | None = None
    definition_summary: str | None = None
    criteria_summary: str | None = None
    effective_start_date: str | None = None
    effective_end_date: str | None = None
    refresh_cadence: str | None = None
    owner_type: str | None = None
    owner_ref: str | None = None
    owner_label: str | None = None


class CreateIdentityGraphMarketRequest(ApiModel):
    name: str
    description: str | None = None
    market_kind: str | None = None
    country_codes: list[str] = []
    region_codes: list[str] = []


class CreateIdentityGraphSourceRequest(ApiModel):
    ga4_property_id: str
    bq_project_id: str
    bq_dataset_id: str
    bq_location: str = ""
    stream_ids: list[str] = []
    declared_market_ids: list[str] = []
    coverage_start: str | None = None
    coverage_end: str | None = None
    traffic_source_capability: bool | None = None
    freshness_state: str | None = None
    overlap_policy: str | None = None
    topology_kind: str | None = None


class DiscoverGa4SourceTable(ApiModel):
    bq_project_id: str
    bq_dataset_id: str
    bq_location: str | None = None
    ga4_property_id: str | None = None
    coverage_start: str | None = None
    coverage_end: str | None = None
    traffic_source_capability: str | None = None
    freshness_state: str | None = None


class DiscoverIdentityGraphSourcesRequest(ApiModel):
    tables: list[DiscoverGa4SourceTable] = []


class CreateIdentityGraphCampaignBindingRequest(ApiModel):
    provider_id: str
    external_campaign_id: str
    external_account_id: str | None = None
    external_campaign_name: str | None = None
    mapping_method: str | None = None
    status: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    source_ref: str | None = None
    external_parent_id: str | None = None
    external_campaign_status: str | None = None


class PatchIdentityGraphCampaignBindingRequest(ApiModel):
    external_campaign_name: str | None = None
    external_campaign_status: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    status: str | None = None
    source_ref: str | None = None


class CreateIdentityGraphAudienceBindingRequest(ApiModel):
    provider_id: str
    external_audience_id: str
    external_account_id: str | None = None
    external_audience_name: str | None = None
    audience_implementation_type: str | None = None
    mapping_method: str | None = None
    status: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    source_ref: str | None = None


class PatchIdentityGraphAudienceBindingRequest(ApiModel):
    external_audience_name: str | None = None
    audience_implementation_type: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    status: str | None = None
    source_ref: str | None = None


class CreateIdentityGraphTrackingBindingRequest(ApiModel):
    tracking_kind: str
    parameter_name: str
    parameter_value: str
    status: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None


class ObserveTrackingRequest(ApiModel):
    source_ref: str
    source_kind: str
    observed_at: str
    identifier_kind: str
    parameter_value: str
    parameter_name: str | None = None
    observation_window_start: str | None = None
    observation_window_end: str | None = None
    external_provider_id: str | None = None
    external_account_id: str | None = None
    external_campaign_id: str | None = None
    candidate_campaign_id: str | None = None


class ResolveTrackingRequest(ApiModel):
    observation_id: str | None = None
    utm_id: str | None = None
    utm_campaign: str | None = None
    provider_id: str | None = None
    external_account_id: str | None = None
    external_campaign_id: str | None = None
    custom_parameter_name: str | None = None
    custom_parameter_value: str | None = None
    user_confirmed_campaign_id: str | None = None
    fuzzy_name: str | None = None
    observed_at: str | None = None


class VerifyTrackingRequest(ApiModel):
    campaign_id: str
    observation_id: str | None = None

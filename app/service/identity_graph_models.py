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
    start_date: str | None = None
    end_date: str | None = None
    utm_campaign: str | None = None


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

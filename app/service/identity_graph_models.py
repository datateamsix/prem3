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

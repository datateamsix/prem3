"""Presentation contracts for MTA APIs."""

from __future__ import annotations

from pydantic import Field

from app.service.models import ApiModel


class MTAOverviewNextActionView(ApiModel):
    action_type: str
    statement: str
    owner: str = "server"
    blocking: bool = False


class MTAOverviewResponse(ApiModel):
    project_id: str
    cycle_id: str
    track_id: str | None = None
    domain_stage: str
    readiness_state: str
    foundation_ready: bool
    conversion_event: str | None = None
    conversion_period_start: str | None = None
    conversion_period_end: str | None = None
    lookback_window_days: int | None = None
    ga4_dataset_id: str | None = None
    ga4_property_id: str | None = None
    identity_strategy: str | None = None
    user_pseudo_id_coverage: float | None = None
    user_id_coverage: float | None = None
    channel_grouping_version: str | None = None
    attribution_models: list[str] = Field(default_factory=list)
    latest_result_state: str | None = None
    settlement_policy: str | None = None
    epistemic_label: str = "Observable journey attribution"
    next_action: MTAOverviewNextActionView
    attention: list[str] = Field(default_factory=list)
    acceptance_computed_by_server: bool = True


class MTAReadinessResponse(ApiModel):
    receipt_id: str
    state: str
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str
    ga4_dataset_id: str | None = None
    conversion_event: str | None = None


class EvaluateMTAReadinessRequest(ApiModel):
    ga4_dataset_exists: bool = False
    daily_shards_continuous: bool = True
    key_event_present: bool = False
    conversion_volume_ok: bool = False
    channel_grouping_approved: bool = False
    unmapped_share_ok: bool = True
    uses_intraday_for_canonical: bool = False
    lookback_covered: bool = False
    user_pseudo_id_coverage: float | None = None

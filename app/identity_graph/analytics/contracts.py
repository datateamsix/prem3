"""IG-04 analytical-plane contracts. Control-plane metadata only; row schemas are not Firestore."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.contracts import utc_now
from app.identity_graph.contracts import IdentityGraphModel
from app.identity_graph.enums import (
    AnalyticalArtifactKind,
    AnalyticalCompilationPhase,
    AnalyticalCompilationStatus,
    BindingStatus,
    CampaignIdentitySource,
    ChannelResolutionMethod,
    CrossLocationCompileStatus,
    MarketResolutionMethod,
    OverlapCompileStatus,
    RowResolutionStatus,
    SettlementCompileStatus,
    UnifiedAnalyticsReadinessState,
)
from app.modeling.mta.contracts import (
    DirectTreatmentPolicy,
    GA4SettlementPolicy,
    IdentityStrategy,
    SessionTrafficSourcePolicy,
)

UNIFIED_ANALYTICS_DATASET = "prem3_modeling"


class ApprovedSourceMediumBinding(IdentityGraphModel):
    """Exact approved source/medium → Channel Registry id. Not name-fuzzy."""

    source: str
    medium: str
    channel_id: str
    status: BindingStatus = BindingStatus.APPROVED


class AnalyticalSourceSelection(IdentityGraphModel):
    tenant_id: str
    project_id: str
    selected_source_binding_ids: tuple[str, ...]
    period_start: str
    period_end: str
    session_traffic_source_policy: SessionTrafficSourcePolicy = (
        SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1
    )
    settlement_policy: GA4SettlementPolicy = GA4SettlementPolicy.DAILY_SETTLED
    identity_strategy: IdentityStrategy = IdentityStrategy.PSEUDO_ID_ONLY
    direct_treatment_policy: DirectTreatmentPolicy = DirectTreatmentPolicy.KEEP_DIRECT
    campaign_slice_required: bool = False
    approved_source_medium_bindings: tuple[ApprovedSourceMediumBinding, ...] = ()
    destination_dataset: str = UNIFIED_ANALYTICS_DATASET
    fingerprint: str = ""


class AnalyticalSessionSeed(IdentityGraphModel):
    """In-memory adapter input. Hashed subject_key only; never user_pseudo_id / user_id."""

    ga4_source_binding_id: str
    ga4_property_id: str
    ga_session_id: str
    subject_key: str
    session_start_ts: str
    source: str | None = None
    medium: str | None = None
    campaign_name: str | None = None
    utm_id: str | None = None
    external_campaign_id: str | None = None
    provider_id: str | None = None
    external_account_id: str | None = None
    geo_country: str | None = None
    stream_id: str | None = None
    hostname: str | None = None
    key_event: bool = False
    audience_provider_id: str | None = None
    audience_external_id: str | None = None
    table_kind: str = "events_daily"


class MarketIdentityResolution(IdentityGraphModel):
    market_id: str | None
    method: MarketResolutionMethod
    status: RowResolutionStatus
    source_ref: str
    geo_country: str | None = None
    issues: tuple[str, ...] = ()
    resolved_count: int = 0
    unresolved_count: int = 0
    review_required_count: int = 0
    denominator: int = 0


class ChannelIdentityResolution(IdentityGraphModel):
    channel_id: str | None
    channel_family_id: str | None = None
    provider_id: str | None = None
    method: ChannelResolutionMethod
    status: RowResolutionStatus
    issues: tuple[str, ...] = ()


class UnifiedSessionRow(IdentityGraphModel):
    """BQ session-grain schema. Not stored in Firestore."""

    session_id: str
    ga4_property_id: str
    ga4_source_binding_id: str
    source: str | None = None
    medium: str | None = None
    campaign_name: str | None = None
    market_id: str | None = None
    market_status: RowResolutionStatus = RowResolutionStatus.UNRESOLVED
    market_method: MarketResolutionMethod = MarketResolutionMethod.UNRESOLVED
    channel_id: str | None = None
    channel_family_id: str | None = None
    channel_status: RowResolutionStatus = RowResolutionStatus.UNRESOLVED
    channel_method: ChannelResolutionMethod = ChannelResolutionMethod.UNRESOLVED
    campaign_id: str | None = None
    campaign_status: RowResolutionStatus = RowResolutionStatus.UNRESOLVED
    campaign_identity_source: CampaignIdentitySource = CampaignIdentitySource.UNRESOLVED
    parent_campaign_id: str | None = None
    audience_id: str | None = None
    audience_status: RowResolutionStatus = RowResolutionStatus.NOT_APPLICABLE
    provider_id: str | None = None
    session_start_ts: str
    key_event: bool = False
    issues: tuple[str, ...] = ()


class MtaTouchpointRow(IdentityGraphModel):
    """MTA-compatible touchpoint grain. No attribution credit."""

    session_id: str
    touchpoint_order: int
    ga4_property_id: str
    ga4_source_binding_id: str
    market_id: str | None = None
    channel_id: str | None = None
    campaign_id: str | None = None
    parent_campaign_id: str | None = None
    audience_id: str | None = None
    provider_id: str | None = None
    session_start_ts: str
    key_event: bool = False
    issues: tuple[str, ...] = ()


class MtaJourneyRow(IdentityGraphModel):
    """MTA-compatible journey grain. journey_id is project-scoped, not a person ID."""

    journey_id: str
    session_ids: tuple[str, ...]
    market_ids: tuple[str, ...] = ()
    channel_ids: tuple[str, ...] = ()
    campaign_ids: tuple[str, ...] = ()
    multi_market: bool = False
    key_event_count: int = 0
    touchpoint_count: int = 0
    issues: tuple[str, ...] = ()


class AnalyticalArtifactRef(IdentityGraphModel):
    artifact_id: str
    compilation_id: str
    tenant_id: str
    project_id: str
    kind: AnalyticalArtifactKind
    dataset_id: str = UNIFIED_ANALYTICS_DATASET
    table_name: str
    schema_fingerprint: str = ""
    row_count: int = 0
    current_pointer: bool = False
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class UnifiedAnalyticsCompilation(IdentityGraphModel):
    compilation_id: str
    tenant_id: str
    project_id: str
    topology_id: str | None = None
    topology_fingerprint: str = ""
    selection_fingerprint: str = ""
    sql_fingerprint: str = ""
    identity_rules_fingerprint: str = ""
    phase: AnalyticalCompilationPhase
    status: AnalyticalCompilationStatus
    selected_source_binding_ids: tuple[str, ...] = ()
    destination_dataset: str = UNIFIED_ANALYTICS_DATASET
    artifact_refs: tuple[AnalyticalArtifactRef, ...] = ()
    receipt_id: str | None = None
    issues: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UnifiedAnalyticsReadinessReceipt(IdentityGraphModel):
    receipt_id: str
    tenant_id: str
    project_id: str
    compilation_id: str | None = None
    state: UnifiedAnalyticsReadinessState
    session_count: int = 0
    session_denominator: int = 0
    touchpoint_count: int = 0
    journey_count: int = 0
    markets_resolved: int = 0
    markets_unresolved: int = 0
    channels_resolved: int = 0
    channels_unresolved: int = 0
    campaigns_resolved: int = 0
    campaigns_unresolved: int = 0
    campaigns_review_required: int = 0
    cross_location_status: CrossLocationCompileStatus = (
        CrossLocationCompileStatus.UNKNOWN_LOCATION
    )
    overlap_status: OverlapCompileStatus = OverlapCompileStatus.NOT_EVALUATED
    settlement_status: SettlementCompileStatus = SettlementCompileStatus.UNKNOWN
    artifact_refs: tuple[AnalyticalArtifactRef, ...] = ()
    issues: tuple[str, ...] = ()
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class M5_03AnalyticalHandoff(IdentityGraphModel):
    """Handoff for M5-03. Does not emit MTA_RESULT_READY."""

    compilation_id: str | None = None
    topology_id: str | None = None
    topology_fingerprint: str = ""
    identity_rules_fingerprint: str = ""
    sql_fingerprint: str = ""
    artifact_refs: tuple[AnalyticalArtifactRef, ...] = ()
    available_market_ids: tuple[str, ...] = ()
    available_channel_ids: tuple[str, ...] = ()
    available_campaign_ids: tuple[str, ...] = ()
    session_count: int = 0
    touchpoint_count: int = 0
    journey_count: int = 0
    issues: tuple[str, ...] = ()
    mta_result_ready: bool = False


class UnifiedAnalyticsOverview(IdentityGraphModel):
    tenant_id: str
    project_id: str
    compilation_id: str | None = None
    status: UnifiedAnalyticsReadinessState
    receipt_id: str | None = None
    artifact_refs: tuple[AnalyticalArtifactRef, ...] = ()
    issue_summary: tuple[str, ...] = ()
    fingerprint: str = ""
    destination_dataset: str = UNIFIED_ANALYTICS_DATASET
    topology_id: str | None = None

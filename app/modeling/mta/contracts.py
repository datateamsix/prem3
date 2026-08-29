"""Immutable MTA contracts. Observable journey credit — not causal incrementality."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import utc_now
from app.modeling.mta.states import MTATrackStage


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GA4SettlementPolicy(StrEnum):
    DAILY_SETTLED = "DAILY_SETTLED"
    PREVIEW_INTRADAY = "PREVIEW_INTRADAY"


class IdentityStrategy(StrEnum):
    PSEUDO_ID_ONLY = "PSEUDO_ID_ONLY"
    USER_ID_PREFERRED_WITH_PSEUDO_FALLBACK = "USER_ID_PREFERRED_WITH_PSEUDO_FALLBACK"
    USER_ID_ONLY = "USER_ID_ONLY"


class SessionizationPolicy(StrEnum):
    GA4_SESSION_ID_V1 = "GA4_SESSION_ID_V1"
    CUSTOM_INACTIVITY_V1 = "CUSTOM_INACTIVITY_V1"


class SessionTrafficSourcePolicy(StrEnum):
    GA4_SESSION_LAST_CLICK_V1 = "GA4_SESSION_LAST_CLICK_V1"
    FIRST_VALID_COLLECTED_SOURCE_V1 = "FIRST_VALID_COLLECTED_SOURCE_V1"
    CUSTOM_APPROVED_V1 = "CUSTOM_APPROVED_V1"


class DirectTreatmentPolicy(StrEnum):
    KEEP_DIRECT = "KEEP_DIRECT"
    LAST_NON_DIRECT_MODEL_ONLY = "LAST_NON_DIRECT_MODEL_ONLY"
    EXCLUDE_DIRECT_FROM_SELECTED_MODELS = "EXCLUDE_DIRECT_FROM_SELECTED_MODELS"
    CUSTOM = "CUSTOM"


class ConversionValueStrategy(StrEnum):
    NONE = "NONE"
    EVENT_VALUE = "EVENT_VALUE"
    FIXED_UNIT = "FIXED_UNIT"


class MultipleConversionsPolicy(StrEnum):
    ALLOW_REPEATED = "ALLOW_REPEATED"
    FIRST_ONLY = "FIRST_ONLY"
    LAST_ONLY = "LAST_ONLY"


class MTAReadinessState(StrEnum):
    NOT_READY = "NOT_READY"
    MTA_INPUT_READY = "MTA_INPUT_READY"


class MTAQualityCheckId(StrEnum):
    GA4_SOURCE_EXISTS = "GA4_SOURCE_EXISTS"
    DAILY_SHARDS_CONTINUOUS = "DAILY_SHARDS_CONTINUOUS"
    SOURCE_SETTLED = "SOURCE_SETTLED"
    KEY_EVENT_EXISTS = "KEY_EVENT_EXISTS"
    CONVERSION_VOLUME = "CONVERSION_VOLUME"
    CONVERSION_VALUE_COVERAGE = "CONVERSION_VALUE_COVERAGE"
    USER_PSEUDO_ID_COVERAGE = "USER_PSEUDO_ID_COVERAGE"
    USER_ID_COVERAGE = "USER_ID_COVERAGE"
    GA_SESSION_ID_COVERAGE = "GA_SESSION_ID_COVERAGE"
    TRAFFIC_SOURCE_COVERAGE = "TRAFFIC_SOURCE_COVERAGE"
    UNMAPPED_CHANNEL_RATE = "UNMAPPED_CHANNEL_RATE"
    DIRECT_SHARE = "DIRECT_SHARE"
    DUPLICATE_TRANSACTION_RATE = "DUPLICATE_TRANSACTION_RATE"
    TIMESTAMP_ORDERING = "TIMESTAMP_ORDERING"
    LOOKBACK_COVERAGE = "LOOKBACK_COVERAGE"
    PATH_LENGTH_DISTRIBUTION = "PATH_LENGTH_DISTRIBUTION"
    NONCONVERTING_PATH_COVERAGE = "NONCONVERTING_PATH_COVERAGE"
    CONSENT_OBSERVABILITY = "CONSENT_OBSERVABILITY"
    LATE_SHARD_POLICY = "LATE_SHARD_POLICY"


class QualityCheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    NOT_EVALUATED = "NOT_EVALUATED"


class AttributionModelId(StrEnum):
    FIRST_TOUCH = "FIRST_TOUCH"
    LAST_TOUCH = "LAST_TOUCH"
    LAST_NON_DIRECT = "LAST_NON_DIRECT"
    LINEAR = "LINEAR"
    TIME_DECAY = "TIME_DECAY"
    POSITION_BASED = "POSITION_BASED"
    MARKOV = "MARKOV"
    SHAPLEY = "SHAPLEY"


class ShapleyPreflightState(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WITH_TRUNCATION = "ELIGIBLE_WITH_TRUNCATION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"


class JourneyDefinition(FrozenModel):
    conversion_closes_journey: bool = True
    inactivity_break_hours: int | None = None
    multiple_conversions_policy: MultipleConversionsPolicy = (
        MultipleConversionsPolicy.ALLOW_REPEATED
    )
    include_nonconverting_paths: bool = False
    lookback_window_days: int = 30
    maximum_touchpoints: int | None = None
    deduplicate_consecutive_same_channel: bool = False
    policy_version: str = "journey_def_v1"


class MTATrackConfig(FrozenModel):
    ga4_property_id: str | None = None
    ga4_dataset_id: str | None = None
    key_event_name: str | None = None
    conversion_period_start: str | None = None
    conversion_period_end: str | None = None
    lookback_window_days: int | None = 30
    identity_strategy: IdentityStrategy | None = IdentityStrategy.PSEUDO_ID_ONLY
    sessionization_policy: SessionizationPolicy | None = SessionizationPolicy.GA4_SESSION_ID_V1
    session_traffic_source_policy: SessionTrafficSourcePolicy | None = None
    settlement_policy: GA4SettlementPolicy = GA4SettlementPolicy.DAILY_SETTLED
    direct_treatment: DirectTreatmentPolicy | None = DirectTreatmentPolicy.KEEP_DIRECT
    channel_grouping_version: str | None = None
    conversion_value_strategy: ConversionValueStrategy | None = ConversionValueStrategy.NONE
    include_nonconverting_paths: bool | None = False
    attribution_models: tuple[AttributionModelId, ...] = ()
    journey_definition: JourneyDefinition | None = None
    domain_stage: MTATrackStage = MTATrackStage.AVAILABLE_TO_CONFIGURE


class GA4SourceBinding(FrozenModel):
    gcp_project_id: str
    dataset_id: str
    property_id: str | None = None
    daily_shard_prefix: str = "events_"
    intraday_shard_prefix: str = "events_intraday_"
    earliest_shard_date: str | None = None
    latest_shard_date: str | None = None
    settled_through_date: str | None = None
    has_session_traffic_source_last_click: bool = False
    has_collected_traffic_source: bool = False
    event_names_sample: tuple[str, ...] = ()
    schema_fields_sample: tuple[str, ...] = ()
    discovery_fingerprint: str
    discovered_at: datetime = Field(default_factory=utc_now)


class GA4DiscoveryResult(FrozenModel):
    bindings: tuple[GA4SourceBinding, ...] = ()
    selected: GA4SourceBinding | None = None
    notes: tuple[str, ...] = ()


class MTAQualityCheckResult(FrozenModel):
    check_id: MTAQualityCheckId
    status: QualityCheckStatus
    detail: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class MTAInputContract(FrozenModel):
    input_contract_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    ga4_dataset_id: str
    ga4_property_id: str | None = None
    source_schema_version: str
    settlement_policy: GA4SettlementPolicy
    conversion_event: str
    conversion_period_start: str
    conversion_period_end: str
    lookback_window_days: int
    identity_strategy: IdentityStrategy
    sessionization_policy: SessionizationPolicy
    traffic_source_policy: SessionTrafficSourcePolicy
    traffic_source_policy_fingerprint: str
    direct_treatment_policy: DirectTreatmentPolicy
    channel_grouping_version: str
    conversion_value_strategy: ConversionValueStrategy
    include_nonconverting_paths: bool
    journey_definition: JourneyDefinition
    touchpoint_table: str | None = None
    journey_table: str | None = None
    path_frequency_table: str | None = None
    quality_receipt_id: str | None = None
    attribution_models: tuple[AttributionModelId, ...] = ()
    fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)


class MTAReadinessReceipt(FrozenModel):
    receipt_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    state: MTAReadinessState
    checks: tuple[MTAQualityCheckResult, ...] = ()
    input_contract_fingerprint: str | None = None
    ga4_dataset_id: str | None = None
    conversion_event: str | None = None
    blocking_failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    generated_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class MTAChannelGroupingRule(FrozenModel):
    rule_id: str
    priority: int
    source_pattern: str | None = None
    medium_pattern: str | None = None
    campaign_pattern: str | None = None
    canonical_channel_id: str
    description: str | None = None


class MTAChannelGrouping(FrozenModel):
    channel_grouping_id: str
    version: str
    business_profile_snapshot_id: str | None = None
    source_dimensions: tuple[str, ...] = ("source", "medium", "campaign")
    rules: tuple[MTAChannelGroupingRule, ...] = ()
    fallback_channel_id: str = "Unmapped"
    direct_channel_id: str = "Direct"
    created_by: str
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None
    fingerprint: str
    routine_name: str
    sql_fingerprint: str | None = None


class MTAProvisionedAsset(FrozenModel):
    asset_name: str
    asset_kind: str
    enabled: bool = True
    required_models: tuple[AttributionModelId, ...] = ()
    description: str | None = None


class MTAProvisioningPlan(FrozenModel):
    plan_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    gcp_project_id: str
    dataset_id: str = "prem3_modeling"
    channel_grouping_version: str
    assets: tuple[MTAProvisionedAsset, ...] = ()
    channel_grouping_routine: str
    fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)


class MTAProvisioningReceipt(FrozenModel):
    receipt_id: str
    plan_id: str
    plan_fingerprint: str
    tenant_id: str
    project_id: str
    created: tuple[str, ...] = ()
    reused: tuple[str, ...] = ()
    untouched: tuple[str, ...] = ()
    verified: bool = False
    generated_at: datetime = Field(default_factory=utc_now)


class MTAAttributionModelSpec(FrozenModel):
    model_id: AttributionModelId
    display_name: str
    assumption: str
    is_heuristic: bool
    requires_path_order: bool = False
    compute_bounded: bool = False


class ShapleyPreflight(FrozenModel):
    state: ShapleyPreflightState
    distinct_channel_count: int
    max_path_length: int | None = None
    p95_path_length: float | None = None
    configured_size: int | None = None
    order_aware: bool = False
    estimated_combinatorial_work: int | None = None
    grouped_path_count: int | None = None
    compute_class: str | None = None
    truncation_size: int | None = None
    notes: tuple[str, ...] = ()
    fingerprint: str


class MTAOverviewNextAction(FrozenModel):
    action_type: str
    statement: str
    owner: str = "server"
    blocking: bool = False


class MTAOverviewReadModel(FrozenModel):
    """Landing read model — not a KPI dashboard."""

    project_id: str
    cycle_id: str
    track_id: str | None = None
    domain_stage: MTATrackStage
    readiness_state: MTAReadinessState
    foundation_ready: bool
    conversion_event: str | None = None
    conversion_period_start: str | None = None
    conversion_period_end: str | None = None
    lookback_window_days: int | None = None
    ga4_dataset_id: str | None = None
    ga4_property_id: str | None = None
    identity_strategy: IdentityStrategy | None = None
    user_pseudo_id_coverage: float | None = None
    user_id_coverage: float | None = None
    channel_grouping_version: str | None = None
    attribution_models: tuple[str, ...] = ()
    latest_result_state: str | None = None
    latest_result_snapshot_id: str | None = None
    current_result_snapshot_id: str | None = None
    models_available: tuple[str, ...] = ()
    top_verified_findings: tuple[str, ...] = ()
    channels_needing_review: tuple[str, ...] = ()
    model_sensitivity_summary: str | None = None
    observability_status: str | None = None
    settlement_policy: GA4SettlementPolicy | None = None
    epistemic_label: str = "Observable journey attribution"
    next_action: MTAOverviewNextAction
    attention: tuple[str, ...] = ()
    acceptance_computed_by_server: bool = True

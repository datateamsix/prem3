"""Build fingerprinted MTAInputContract."""

from __future__ import annotations

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import (
    AttributionModelId,
    ConversionValueStrategy,
    DirectTreatmentPolicy,
    GA4SettlementPolicy,
    IdentityStrategy,
    JourneyDefinition,
    MTAInputContract,
    SessionizationPolicy,
    SessionTrafficSourcePolicy,
)
from app.modeling.mta.policies import traffic_source_policy_fingerprint


def build_input_contract(
    *,
    input_contract_id: str,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    track_id: str,
    ga4_dataset_id: str,
    conversion_event: str,
    conversion_period_start: str,
    conversion_period_end: str,
    channel_grouping_version: str,
    ga4_property_id: str | None = None,
    lookback_window_days: int = 30,
    identity_strategy: IdentityStrategy = IdentityStrategy.PSEUDO_ID_ONLY,
    sessionization_policy: SessionizationPolicy = SessionizationPolicy.GA4_SESSION_ID_V1,
    traffic_source_policy: SessionTrafficSourcePolicy = (
        SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1
    ),
    settlement_policy: GA4SettlementPolicy = GA4SettlementPolicy.DAILY_SETTLED,
    direct_treatment_policy: DirectTreatmentPolicy = DirectTreatmentPolicy.KEEP_DIRECT,
    conversion_value_strategy: ConversionValueStrategy = ConversionValueStrategy.NONE,
    include_nonconverting_paths: bool = False,
    journey_definition: JourneyDefinition | None = None,
    attribution_models: tuple[AttributionModelId, ...] = (),
    source_schema_version: str = "ga4_bq_export_v1",
) -> MTAInputContract:
    journey = journey_definition or JourneyDefinition(lookback_window_days=lookback_window_days)
    tsp_fp = traffic_source_policy_fingerprint(traffic_source_policy)
    payload = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "cycle_id": cycle_id,
        "track_id": track_id,
        "ga4_dataset_id": ga4_dataset_id,
        "conversion_event": conversion_event,
        "conversion_period_start": conversion_period_start,
        "conversion_period_end": conversion_period_end,
        "lookback_window_days": lookback_window_days,
        "identity_strategy": identity_strategy.value,
        "sessionization_policy": sessionization_policy.value,
        "traffic_source_policy": traffic_source_policy.value,
        "traffic_source_policy_fingerprint": tsp_fp,
        "settlement_policy": settlement_policy.value,
        "direct_treatment_policy": direct_treatment_policy.value,
        "channel_grouping_version": channel_grouping_version,
        "journey": journey.model_dump(mode="json"),
        "models": [m.value for m in attribution_models],
    }
    return MTAInputContract(
        input_contract_id=input_contract_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=track_id,
        ga4_dataset_id=ga4_dataset_id,
        ga4_property_id=ga4_property_id,
        source_schema_version=source_schema_version,
        settlement_policy=settlement_policy,
        conversion_event=conversion_event,
        conversion_period_start=conversion_period_start,
        conversion_period_end=conversion_period_end,
        lookback_window_days=lookback_window_days,
        identity_strategy=identity_strategy,
        sessionization_policy=sessionization_policy,
        traffic_source_policy=traffic_source_policy,
        traffic_source_policy_fingerprint=tsp_fp,
        direct_treatment_policy=direct_treatment_policy,
        channel_grouping_version=channel_grouping_version,
        conversion_value_strategy=conversion_value_strategy,
        include_nonconverting_paths=include_nonconverting_paths,
        journey_definition=journey,
        attribution_models=attribution_models,
        fingerprint=canonical_fingerprint(payload),
    )

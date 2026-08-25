"""MTA Overview landing assembler — server-owned next actions."""

from __future__ import annotations

from app.modeling.mta.contracts import (
    MTAInputContract,
    MTAOverviewNextAction,
    MTAOverviewReadModel,
    MTAReadinessReceipt,
    MTAReadinessState,
    MTATrackConfig,
)
from app.modeling.mta.states import MTATrackStage


def assemble_mta_overview(
    *,
    project_id: str,
    cycle_id: str,
    track_id: str | None,
    foundation_ready: bool,
    config: MTATrackConfig | None,
    readiness: MTAReadinessReceipt | None,
    contract: MTAInputContract | None = None,
    user_pseudo_id_coverage: float | None = None,
    user_id_coverage: float | None = None,
) -> MTAOverviewReadModel:
    cfg = config or MTATrackConfig()
    readiness_state = (
        readiness.state if readiness is not None else MTAReadinessState.NOT_READY
    )
    stage = cfg.domain_stage
    if not foundation_ready:
        next_action = MTAOverviewNextAction(
            action_type="CONTINUE_DATA_FOUNDATION",
            statement="Complete Data Foundation before configuring MTA.",
            blocking=True,
        )
        stage = MTATrackStage.AVAILABLE_TO_CONFIGURE
    elif readiness_state is MTAReadinessState.MTA_INPUT_READY:
        next_action = MTAOverviewNextAction(
            action_type="OPEN_MTA_MODELS",
            statement="MTA input is ready. Configure attribution models for a future run.",
            blocking=False,
        )
        stage = MTATrackStage.MTA_INPUT_READY
    elif not cfg.ga4_dataset_id:
        next_action = MTAOverviewNextAction(
            action_type="SETUP_MTA",
            statement="Discover and bind a GA4 BigQuery export dataset (analytics_<property_id>).",
            blocking=True,
        )
    elif not cfg.key_event_name:
        next_action = MTAOverviewNextAction(
            action_type="SELECT_MTA_KEY_EVENT",
            statement="Select the conversion/key event this MTA analysis should measure.",
            blocking=True,
        )
    elif not cfg.channel_grouping_version:
        next_action = MTAOverviewNextAction(
            action_type="APPROVE_CHANNEL_GROUPING",
            statement="Approve a versioned channel grouping before MTA_INPUT_READY.",
            blocking=True,
        )
    else:
        next_action = MTAOverviewNextAction(
            action_type="ASSESS_MTA_INPUT",
            statement="Resolve remaining MTA input quality checks.",
            blocking=True,
        )
        stage = MTATrackStage.ASSESSING_INPUT

    attention: list[str] = []
    if readiness is not None:
        attention.extend(readiness.warnings)
        attention.extend(readiness.blocking_failures)

    models = tuple(m.value for m in cfg.attribution_models)
    if contract is not None and contract.attribution_models:
        models = tuple(m.value for m in contract.attribution_models)

    return MTAOverviewReadModel(
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=track_id,
        domain_stage=stage,
        readiness_state=readiness_state,
        foundation_ready=foundation_ready,
        conversion_event=cfg.key_event_name,
        conversion_period_start=cfg.conversion_period_start,
        conversion_period_end=cfg.conversion_period_end,
        lookback_window_days=cfg.lookback_window_days,
        ga4_dataset_id=cfg.ga4_dataset_id,
        ga4_property_id=cfg.ga4_property_id,
        identity_strategy=cfg.identity_strategy,
        user_pseudo_id_coverage=user_pseudo_id_coverage,
        user_id_coverage=user_id_coverage,
        channel_grouping_version=cfg.channel_grouping_version,
        attribution_models=models,
        latest_result_state="NOT_AVAILABLE",
        settlement_policy=cfg.settlement_policy,
        next_action=next_action,
        attention=tuple(attention),
    )

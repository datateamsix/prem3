"""MTA Overview landing assembler — server-owned next actions."""

from __future__ import annotations

from typing import Any

from app.modeling.mta.contracts import (
    MTAInputContract,
    MTAOverviewNextAction,
    MTAOverviewReadModel,
    MTAReadinessReceipt,
    MTAReadinessState,
    MTATrackConfig,
)
from app.modeling.mta.results_contracts import (
    ChannelRoleLabel,
    MTADecisionIntelligenceBrief,
    MTAResultPointers,
    MTAResultsSnapshot,
    ObservabilityStatus,
    SensitivityLabel,
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
    snapshot: MTAResultsSnapshot | None = None,
    pointers: MTAResultPointers | None = None,
    compiled: Any | None = None,
    brief: MTADecisionIntelligenceBrief | None = None,
) -> MTAOverviewReadModel:
    cfg = config or MTATrackConfig()
    readiness_state = readiness.state if readiness is not None else MTAReadinessState.NOT_READY
    stage = cfg.domain_stage
    if not foundation_ready:
        next_action = MTAOverviewNextAction(
            action_type="CONTINUE_DATA_FOUNDATION",
            statement="Complete Data Foundation before configuring MTA.",
            blocking=True,
        )
        stage = MTATrackStage.AVAILABLE_TO_CONFIGURE
    elif snapshot is not None:
        next_action = _results_next_action(snapshot=snapshot, compiled=compiled)
        stage = MTATrackStage.MTA_INPUT_READY
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

    latest_state = "NOT_AVAILABLE"
    latest_id = None if pointers is None else pointers.latest_result_snapshot_id
    current_id = None if pointers is None else pointers.current_result_snapshot_id
    models_available: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    review_channels: tuple[str, ...] = ()
    sensitivity_summary = None
    observability_status = None
    if snapshot is not None:
        latest_state = snapshot.result_status.value
        latest_id = snapshot.result_snapshot_id if latest_id is None else latest_id
        models_available = snapshot.models_completed or models
        observability_status = snapshot.observability_summary.status.value
        if compiled is not None:
            high = [
                s.channel_id
                for s in compiled.sensitivity
                if s.sensitivity_label in (SensitivityLabel.HIGH, SensitivityLabel.VERY_HIGH)
            ]
            if high:
                sensitivity_summary = "HIGH/VERY_HIGH model disagreement for: " + ", ".join(high)
            review_channels = tuple(
                r.channel_id
                for r in compiled.roles
                if ChannelRoleLabel.LOW_OBSERVABILITY in r.labels
                or ChannelRoleLabel.MODEL_SENSITIVE in r.labels
            )
        if brief is not None:
            findings = tuple(f.statement for f in brief.verified_findings[:3])
        if snapshot.observability_summary.status is ObservabilityStatus.LIMITED:
            attention.append("Observability is LIMITED.")

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
        latest_result_state=latest_state,
        latest_result_snapshot_id=latest_id,
        current_result_snapshot_id=current_id,
        models_available=models_available,
        top_verified_findings=findings,
        channels_needing_review=review_channels,
        model_sensitivity_summary=sensitivity_summary,
        observability_status=observability_status,
        settlement_policy=cfg.settlement_policy,
        next_action=next_action,
        attention=tuple(attention),
    )


def _results_next_action(*, snapshot: MTAResultsSnapshot, compiled: Any | None):
    if snapshot.observability_summary.status is ObservabilityStatus.LIMITED:
        return MTAOverviewNextAction(
            action_type="REVIEW_LOW_OBSERVABILITY",
            statement=(
                "Review identity or mapping coverage before treating "
                "channel roles as stable."
            ),
            blocking=False,
        )
    shapley_blocked = (
        compiled is not None
        and compiled.shapley.availability.value in {"NOT_RUN", "BLOCKED_BY_PREFLIGHT"}
        and "SHAPLEY" in snapshot.models_requested
    )
    if shapley_blocked:
        return MTAOverviewNextAction(
            action_type="REVIEW_SHAPLEY_LIMITATION",
            statement=(
                "Shapley was not run; review preflight or configuration "
                "before treating coalitions as complete."
            ),
            blocking=False,
        )
    if compiled is not None and any(
        ChannelRoleLabel.DIRECT_CAPTURE in r.labels for r in compiled.roles
    ):
        return MTAOverviewNextAction(
            action_type="REVIEW_DIRECT_POLICY",
            statement=(
                "Direct shows high closing presence; review Direct treatment "
                "before comparing paid channels."
            ),
            blocking=False,
        )
    if compiled is not None and any(
        s.sensitivity_label in (SensitivityLabel.HIGH, SensitivityLabel.VERY_HIGH)
        for s in compiled.sensitivity
    ):
        return MTAOverviewNextAction(
            action_type="REVIEW_MODEL_SENSITIVITY",
            statement=(
                "Compare attribution models; some channels show material "
                "cross-model disagreement."
            ),
            blocking=False,
        )
    if len(snapshot.models_completed) >= 2:
        return MTAOverviewNextAction(
            action_type="COMPARE_ATTRIBUTION_MODELS",
            statement=(
                "Review model comparison. Filtering displayed models does "
                "not rerun attribution."
            ),
            blocking=False,
        )
    return MTAOverviewNextAction(
        action_type="REVIEW_MTA_RESULTS",
        statement="Review verified MTA result evidence and channel-role intelligence.",
        blocking=False,
    )

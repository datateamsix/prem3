"""Governed realized outcomes. Spend is not a business outcome."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import OutcomeSemanticType, OutcomeSourceAuthority
from app.investment_optimization.errors import (
    OutcomeSourceNotGovernedError,
    OutcomeWindowInvalidError,
)
from app.investment_optimization.ids import new_outcome_observation_id
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import DecisionOutcomeObservation
from app.investment_planning.outcomes.temporal import assert_temporal_order


def pin_outcome_observation(
    *,
    project_id: str,
    investment_decision_ref: str,
    outcome_metric_id: str,
    outcome_unit: str,
    semantic_type: OutcomeSemanticType,
    observation_window_start: datetime,
    observation_window_end: datetime,
    as_of_time: datetime,
    source_authority: OutcomeSourceAuthority,
    source_refs: tuple[str, ...],
    approved_plan_ref: str | None = None,
    measurement_cycle_ref: str | None = None,
    outcome_artifact_ref: str | None = None,
    observed_value: float | None = None,
    supersedes_observation_id: str | None = None,
    decision_as_of_time: datetime | None = None,
) -> DecisionOutcomeObservation:
    if not source_refs:
        raise OutcomeSourceNotGovernedError("A realized outcome requires explicit source refs.")
    if observation_window_end < observation_window_start:
        raise OutcomeWindowInvalidError("Outcome window end precedes window start.")
    if decision_as_of_time is not None:
        assert_temporal_order(
            recommendation_as_of_time=decision_as_of_time,
            decision_as_of_time=decision_as_of_time,
            prediction_evidence_as_of_time=decision_as_of_time,
            realized_outcome_as_of_time=as_of_time,
            observation_window_start=observation_window_start,
            observation_window_end=observation_window_end,
        )
    created = datetime.now(UTC)
    payload = {
        "decision": investment_decision_ref,
        "metric": outcome_metric_id,
        "unit": outcome_unit,
        "semantic": semantic_type.value,
        "window_start": observation_window_start.isoformat(),
        "window_end": observation_window_end.isoformat(),
        "as_of": as_of_time.isoformat(),
        "authority": source_authority.value,
        "sources": list(source_refs),
        "supersedes": supersedes_observation_id or "",
    }
    return DecisionOutcomeObservation(
        decision_outcome_observation_id=new_outcome_observation_id(),
        project_id=project_id,
        investment_decision_ref=investment_decision_ref,
        approved_plan_ref=approved_plan_ref,
        measurement_cycle_ref=measurement_cycle_ref,
        outcome_metric_id=outcome_metric_id,
        outcome_unit=outcome_unit,
        semantic_type=semantic_type,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        as_of_time=as_of_time,
        source_authority=source_authority,
        source_refs=source_refs,
        outcome_artifact_ref=outcome_artifact_ref,
        observed_value=observed_value,
        supersedes_observation_id=supersedes_observation_id,
        observation_fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )

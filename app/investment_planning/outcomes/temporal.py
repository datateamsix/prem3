"""Fail-closed temporal authority. Latest-state substitution is forbidden."""

from __future__ import annotations

from datetime import datetime

from app.investment_optimization.errors import OutcomeEvaluationTemporalBoundaryInvalidError


def assert_temporal_order(
    *,
    recommendation_as_of_time: datetime,
    decision_as_of_time: datetime,
    prediction_evidence_as_of_time: datetime,
    realized_outcome_as_of_time: datetime | None = None,
    observation_window_start: datetime | None = None,
    observation_window_end: datetime | None = None,
) -> None:
    if prediction_evidence_as_of_time > decision_as_of_time:
        raise OutcomeEvaluationTemporalBoundaryInvalidError(
            "Prediction evidence after decision time is future-information leakage."
        )
    if recommendation_as_of_time > decision_as_of_time:
        raise OutcomeEvaluationTemporalBoundaryInvalidError(
            "Recommendation evidence after decision time is invalid."
        )
    if observation_window_start and observation_window_end:
        if observation_window_end < observation_window_start:
            raise OutcomeEvaluationTemporalBoundaryInvalidError(
                "Outcome window end precedes window start."
            )
        if (
            realized_outcome_as_of_time is not None
            and realized_outcome_as_of_time < observation_window_start
        ):
            raise OutcomeEvaluationTemporalBoundaryInvalidError(
                "Outcome evidence timestamp is before the observation window."
            )


def reject_latest_state_substitution() -> None:
    raise OutcomeEvaluationTemporalBoundaryInvalidError(
        "Latest-state substitution is not allowed for historical evaluation."
    )


def reject_future_model_version() -> None:
    raise OutcomeEvaluationTemporalBoundaryInvalidError(
        "A future model version cannot evaluate a past decision."
    )

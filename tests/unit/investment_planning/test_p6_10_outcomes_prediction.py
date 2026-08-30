"""P6-10 observations, temporal safety, and point prediction error."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.investment_optimization.enums import (
    OutcomeSemanticType,
    OutcomeSourceAuthority,
    PredictionErrorClass,
)
from app.investment_optimization.errors import (
    OutcomeEvaluationTemporalBoundaryInvalidError,
    OutcomeSourceNotGovernedError,
    OutcomeUnitMismatchError,
    OutcomeWindowInvalidError,
    SimulationEvidenceNotAvailableError,
)
from app.investment_planning.outcomes.observations import pin_outcome_observation
from app.investment_planning.outcomes.prediction import (
    compute_prediction_error,
    pin_prediction_evidence,
    require_simulation_handoff,
)
from app.investment_planning.outcomes.temporal import (
    assert_temporal_order,
    reject_future_model_version,
    reject_latest_state_substitution,
)
from tests.unit.investment_planning.p6_10_support import PROJECT, now


def _decision_time() -> datetime:
    return now()


def _observation(
    *,
    as_of: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    supersedes: str | None = None,
    sources: tuple[str, ...] = ("bq_p610_kpi",),
    unit: str = "revenue",
    value: float | None = 110.0,
):
    window_start = start or datetime(2026, 4, 1, tzinfo=UTC)
    window_end = end or datetime(2026, 6, 30, tzinfo=UTC)
    return pin_outcome_observation(
        project_id=PROJECT,
        investment_decision_ref="oidec_p610decision000010",
        outcome_metric_id="kpi_revenue",
        outcome_unit=unit,
        semantic_type=OutcomeSemanticType.OBSERVED_REVENUE,
        observation_window_start=window_start,
        observation_window_end=window_end,
        as_of_time=as_of or datetime(2026, 7, 2, tzinfo=UTC),
        source_authority=OutcomeSourceAuthority.GOVERNED_BIGQUERY,
        source_refs=sources,
        observed_value=value,
        supersedes_observation_id=supersedes,
        decision_as_of_time=_decision_time(),
    )


def _evidence(
    *,
    predicted: float | None = 100.0,
    sim_ref: str | None = None,
    unit: str = "revenue",
):
    decision = _decision_time()
    return pin_prediction_evidence(
        project_id=PROJECT,
        predicted_unit=unit,
        recommendation_as_of_time=decision - timedelta(days=1),
        decision_as_of_time=decision,
        prediction_evidence_as_of_time=decision - timedelta(hours=1),
        predicted_value=predicted,
        frontier_selection_ref="osel_p610selection000001",
        simulation_evidence_handoff_ref=sim_ref,
    )


def test_observation_requires_governed_source_refs() -> None:
    with pytest.raises(OutcomeSourceNotGovernedError):
        _observation(sources=())


def test_observation_rejects_inverted_window() -> None:
    start = datetime(2026, 6, 30, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)
    with pytest.raises(OutcomeWindowInvalidError):
        _observation(start=start, end=end)


def test_superseding_observation_does_not_rewrite_v1() -> None:
    first = _observation()
    second = _observation(supersedes=first.decision_outcome_observation_id, value=108.0)
    assert second.supersedes_observation_id == first.decision_outcome_observation_id
    assert first.observed_value == 110.0
    assert first.decision_outcome_observation_id != second.decision_outcome_observation_id


def test_prediction_after_decision_time_is_fail_closed() -> None:
    decision = _decision_time()
    with pytest.raises(OutcomeEvaluationTemporalBoundaryInvalidError):
        pin_prediction_evidence(
            project_id=PROJECT,
            predicted_unit="revenue",
            recommendation_as_of_time=decision,
            decision_as_of_time=decision,
            prediction_evidence_as_of_time=decision + timedelta(minutes=1),
            predicted_value=100.0,
            frontier_selection_ref="osel_p610selection000001",
        )


def test_outcome_before_window_is_fail_closed() -> None:
    with pytest.raises(OutcomeEvaluationTemporalBoundaryInvalidError):
        assert_temporal_order(
            recommendation_as_of_time=_decision_time(),
            decision_as_of_time=_decision_time(),
            prediction_evidence_as_of_time=_decision_time(),
            realized_outcome_as_of_time=datetime(2026, 3, 1, tzinfo=UTC),
            observation_window_start=datetime(2026, 4, 1, tzinfo=UTC),
            observation_window_end=datetime(2026, 6, 30, tzinfo=UTC),
        )


def test_latest_state_and_future_model_are_rejected() -> None:
    with pytest.raises(OutcomeEvaluationTemporalBoundaryInvalidError):
        reject_latest_state_substitution()
    with pytest.raises(OutcomeEvaluationTemporalBoundaryInvalidError):
        reject_future_model_version()


def test_point_prediction_error_without_simulation() -> None:
    evidence = _evidence()
    observation = _observation()
    error = compute_prediction_error(evidence=evidence, observation=observation)
    assert error.signed_error == pytest.approx(10.0)
    assert error.absolute_error == pytest.approx(10.0)
    assert error.percentage_error == pytest.approx(0.1)
    assert error.realized_percentile is None
    assert error.inside_expected_interval is None
    assert "SIMULATION_EVIDENCE_NOT_AVAILABLE" in error.limitations
    assert error.error_class is PredictionErrorClass.WITHIN_EXPECTED_RANGE


def test_core_prediction_is_green_when_handoff_ref_absent() -> None:
    evidence = _evidence(sim_ref=None)
    assert evidence.simulation_evidence_handoff_ref is None
    assert "SIMULATION_EVIDENCE_NOT_AVAILABLE" in evidence.limitations
    error = compute_prediction_error(evidence=evidence, observation=_observation())
    assert error.realized_percentile is None


def test_missing_simulation_is_not_zero_uncertainty() -> None:
    evidence = _evidence()
    with pytest.raises(SimulationEvidenceNotAvailableError, match="not zero uncertainty"):
        require_simulation_handoff(evidence)


def test_unit_mismatch_is_fail_closed() -> None:
    with pytest.raises(OutcomeUnitMismatchError):
        compute_prediction_error(
            evidence=_evidence(unit="revenue"),
            observation=_observation(unit="kpi"),
        )


def test_zero_predicted_refuses_percentage_error() -> None:
    error = compute_prediction_error(
        evidence=_evidence(predicted=0.0),
        observation=_observation(value=5.0),
    )
    assert error.percentage_error is None
    assert error.absolute_error == pytest.approx(5.0)

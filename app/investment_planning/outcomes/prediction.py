"""Point prediction error. Distribution fields stay null without a handoff."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import PredictionErrorClass
from app.investment_optimization.errors import (
    OutcomeUnitMismatchError,
    PredictionErrorNotComputableError,
    PredictionEvidenceIncompleteError,
    SimulationEvidenceNotAvailableError,
)
from app.investment_optimization.ids import new_prediction_error_id, new_prediction_evidence_id
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import (
    DecisionOutcomeObservation,
    PredictionErrorSummary,
    PredictionEvidenceSet,
)
from app.investment_planning.outcomes.simulation_handoff import resolve_simulation_interval
from app.investment_planning.outcomes.temporal import assert_temporal_order


def pin_prediction_evidence(
    *,
    project_id: str,
    predicted_unit: str,
    recommendation_as_of_time: datetime,
    decision_as_of_time: datetime,
    prediction_evidence_as_of_time: datetime,
    predicted_value: float | None = None,
    frontier_selection_ref: str | None = None,
    portfolio_risk_evaluation_ref: str | None = None,
    parity_receipt_id: str | None = None,
    exposure_risk_handoff_ref: str | None = None,
    native_optimization_result_ref: str | None = None,
    simulation_evidence_handoff_ref: str | None = None,
) -> PredictionEvidenceSet:
    assert_temporal_order(
        recommendation_as_of_time=recommendation_as_of_time,
        decision_as_of_time=decision_as_of_time,
        prediction_evidence_as_of_time=prediction_evidence_as_of_time,
    )
    if (
        predicted_value is None
        and not frontier_selection_ref
        and not portfolio_risk_evaluation_ref
        and not native_optimization_result_ref
    ):
        raise PredictionEvidenceIncompleteError("Prediction evidence set has no pinned source.")
    limitations: list[str] = []
    if not simulation_evidence_handoff_ref:
        limitations.append("SIMULATION_EVIDENCE_NOT_AVAILABLE")
    created = datetime.now(UTC)
    payload = {
        # The project is part of the identity of the evidence set. Without it two
        # projects pinning the same refs, value and timestamps collide on one
        # record owned by whichever wrote it first.
        "project_id": project_id,
        "selection": frontier_selection_ref or "",
        "evaluation": portfolio_risk_evaluation_ref or "",
        "parity": parity_receipt_id or "",
        "predicted": predicted_value,
        "unit": predicted_unit,
        "rec_as_of": recommendation_as_of_time.isoformat(),
        "dec_as_of": decision_as_of_time.isoformat(),
        "pred_as_of": prediction_evidence_as_of_time.isoformat(),
        "sim_ref": simulation_evidence_handoff_ref or "",
    }
    return PredictionEvidenceSet(
        prediction_evidence_id=new_prediction_evidence_id(),
        project_id=project_id,
        frontier_selection_ref=frontier_selection_ref,
        portfolio_risk_evaluation_ref=portfolio_risk_evaluation_ref,
        parity_receipt_id=parity_receipt_id,
        exposure_risk_handoff_ref=exposure_risk_handoff_ref,
        native_optimization_result_ref=native_optimization_result_ref,
        simulation_evidence_handoff_ref=simulation_evidence_handoff_ref,
        predicted_value=predicted_value,
        predicted_unit=predicted_unit,
        recommendation_as_of_time=recommendation_as_of_time,
        decision_as_of_time=decision_as_of_time,
        prediction_evidence_as_of_time=prediction_evidence_as_of_time,
        fingerprint=metadata_fingerprint(payload),
        limitations=tuple(limitations),
        created_at=created,
    )


def compute_prediction_error(
    *,
    evidence: PredictionEvidenceSet,
    observation: DecisionOutcomeObservation | None,
    store: OptimizationMetadataStore | None = None,
) -> PredictionErrorSummary:
    limitations = list(evidence.limitations)
    interval = resolve_simulation_interval(
        evidence=evidence, observation=observation, store=store
    )
    if evidence.simulation_evidence_handoff_ref is None:
        limitations.append("SIMULATION_EVIDENCE_NOT_AVAILABLE")
    if observation is None:
        created = datetime.now(UTC)
        payload = {"evidence": evidence.fingerprint, "observed": ""}
        return PredictionErrorSummary(
            prediction_error_id=new_prediction_error_id(),
            project_id=evidence.project_id,
            prediction_evidence_ref=evidence.prediction_evidence_id,
            error_class=PredictionErrorClass.NOT_COMPUTABLE,
            fingerprint=metadata_fingerprint(payload),
            limitations=tuple([*limitations, "OUTCOME_NOT_OBSERVED"]),
            created_at=created,
        )
    if observation.outcome_unit != evidence.predicted_unit:
        raise OutcomeUnitMismatchError("Predicted and realized outcome units do not match.")
    assert_temporal_order(
        recommendation_as_of_time=evidence.recommendation_as_of_time,
        decision_as_of_time=evidence.decision_as_of_time,
        prediction_evidence_as_of_time=evidence.prediction_evidence_as_of_time,
        realized_outcome_as_of_time=observation.as_of_time,
        observation_window_start=observation.observation_window_start,
        observation_window_end=observation.observation_window_end,
    )
    predicted = evidence.predicted_value
    realized = observation.observed_value
    if predicted is None or realized is None:
        raise PredictionErrorNotComputableError("Point prediction error requires both values.")
    signed = realized - predicted
    absolute = abs(signed)
    percent = None if predicted == 0.0 else signed / predicted
    directional = (signed > 0 and predicted > 0) or (signed < 0 and predicted < 0) or signed == 0
    error_class = (
        PredictionErrorClass.WITHIN_EXPECTED_RANGE
        if absolute <= abs(predicted) * 0.1
        else PredictionErrorClass.MAGNITUDE_MISS
    )
    if signed != 0 and not directional:
        error_class = PredictionErrorClass.DIRECTIONAL_MISS
    created = datetime.now(UTC)
    payload = {
        "evidence": evidence.fingerprint,
        "observed": observation.observation_fingerprint,
        "signed": signed,
        "absolute": absolute,
    }
    if interval.realized_percentile is not None:
        payload["percentile"] = interval.realized_percentile
        payload["inside"] = interval.inside_expected_interval
    return PredictionErrorSummary(
        prediction_error_id=new_prediction_error_id(),
        project_id=evidence.project_id,
        prediction_evidence_ref=evidence.prediction_evidence_id,
        outcome_observation_ref=observation.decision_outcome_observation_id,
        predicted_value=predicted,
        realized_value=realized,
        signed_error=signed,
        absolute_error=absolute,
        percentage_error=percent,
        directional_correct=directional,
        realized_percentile=interval.realized_percentile,
        inside_expected_interval=interval.inside_expected_interval,
        error_class=error_class,
        fingerprint=metadata_fingerprint(payload),
        limitations=tuple(dict.fromkeys(limitations)),
        created_at=created,
    )


def require_simulation_handoff(evidence: PredictionEvidenceSet) -> None:
    if not evidence.simulation_evidence_handoff_ref:
        raise SimulationEvidenceNotAvailableError(
            "Simulation evidence is unavailable; missing simulation is not zero uncertainty."
        )

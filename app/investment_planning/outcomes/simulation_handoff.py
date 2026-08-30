"""Resolve P6-09A SimulationEvidenceHandoff for P6-10 prediction intervals.

Loads metadata only. Draw arrays, RNG, correlation, and the simulation engine
are out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.investment_optimization.enums import OutcomeUnit, SimulationRunStatus
from app.investment_optimization.errors import SimulationEvidenceInvalidForPredictionError
from app.investment_optimization.simulation.models import PortfolioOutcomeDistribution
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.outcomes.models import (
    DecisionOutcomeObservation,
    PredictionEvidenceSet,
)
from app.investment_planning.outcomes.temporal import assert_temporal_order

_UNIT_ALIASES = {
    "KPI": OutcomeUnit.KPI,
    "INCREMENTAL_KPI": OutcomeUnit.INCREMENTAL_KPI,
    "REVENUE": OutcomeUnit.REVENUE,
    "INCREMENTAL_REVENUE": OutcomeUnit.INCREMENTAL_REVENUE,
    "CONTRIBUTION_VALUE": OutcomeUnit.CONTRIBUTION_VALUE,
}


@dataclass(frozen=True)
class ResolvedSimulationInterval:
    realized_percentile: float | None
    inside_expected_interval: bool | None


def _fail(message: str) -> None:
    raise SimulationEvidenceInvalidForPredictionError(message)


def _outcome_unit(predicted_unit: str) -> OutcomeUnit | None:
    normalized = predicted_unit.strip().upper().replace(" ", "_")
    mapped = _UNIT_ALIASES.get(normalized)
    if mapped is not None:
        return mapped
    try:
        return OutcomeUnit(normalized)
    except ValueError:
        return None


def _quantile_points(distribution: PortfolioOutcomeDistribution) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for key, value in distribution.quantiles.items():
        if len(key) > 1 and key[0] in {"p", "P"} and key[1:].isdigit():
            points.append((int(key[1:]) / 100.0, float(value)))
    if not any(abs(probability - 0.5) < 1e-12 for probability, _ in points):
        points.append((0.5, float(distribution.median)))
    points.sort(key=lambda item: item[0])
    return points


def _percentile_from_metadata(
    *,
    distribution: PortfolioOutcomeDistribution,
    realized: float,
) -> tuple[float, bool]:
    points = _quantile_points(distribution)
    if not points:
        _fail("PortfolioOutcomeDistribution has no usable quantile metadata.")
    if realized <= points[0][1]:
        percentile = points[0][0]
    elif realized >= points[-1][1]:
        percentile = points[-1][0]
    else:
        percentile = points[-1][0]
        for index in range(len(points) - 1):
            left_p, left_v = points[index]
            right_p, right_v = points[index + 1]
            if left_v <= realized <= right_v:
                if right_v == left_v:
                    percentile = right_p
                else:
                    percentile = left_p + (right_p - left_p) * (realized - left_v) / (
                        right_v - left_v
                    )
                break
    lower = distribution.quantiles.get("p10")
    upper = distribution.quantiles.get("p90")
    if lower is None or upper is None:
        values = [value for _, value in points]
        lower = min(values)
        upper = max(values)
    inside = min(float(lower), float(upper)) <= realized <= max(float(lower), float(upper))
    return percentile, inside


def resolve_simulation_interval(
    *,
    evidence: PredictionEvidenceSet,
    observation: DecisionOutcomeObservation | None,
    store: OptimizationMetadataStore | None,
) -> ResolvedSimulationInterval:
    handoff_id = evidence.simulation_evidence_handoff_ref
    if not handoff_id:
        return ResolvedSimulationInterval(None, None)
    if store is None:
        _fail("Simulation evidence handoff cannot be resolved without the metadata store.")
    handoff = store.get_simulation_evidence_handoff(handoff_id)
    if handoff is None:
        _fail("Simulation evidence handoff was not found.")
    run = store.get_simulation_run(handoff.simulation_run_id)
    if run is None:
        _fail("Simulation run for the evidence handoff was not found.")
    spec = store.get_run_spec(run.run_spec_id)
    if spec is None:
        _fail("Simulation run spec for the evidence handoff was not found.")
    receipt = store.get_simulation_receipt_for_run(run.simulation_run_id)
    if receipt is None:
        _fail("Monte Carlo receipt for the evidence handoff was not found.")
    if run.project_id != evidence.project_id or spec.project_id != evidence.project_id:
        _fail("Simulation evidence handoff project does not match the prediction.")
    if run.status is not SimulationRunStatus.COMPLETE:
        _fail("Simulation evidence handoff requires a COMPLETE simulation run.")
    evidence_time = min(evidence.decision_as_of_time, evidence.prediction_evidence_as_of_time)
    if handoff.as_of_time > evidence_time:
        _fail("Simulation evidence as_of_time is after decision or prediction evidence time.")
    if handoff.model_version_ref != spec.model_version_ref:
        _fail("Simulation evidence model_version_ref is incompatible with the run spec.")
    if not evidence.frontier_selection_ref:
        _fail("Simulation evidence handoff requires a frontier selection to bind a candidate.")
    selection = store.get_selection(evidence.frontier_selection_ref)
    if selection is None:
        _fail("Frontier selection for the simulation evidence handoff was not found.")
    candidate_id = selection.selected_candidate_ref
    if (
        candidate_id not in handoff.candidate_set_ref
        or candidate_id not in spec.candidate_set_ref
    ):
        _fail("Selected candidate is not in the simulation evidence candidate set.")
    predicted_unit = _outcome_unit(evidence.predicted_unit)
    if predicted_unit is None:
        _fail("Predicted outcome unit is not a simulation OutcomeUnit.")
    distributions = store.list_outcome_distributions(simulation_run_id=run.simulation_run_id)
    selected: PortfolioOutcomeDistribution | None = None
    for item in distributions:
        if (
            item.candidate_portfolio_id == candidate_id
            and item.portfolio_outcome_distribution_id
            in handoff.portfolio_outcome_distribution_refs
        ):
            selected = item
            break
    if selected is None:
        _fail("PortfolioOutcomeDistribution for the selected candidate was not found.")
    if selected.outcome_unit is not predicted_unit:
        _fail("Simulation outcome unit does not match the predicted unit.")
    policy = store.get_simulation_policy(run.policy_id)
    if policy is not None and policy.outcome_unit is not predicted_unit:
        _fail("Simulation policy outcome unit does not match the predicted unit.")
    if observation is not None:
        assert_temporal_order(
            recommendation_as_of_time=evidence.recommendation_as_of_time,
            decision_as_of_time=evidence.decision_as_of_time,
            prediction_evidence_as_of_time=evidence.prediction_evidence_as_of_time,
            realized_outcome_as_of_time=observation.as_of_time,
            observation_window_start=observation.observation_window_start,
            observation_window_end=observation.observation_window_end,
        )
        realized = observation.observed_value
        if realized is None:
            return ResolvedSimulationInterval(None, None)
        percentile, inside = _percentile_from_metadata(
            distribution=selected, realized=float(realized)
        )
        return ResolvedSimulationInterval(percentile, inside)
    return ResolvedSimulationInterval(None, None)

"""Governed outcome evaluators. Does not invent Meridian response curves."""

from __future__ import annotations

from app.investment_optimization.enums import OutcomeEvaluatorKind, SimulationSemanticType
from app.investment_optimization.errors import PosteriorSimulationSourceUnavailableError
from app.investment_optimization.simulation.models import ScenarioVariableDistribution

GOVERNED_PLANNING_ECONOMICS_VERSION = "p6-09a/governed-planning-economics/v1"
ACCEPTED_POSTERIOR_EVALUATION_VERSION = "p6-09a/accepted-posterior-evaluation/v1"


def evaluator_version(kind: OutcomeEvaluatorKind) -> str:
    if kind is OutcomeEvaluatorKind.GOVERNED_PLANNING_ECONOMICS:
        return GOVERNED_PLANNING_ECONOMICS_VERSION
    return ACCEPTED_POSTERIOR_EVALUATION_VERSION


def require_posterior_source(*, posterior_artifact_ref: str | None) -> None:
    if not posterior_artifact_ref:
        raise PosteriorSimulationSourceUnavailableError(
            "Accepted posterior artifact is unavailable; missing posterior is not zero uncertainty."
        )


def evaluate_planning_economics(
    *,
    shares: dict[str, float],
    realizations: dict[str, float],
    variables: tuple[ScenarioVariableDistribution, ...],
    baseline_kpi: float,
) -> float:
    """Weighted channel multipliers times conversion value times pinned baseline KPI."""
    conversion = 1.0
    demand = 1.0
    weighted = 0.0
    used_channel = False
    for variable in variables:
        value = realizations[variable.variable_id]
        if variable.semantic_type is SimulationSemanticType.CONVERSION_VALUE:
            conversion = value
        elif variable.semantic_type is SimulationSemanticType.DEMAND_MULTIPLIER:
            demand = value
        elif variable.channel_id and variable.channel_id in shares:
            weighted += shares[variable.channel_id] * value
            used_channel = True
        elif (
            variable.semantic_type is SimulationSemanticType.CHANNEL_MULTIPLIER
            and variable.channel_id in shares
        ):
            weighted += shares[variable.channel_id] * value
            used_channel = True
    if not used_channel:
        weighted = demand
    return baseline_kpi * weighted * conversion

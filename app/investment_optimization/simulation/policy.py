"""Pin and fingerprint a MonteCarloSimulationPolicy."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    SIMULATION_ENGINE_VERSION,
    SIMULATION_MAX_CANDIDATES,
    SIMULATION_MAX_CELLS,
    SIMULATION_MAX_DRAWS,
    SIMULATION_MAX_VARIABLES,
    SIMULATION_MIN_DRAWS,
    OutcomeEvaluatorKind,
    OutcomeUnit,
)
from app.investment_optimization.errors import (
    SimulationLimitExceededError,
    SimulationPolicyInvalidError,
)
from app.investment_optimization.ids import new_simulation_policy_id
from app.investment_optimization.simulation.models import MonteCarloSimulationPolicy
from app.investment_planning.fingerprint import metadata_fingerprint


def pin_simulation_policy(
    *,
    tenant_id: str,
    project_id: str,
    number_of_draws: int,
    random_seed: int,
    batch_size: int,
    distribution_set_ref: str,
    correlation_spec_ref: str,
    candidate_set_ref: tuple[str, ...],
    variable_count: int,
    as_of_time: datetime,
    posterior_sampling_policy: str = "NONE",
    outcome_evaluator: OutcomeEvaluatorKind = OutcomeEvaluatorKind.GOVERNED_PLANNING_ECONOMICS,
    outcome_unit: OutcomeUnit = OutcomeUnit.KPI,
    tail_probability: float = 0.05,
) -> MonteCarloSimulationPolicy:
    if number_of_draws < SIMULATION_MIN_DRAWS or number_of_draws > SIMULATION_MAX_DRAWS:
        raise SimulationLimitExceededError("number_of_draws is outside the governed policy bounds.")
    if batch_size < 1 or batch_size > number_of_draws:
        raise SimulationPolicyInvalidError("batch_size must be in [1, number_of_draws].")
    if not candidate_set_ref:
        raise SimulationPolicyInvalidError("candidate_set_ref is required.")
    if len(candidate_set_ref) > SIMULATION_MAX_CANDIDATES:
        raise SimulationLimitExceededError("candidate count exceeds the governed maximum.")
    if variable_count > SIMULATION_MAX_VARIABLES:
        raise SimulationLimitExceededError("variable count exceeds the governed maximum.")
    if len(candidate_set_ref) * number_of_draws > SIMULATION_MAX_CELLS:
        raise SimulationLimitExceededError("candidate × draw cells exceed the governed maximum.")
    created = datetime.now(UTC)
    payload = {
        "project_id": project_id,
        "engine_version": SIMULATION_ENGINE_VERSION,
        "number_of_draws": number_of_draws,
        "random_seed": random_seed,
        "batch_size": batch_size,
        "distribution_set_ref": distribution_set_ref,
        "correlation_spec_ref": correlation_spec_ref,
        "candidate_set_ref": list(candidate_set_ref),
        "posterior_sampling_policy": posterior_sampling_policy,
        "outcome_evaluator": outcome_evaluator.value,
        "outcome_unit": outcome_unit.value,
        "tail_probability": tail_probability,
        "as_of_time": as_of_time.isoformat(),
    }
    return MonteCarloSimulationPolicy(
        policy_id=new_simulation_policy_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        number_of_draws=number_of_draws,
        random_seed=random_seed,
        batch_size=batch_size,
        distribution_set_ref=distribution_set_ref,
        correlation_spec_ref=correlation_spec_ref,
        candidate_set_ref=candidate_set_ref,
        posterior_sampling_policy=posterior_sampling_policy,
        outcome_evaluator=outcome_evaluator,
        outcome_unit=outcome_unit,
        tail_probability=tail_probability,
        as_of_time=as_of_time,
        fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )

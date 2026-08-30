"""Compile an immutable SimulationRunSpec."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.ids import new_simulation_run_spec_id
from app.investment_optimization.simulation.models import (
    MonteCarloSimulationPolicy,
    ScenarioCorrelationSpec,
    ScenarioDistributionSet,
    SimulationRunSpec,
)
from app.investment_planning.fingerprint import metadata_fingerprint


def compile_run_spec(
    *,
    tenant_id: str,
    project_id: str,
    baseline_ref: str,
    policy: MonteCarloSimulationPolicy,
    distribution_set: ScenarioDistributionSet,
    correlation: ScenarioCorrelationSpec,
    model_version_ref: str,
    posterior_artifact_ref: str | None = None,
    future_assumption_set_ref: str | None = None,
    exposure_risk_handoff_ref: str | None = None,
) -> SimulationRunSpec:
    created = datetime.now(UTC)
    payload = {
        "baseline_ref": baseline_ref,
        "candidate_set_ref": list(policy.candidate_set_ref),
        "model_version_ref": model_version_ref,
        "posterior_artifact_ref": posterior_artifact_ref or "",
        "future_assumption_set_ref": future_assumption_set_ref or "",
        "scenario_distribution_set_ref": distribution_set.scenario_distribution_set_id,
        "distribution_set_fingerprint": distribution_set.distribution_set_fingerprint,
        "scenario_correlation_spec_ref": correlation.correlation_spec_id,
        "correlation_fingerprint": correlation.fingerprint,
        "exposure_risk_handoff_ref": exposure_risk_handoff_ref or "",
        "simulation_policy_ref": policy.policy_id,
        "policy_fingerprint": policy.fingerprint,
        "as_of_time": policy.as_of_time.isoformat(),
    }
    return SimulationRunSpec(
        simulation_run_spec_id=new_simulation_run_spec_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        baseline_ref=baseline_ref,
        candidate_set_ref=policy.candidate_set_ref,
        model_version_ref=model_version_ref,
        posterior_artifact_ref=posterior_artifact_ref,
        future_assumption_set_ref=future_assumption_set_ref,
        scenario_distribution_set_ref=distribution_set.scenario_distribution_set_id,
        scenario_correlation_spec_ref=correlation.correlation_spec_id,
        exposure_risk_handoff_ref=exposure_risk_handoff_ref,
        simulation_policy_ref=policy.policy_id,
        as_of_time=policy.as_of_time,
        input_fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )

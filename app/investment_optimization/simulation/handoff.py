"""Serialized P6-10 simulation evidence handoff. Refs only."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import SIMULATION_ENGINE_VERSION
from app.investment_optimization.ids import new_simulation_handoff_id
from app.investment_optimization.simulation.models import (
    MonteCarloSimulationReceipt,
    PortfolioOutcomeDistribution,
    SimulationEvidenceHandoff,
    SimulationRunSpec,
)


def build_evidence_handoff(
    *,
    spec: SimulationRunSpec,
    receipt: MonteCarloSimulationReceipt,
    distributions: tuple[PortfolioOutcomeDistribution, ...],
    baseline_distribution_ref: str | None = None,
) -> SimulationEvidenceHandoff:
    created = datetime.now(UTC)
    refs = tuple(item.portfolio_outcome_distribution_id for item in distributions)
    return SimulationEvidenceHandoff(
        simulation_evidence_handoff_id=new_simulation_handoff_id(),
        simulation_run_id=receipt.simulation_run_id,
        portfolio_outcome_distribution_refs=refs,
        baseline_distribution_ref=baseline_distribution_ref,
        scenario_distribution_set_ref=spec.scenario_distribution_set_ref,
        correlation_spec_ref=spec.scenario_correlation_spec_ref,
        model_version_ref=spec.model_version_ref,
        candidate_set_ref=spec.candidate_set_ref,
        engine_version=SIMULATION_ENGINE_VERSION,
        input_fingerprint=spec.input_fingerprint,
        simulation_fingerprint=receipt.simulation_fingerprint,
        as_of_time=spec.as_of_time,
        limitations=receipt.limitations,
        created_at=created,
    )

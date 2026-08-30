"""Lifecycle, reproducibility, posterior fail-closed, P6-09 bridge."""

from __future__ import annotations

import pytest

from app.investment_optimization.enums import OutcomeEvaluatorKind, SimulationRunStatus
from app.investment_optimization.errors import (
    PosteriorSimulationSourceUnavailableError,
    SimulationCandidateInvalidError,
    SimulationInsufficientDrawsForTailError,
)
from app.investment_optimization.simulation.p6_09_bridge import draws_for_evaluate
from app.investment_optimization.simulation.sampling import batch_seed
from app.investment_optimization.simulation.summaries import summarize_outcomes
from tests.unit.investment_optimization.p6_09a_support import governed_stack


def test_ready_running_complete_and_idempotent() -> None:
    sim, run, spec, policy, dist_set, corr, candidates, baseline = governed_stack()
    assert run.status is SimulationRunStatus.READY
    first = sim.execute_inline(
        simulation_run_id=run.simulation_run_id,
        spec=spec,
        policy=policy,
        distribution_set=dist_set,
        correlation=corr,
        candidates=candidates,
        baseline_shares=baseline,
    )
    assert first.status is SimulationRunStatus.COMPLETE
    second = sim.execute_inline(
        simulation_run_id=run.simulation_run_id,
        spec=spec,
        policy=policy,
        distribution_set=dist_set,
        correlation=corr,
        candidates=candidates,
        baseline_shares=baseline,
    )
    assert first.simulation_fingerprint == second.simulation_fingerprint
    assert second.simulation_run_id == first.simulation_run_id
    receipt = sim.get_receipt(run.simulation_run_id)
    assert receipt.status is SimulationRunStatus.COMPLETE
    assert receipt.draw_count == 64
    assert receipt.batch_count == 2


def test_same_seed_same_fingerprint() -> None:
    sim_a, run_a, spec_a, policy_a, dist_a, corr_a, cand_a, base_a = governed_stack()
    sim_a.execute_inline(
        simulation_run_id=run_a.simulation_run_id,
        spec=spec_a,
        policy=policy_a,
        distribution_set=dist_a,
        correlation=corr_a,
        candidates=cand_a,
        baseline_shares=base_a,
    )
    sim_b, run_b, spec_b, policy_b, dist_b, corr_b, cand_b, base_b = governed_stack()
    sim_b.execute_inline(
        simulation_run_id=run_b.simulation_run_id,
        spec=spec_b,
        policy=policy_b,
        distribution_set=dist_b,
        correlation=corr_b,
        candidates=cand_b,
        baseline_shares=base_b,
    )
    dist_a_row = sim_a.get_distributions(run_a.simulation_run_id)[0]
    dist_b_row = sim_b.get_distributions(run_b.simulation_run_id)[0]
    assert dist_a_row.mean == dist_b_row.mean
    assert dist_a_row.median == dist_b_row.median
    assert dist_a_row.lower_tail_metric == dist_b_row.lower_tail_metric
    assert dist_a_row.distribution_fingerprint == dist_b_row.distribution_fingerprint


def test_posterior_evaluator_fails_without_artifact() -> None:
    sim, run, spec, policy, dist_set, corr, candidates, baseline = governed_stack()
    posterior_policy = policy.model_copy(
        update={"outcome_evaluator": OutcomeEvaluatorKind.ACCEPTED_POSTERIOR_EVALUATION}
    )
    with pytest.raises(PosteriorSimulationSourceUnavailableError):
        sim.execute_inline(
            simulation_run_id=run.simulation_run_id,
            spec=spec,
            policy=posterior_policy,
            distribution_set=dist_set,
            correlation=corr,
            candidates=candidates,
            baseline_shares=baseline,
        )


def test_p6_09_bridge_loads_artifact_tuples() -> None:
    sim, run, spec, policy, dist_set, corr, candidates, baseline = governed_stack()
    sim.execute_inline(
        simulation_run_id=run.simulation_run_id,
        spec=spec,
        policy=policy,
        distribution_set=dist_set,
        correlation=corr,
        candidates=candidates,
        baseline_shares=baseline,
    )
    dist = sim.get_distributions(run.simulation_run_id)[0]
    candidate_draws, baseline_draws = draws_for_evaluate(
        object_store=sim._object_store,
        bucket=sim._artifact_bucket,
        artifact_ref=dist.distribution_artifact_ref,
    )
    assert len(candidate_draws) == 64
    assert len(baseline_draws) == 64


def test_insufficient_draws_fail_closed() -> None:
    with pytest.raises(SimulationInsufficientDrawsForTailError):
        summarize_outcomes(
            candidate_outcomes=(1.0, 1.1),
            baseline_outcomes=(1.0, 1.0),
            tail_probability=0.05,
        )


def test_invalid_candidate_fails() -> None:
    sim, run, spec, policy, dist_set, corr, candidates, baseline = governed_stack()
    broken = candidates[0].model_copy(update={"feasibility_receipt_id": ""})
    with pytest.raises(SimulationCandidateInvalidError):
        sim.execute_inline(
            simulation_run_id=run.simulation_run_id,
            spec=spec,
            policy=policy,
            distribution_set=dist_set,
            correlation=corr,
            candidates=(broken, *candidates[1:]),
            baseline_shares=baseline,
        )


def test_batch_seed_is_schedule_stable() -> None:
    assert batch_seed(parent_seed=7, batch_index=0) == batch_seed(parent_seed=7, batch_index=0)
    assert batch_seed(parent_seed=7, batch_index=0) != batch_seed(parent_seed=7, batch_index=1)


def test_handoff_has_temporal_authority() -> None:
    sim, run, spec, policy, dist_set, corr, candidates, baseline = governed_stack()
    sim.execute_inline(
        simulation_run_id=run.simulation_run_id,
        spec=spec,
        policy=policy,
        distribution_set=dist_set,
        correlation=corr,
        candidates=candidates,
        baseline_shares=baseline,
    )
    handoff = sim.get_handoff(run.simulation_run_id)
    dumped = handoff.model_dump()
    assert handoff.as_of_time == spec.as_of_time
    assert handoff.model_version_ref
    assert handoff.candidate_set_ref
    assert handoff.scenario_distribution_set_ref
    assert handoff.correlation_spec_ref
    assert handoff.input_fingerprint
    assert handoff.simulation_fingerprint
    assert "candidate_outcomes" not in dumped
    assert "draws" not in dumped

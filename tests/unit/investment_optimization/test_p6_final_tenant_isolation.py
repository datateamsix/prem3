"""Class A tenant isolation proofs for the P6-09A simulation surface.

Findings A1 and A3 of docs/backend/P6_FINAL_CODE_REVIEW_GATE.md.

A foreign workspace must never read a record it does not own, and must not be
able to tell whether the identifier exists at all.
"""

from __future__ import annotations

import pytest

from app.investment_optimization.enums import CorrelationAuthority
from app.investment_optimization.errors import SimulationNotFoundError
from tests.unit.investment_optimization.p6_09_support import PROJECT, TENANT
from tests.unit.investment_optimization.p6_09a_support import governed_stack, simulation_service

OTHER_TENANT = "ten_p609_intruder"
OTHER_PROJECT = "ws_p609_intruder"

FOREIGN = {"tenant_id": OTHER_TENANT, "project_id": OTHER_PROJECT}
OWNER = {"tenant_id": TENANT, "project_id": PROJECT}


def executed_stack():
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
    return sim, run, spec, policy, dist_set, corr, candidates


def test_distribution_set_read_refuses_foreign_tenant() -> None:
    sim, _run, _spec, _policy, dist_set, _corr, _candidates, _shares = governed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_distribution_set(dist_set.scenario_distribution_set_id, **FOREIGN)


def test_distribution_set_read_allows_owning_tenant() -> None:
    sim, _run, _spec, _policy, dist_set, _corr, _candidates, _shares = governed_stack()

    item = sim.get_distribution_set(dist_set.scenario_distribution_set_id, **OWNER)

    assert item.scenario_distribution_set_id == dist_set.scenario_distribution_set_id


def test_correlation_read_refuses_foreign_tenant() -> None:
    sim, _run, _spec, _policy, _dist_set, corr, _candidates, _shares = governed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_correlation(corr.correlation_spec_id, **FOREIGN)


def test_policy_read_refuses_foreign_tenant() -> None:
    sim, _run, _spec, policy, _dist_set, _corr, _candidates, _shares = governed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_policy(policy.policy_id, **FOREIGN)


def test_run_spec_read_refuses_foreign_tenant() -> None:
    sim, _run, spec, _policy, _dist_set, _corr, _candidates, _shares = governed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_run_spec(spec.simulation_run_spec_id, **FOREIGN)


def test_run_read_refuses_foreign_tenant() -> None:
    sim, run, _spec, _policy, _dist_set, _corr, _candidates, _shares = governed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_run(run.simulation_run_id, **FOREIGN)


def test_receipt_read_refuses_foreign_tenant() -> None:
    sim, run, *_ = executed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_receipt(run.simulation_run_id, **FOREIGN)


def test_outcome_distributions_read_refuses_foreign_tenant() -> None:
    sim, run, *_ = executed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_distributions(run.simulation_run_id, **FOREIGN)


def test_handoff_read_refuses_foreign_tenant() -> None:
    sim, run, *_ = executed_stack()

    with pytest.raises(SimulationNotFoundError):
        sim.get_handoff(run.simulation_run_id, **FOREIGN)


def test_run_scoped_reads_allow_owning_tenant() -> None:
    sim, run, *_ = executed_stack()

    assert sim.get_receipt(run.simulation_run_id, **OWNER).simulation_run_id == (
        run.simulation_run_id
    )
    assert sim.get_distributions(run.simulation_run_id, **OWNER)
    assert sim.get_handoff(run.simulation_run_id, **OWNER)


def test_candidate_read_refuses_foreign_tenant() -> None:
    sim, _run, _spec, _policy, _dist_set, _corr, candidates, _shares = governed_stack()

    assert sim.get_candidate(candidates[0].candidate_portfolio_id, **FOREIGN) is None


def test_candidate_read_allows_owning_tenant() -> None:
    sim, _run, _spec, _policy, _dist_set, _corr, candidates, _shares = governed_stack()

    found = sim.get_candidate(candidates[0].candidate_portfolio_id, **OWNER)

    assert found is not None
    assert found.candidate_portfolio_id == candidates[0].candidate_portfolio_id


def test_correlation_spec_is_not_shared_across_tenants() -> None:
    # An INDEPENDENT spec with no variables validates and fingerprints to a
    # constant, so an unscoped idempotency lookup hands the second tenant the
    # first tenant's record.
    sim = simulation_service()
    first = sim.create_correlation_spec(
        tenant_id=TENANT,
        project_id=PROJECT,
        authority=CorrelationAuthority.INDEPENDENT,
        variable_ids=(),
    )
    second = sim.create_correlation_spec(
        tenant_id=OTHER_TENANT,
        project_id=OTHER_PROJECT,
        authority=CorrelationAuthority.INDEPENDENT,
        variable_ids=(),
    )

    assert second.correlation_spec_id != first.correlation_spec_id
    assert second.tenant_id == OTHER_TENANT
    assert second.project_id == OTHER_PROJECT


def test_correlation_spec_stays_idempotent_within_one_tenant() -> None:
    sim = simulation_service()
    first = sim.create_correlation_spec(
        tenant_id=TENANT,
        project_id=PROJECT,
        authority=CorrelationAuthority.INDEPENDENT,
        variable_ids=(),
    )
    again = sim.create_correlation_spec(
        tenant_id=TENANT,
        project_id=PROJECT,
        authority=CorrelationAuthority.INDEPENDENT,
        variable_ids=(),
    )

    assert again.correlation_spec_id == first.correlation_spec_id

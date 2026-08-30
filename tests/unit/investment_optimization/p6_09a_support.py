"""P6-09A test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    CorrelationAuthority,
    DistributionAuthority,
    DistributionFamily,
    SimulationSemanticType,
)
from app.investment_optimization.simulation.distributions import pin_variable
from app.investment_optimization.simulation.execution import LocalSimulationExecutionAdapter
from app.investment_optimization.simulation.service import SimulationService
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from tests.unit.investment_optimization.p6_09_support import (
    MODEL,
    NATIVE_SHARES,
    PLAN,
    PROJECT,
    READY,
    RUN,
    TENANT,
    risk_service,
)

AS_OF = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def demand_variable():
    return pin_variable(
        semantic_type=SimulationSemanticType.DEMAND_MULTIPLIER,
        family=DistributionFamily.NORMAL,
        parameters={"mean": 1.0, "std": 0.05},
        source_authority=DistributionAuthority.USER_APPROVED,
        source_refs=("policy:demand",),
        unit="1",
        lower_bound=0.0,
        truncate=True,
    )


def simulation_service() -> SimulationService:
    return SimulationService(
        InMemoryOptimizationMetadataStore(),
        adapter=LocalSimulationExecutionAdapter(),
    )


def governed_stack():
    sim = simulation_service()
    risk = risk_service()
    policy = risk.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    candidates = risk.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    for item in candidates:
        sim.register_candidate_shares(
            item.candidate_portfolio_id,
            risk.shares_for(item.candidate_portfolio_id),
        )
        sim._store.put(item)
    variable = demand_variable()
    dist_set = sim.create_distribution_set(
        tenant_id=TENANT,
        project_id=PROJECT,
        effective_period="FY2027Q1",
        as_of_time=AS_OF,
        variables=(variable,),
        approval_state="APPROVED",
        source_refs=("policy:demand",),
    )
    corr = sim.create_correlation_spec(
        tenant_id=TENANT,
        project_id=PROJECT,
        authority=CorrelationAuthority.INDEPENDENT,
        variable_ids=(variable.variable_id,),
    )
    sim_policy = sim.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        number_of_draws=64,
        random_seed=7,
        batch_size=32,
        distribution_set_ref=dist_set.scenario_distribution_set_id,
        correlation_spec_ref=corr.correlation_spec_id,
        candidate_set_ref=tuple(item.candidate_portfolio_id for item in candidates),
        variable_count=1,
        as_of_time=AS_OF,
    )
    spec = sim.create_run_spec(
        tenant_id=TENANT,
        project_id=PROJECT,
        baseline_ref=PLAN,
        policy=sim_policy,
        distribution_set=dist_set,
        correlation=corr,
        model_version_ref=MODEL,
    )
    run = sim.create_run(
        spec=spec,
        policy=sim_policy,
        distribution_set=dist_set,
        correlation=corr,
        candidates=candidates,
    )
    return sim, run, spec, sim_policy, dist_set, corr, candidates, NATIVE_SHARES

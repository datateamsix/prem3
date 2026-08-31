"""P6-09A privacy: no draws in Firestore; HTTP no-store; no local adapter in app."""

from __future__ import annotations

from pathlib import Path

from app.control_plane.entitlements import PlanId
from app.investment_optimization.enums import RiskTaxonomyClass
from app.investment_optimization.errors import PosteriorRiskUnavailableError
from app.investment_optimization.simulation.models import SimulationDrawArtifact
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.errors import PersistenceBarrierError
from app.tools.simulation_worker import execute_server_owned_request
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_optimization.p6_09_support import (
    BASELINE_SHARES,
    MODEL,
    NATIVE_SHARES,
    PLAN,
    PROJECT,
    READY,
    RUN,
    TENANT,
    risk_service,
)
from tests.unit.investment_optimization.p6_09a_support import governed_stack


def test_draw_artifact_cannot_be_stored() -> None:
    store = InMemoryOptimizationMetadataStore()
    artifact = SimulationDrawArtifact(
        simulation_run_id="osim_x",
        candidate_portfolio_id="ocand_x",
        draw_count=2,
        candidate_outcomes=(1.0, 2.0),
        baseline_outcomes=(1.0, 1.0),
        losses=(0.0, -1.0),
        fingerprint="fp",
    )
    try:
        store.put(artifact)  # type: ignore[arg-type]
        raise AssertionError("amount-bearing draw artifact must not persist")
    except PersistenceBarrierError:
        pass


def test_metadata_has_no_draw_arrays() -> None:
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
    dist = sim.get_distributions(run.simulation_run_id, tenant_id=TENANT, project_id=PROJECT)[0]
    dumped = dist.model_dump()
    assert "candidate_outcomes" not in dumped
    assert "baseline_outcomes" not in dumped
    assert "recommended_total" not in dumped


def test_http_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    created = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio/simulations/correlation-specs",
        headers=auth_header(),
        json={"authority": "INDEPENDENT", "variable_ids": ["osvar_a"]},
    )
    assert created.status_code == 200, created.text
    assert created.headers.get("cache-control") == "private, no-store"
    spec_id = created.json()["correlation_spec_id"]
    fetched = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio/simulations/correlation-specs/{spec_id}",
        headers=auth_header(),
    )
    assert fetched.status_code == 200
    assert fetched.headers.get("cache-control") == "private, no-store"


def test_app_does_not_install_local_adapter() -> None:
    text = Path("app/service/app.py").read_text(encoding="utf-8")
    assert "LocalSimulationExecutionAdapter" not in text
    assert "UnavailableSimulationExecutionAdapter" in text


def test_worker_rejects_amount_keys() -> None:
    try:
        execute_server_owned_request({"simulation_run_id": "osim_x", "draw_array": [1.0]})
        raise AssertionError("worker must reject amount keys")
    except RuntimeError:
        pass


def test_p6_09_evaluate_without_simulation_still_unavailable() -> None:
    service = risk_service()
    policy = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        evaluation_dimensions=(RiskTaxonomyClass.POSTERIOR,),
    )
    candidates = service.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    try:
        service.evaluate(
            policy=policy,
            candidate=candidates[0],
            baseline_shares=BASELINE_SHARES,
            candidate_draws=None,
            baseline_draws=None,
        )
        raise AssertionError("missing draws must stay POSTERIOR_RISK_UNAVAILABLE")
    except PosteriorRiskUnavailableError:
        pass

"""P6-final SimulationEvidenceHandoff resolver. Metadata only; no draw arrays."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.investment_optimization.enums import (
    SIMULATION_ENGINE_VERSION,
    SIMULATION_POLICY_VERSION,
    OutcomeUnit,
    SimulationRunStatus,
)
from app.investment_optimization.errors import (
    SimulationEvidenceInvalidForPredictionError,
)
from app.investment_optimization.simulation.models import (
    MonteCarloSimulationPolicy,
    MonteCarloSimulationReceipt,
    PortfolioOutcomeDistribution,
    SimulationDrawArtifact,
    SimulationEvidenceHandoff,
    SimulationRun,
    SimulationRunSpec,
)
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.errors import PersistenceBarrierError
from app.investment_planning.outcomes.prediction import compute_prediction_error
from app.investment_planning.outcomes.service import OutcomeService
from tests.unit.investment_planning.p6_10_support import (
    PROJECT,
    RECOMMENDED_REF,
    TENANT,
    frontier_selection,
    now,
)
from tests.unit.investment_planning.test_p6_10_outcomes_prediction import (
    _evidence,
    _observation,
)

HANDOFF_ID = "ohand_p6finalhandoff00001"
RUN_ID = "osim_p6finalrun000000001"
SPEC_ID = "ospec_p6finalspec0000001"
POLICY_ID = "osimpol_p6finalpolicy0001"
DIST_ID = "odist_p6finaldist0000001"
RECEIPT_ID = "osimr_p6finalreceipt00001"
MODEL_REF = "mver_p6finalmodel0000001"
AS_OF = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)

_DRAW_KEYS = frozenset({"candidate_outcomes", "baseline_outcomes", "losses"})


def _run(*, status: SimulationRunStatus = SimulationRunStatus.COMPLETE, project_id: str = PROJECT):
    return SimulationRun(
        simulation_run_id=RUN_ID,
        tenant_id=TENANT,
        project_id=project_id,
        run_spec_id=SPEC_ID,
        policy_id=POLICY_ID,
        status=status,
        engine_version=SIMULATION_ENGINE_VERSION,
        number_of_draws=64,
        random_seed=7,
        as_of_time=AS_OF,
        input_fingerprint="sim_input_fp_p6final",
        simulation_fingerprint="sim_fp_p6final",
        created_at=AS_OF,
    )


def _spec(*, project_id: str = PROJECT, candidate_id: str = RECOMMENDED_REF):
    return SimulationRunSpec(
        simulation_run_spec_id=SPEC_ID,
        tenant_id=TENANT,
        project_id=project_id,
        baseline_ref="ipln_p610approved00000001",
        candidate_set_ref=(candidate_id,),
        model_version_ref=MODEL_REF,
        scenario_distribution_set_ref="osds_p6finalset000000001",
        scenario_correlation_spec_ref="oscor_p6finalcorr0000001",
        simulation_policy_ref=POLICY_ID,
        as_of_time=AS_OF,
        schema_version=SIMULATION_POLICY_VERSION,
        input_fingerprint="sim_input_fp_p6final",
        created_at=AS_OF,
    )


def _policy(*, outcome_unit: OutcomeUnit = OutcomeUnit.REVENUE):
    return MonteCarloSimulationPolicy(
        policy_id=POLICY_ID,
        tenant_id=TENANT,
        project_id=PROJECT,
        policy_version=SIMULATION_POLICY_VERSION,
        engine_version=SIMULATION_ENGINE_VERSION,
        number_of_draws=64,
        random_seed=7,
        batch_size=32,
        distribution_set_ref="osds_p6finalset000000001",
        correlation_spec_ref="oscor_p6finalcorr0000001",
        candidate_set_ref=(RECOMMENDED_REF,),
        outcome_unit=outcome_unit,
        as_of_time=AS_OF,
        fingerprint="sim_policy_fp_p6final",
        created_at=AS_OF,
    )


def _receipt():
    return MonteCarloSimulationReceipt(
        receipt_id=RECEIPT_ID,
        simulation_run_id=RUN_ID,
        tenant_id=TENANT,
        project_id=PROJECT,
        status=SimulationRunStatus.COMPLETE,
        draw_count=64,
        effective_draw_count=64,
        batch_count=2,
        engine_version=SIMULATION_ENGINE_VERSION,
        input_fingerprint="sim_input_fp_p6final",
        simulation_fingerprint="sim_fp_p6final",
        outcome_distribution_ids=(DIST_ID,),
        created_at=AS_OF,
    )


def _distribution(*, outcome_unit: OutcomeUnit = OutcomeUnit.REVENUE):
    return PortfolioOutcomeDistribution(
        portfolio_outcome_distribution_id=DIST_ID,
        simulation_run_id=RUN_ID,
        candidate_portfolio_id=RECOMMENDED_REF,
        outcome_unit=outcome_unit,
        draw_count=64,
        mean=102.0,
        median=100.0,
        quantiles={"p10": 80.0, "p50": 100.0, "p90": 130.0},
        distribution_artifact_ref="gs://prem3-test-artifacts/sim/p6final.parquet",
        distribution_fingerprint="dist_fp_p6final",
        created_at=AS_OF,
    )


def _handoff(
    *,
    as_of_time: datetime = AS_OF,
    candidate_id: str = RECOMMENDED_REF,
    model_version_ref: str = MODEL_REF,
):
    return SimulationEvidenceHandoff(
        simulation_evidence_handoff_id=HANDOFF_ID,
        simulation_run_id=RUN_ID,
        portfolio_outcome_distribution_refs=(DIST_ID,),
        scenario_distribution_set_ref="osds_p6finalset000000001",
        correlation_spec_ref="oscor_p6finalcorr0000001",
        model_version_ref=model_version_ref,
        candidate_set_ref=(candidate_id,),
        engine_version=SIMULATION_ENGINE_VERSION,
        input_fingerprint="sim_input_fp_p6final",
        simulation_fingerprint="sim_fp_p6final",
        as_of_time=as_of_time,
        created_at=AS_OF,
    )


def _seed(
    store: InMemoryOptimizationMetadataStore,
    *,
    run: SimulationRun | None = None,
    spec: SimulationRunSpec | None = None,
    policy: MonteCarloSimulationPolicy | None = None,
    receipt: MonteCarloSimulationReceipt | None = None,
    distribution: PortfolioOutcomeDistribution | None = None,
    handoff: SimulationEvidenceHandoff | None = None,
) -> None:
    store.put(frontier_selection())
    store.put(policy if policy is not None else _policy())
    store.put(spec if spec is not None else _spec())
    store.put(run if run is not None else _run())
    store.put(receipt if receipt is not None else _receipt())
    store.put(distribution if distribution is not None else _distribution())
    store.put(handoff if handoff is not None else _handoff())


def _persisted_payloads(store: InMemoryOptimizationMetadataStore) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for value in vars(store).values():
        if not isinstance(value, dict):
            continue
        for item in value.values():
            if hasattr(item, "model_dump"):
                payloads.append(item.model_dump())
    return payloads


def test_no_handoff_is_green_limitation() -> None:
    service = OutcomeService(InMemoryOptimizationMetadataStore())
    error = service.create_prediction_error(evidence=_evidence(), observation=_observation())
    assert error.realized_percentile is None
    assert error.inside_expected_interval is None
    assert "SIMULATION_EVIDENCE_NOT_AVAILABLE" in error.limitations


def test_valid_handoff_sets_percentile_without_draws() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store)
    service = OutcomeService(store)
    evidence = _evidence(sim_ref=HANDOFF_ID)
    error = service.create_prediction_error(evidence=evidence, observation=_observation())
    assert error.realized_percentile == pytest.approx(0.5 + 0.4 * (10.0 / 30.0))
    assert error.inside_expected_interval is True
    assert "SIMULATION_EVIDENCE_NOT_AVAILABLE" not in error.limitations
    dump = _persisted_payloads(store)
    for payload in dump:
        assert _DRAW_KEYS.isdisjoint(payload)
        assert "candidate_outcomes" not in payload


def test_invalid_project_is_fail_closed() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store, run=_run(project_id="ws_otherproject0000001"))
    with pytest.raises(SimulationEvidenceInvalidForPredictionError):
        compute_prediction_error(
            evidence=_evidence(sim_ref=HANDOFF_ID),
            observation=_observation(),
            store=store,
        )


def test_invalid_candidate_is_fail_closed() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store, handoff=_handoff(candidate_id="ocand_p6finalother000001"))
    with pytest.raises(SimulationEvidenceInvalidForPredictionError):
        compute_prediction_error(
            evidence=_evidence(sim_ref=HANDOFF_ID),
            observation=_observation(),
            store=store,
        )


def test_invalid_unit_is_fail_closed() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store, distribution=_distribution(outcome_unit=OutcomeUnit.KPI))
    with pytest.raises(SimulationEvidenceInvalidForPredictionError):
        compute_prediction_error(
            evidence=_evidence(sim_ref=HANDOFF_ID),
            observation=_observation(),
            store=store,
        )


def test_future_as_of_time_is_fail_closed() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store, handoff=_handoff(as_of_time=now() + timedelta(days=1)))
    with pytest.raises(SimulationEvidenceInvalidForPredictionError):
        compute_prediction_error(
            evidence=_evidence(sim_ref=HANDOFF_ID),
            observation=_observation(),
            store=store,
        )


def test_non_complete_run_is_fail_closed() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store, run=_run(status=SimulationRunStatus.FAILED))
    with pytest.raises(SimulationEvidenceInvalidForPredictionError):
        compute_prediction_error(
            evidence=_evidence(sim_ref=HANDOFF_ID),
            observation=_observation(),
            store=store,
        )


def test_draw_artifact_cannot_enter_control_plane() -> None:
    store = InMemoryOptimizationMetadataStore()
    with pytest.raises(PersistenceBarrierError):
        store.put(
            SimulationDrawArtifact(
                simulation_run_id=RUN_ID,
                candidate_portfolio_id=RECOMMENDED_REF,
                draw_count=2,
                candidate_outcomes=(1.0, 2.0),
                baseline_outcomes=(0.5, 1.5),
                losses=(0.0, 0.0),
                fingerprint="draw_fp_p6final",
            )
        )


def test_unknown_handoff_ref_is_fail_closed() -> None:
    store = InMemoryOptimizationMetadataStore()
    _seed(store)
    with pytest.raises(SimulationEvidenceInvalidForPredictionError):
        compute_prediction_error(
            evidence=_evidence(sim_ref="ohand_missinghandoff00001"),
            observation=_observation(),
            store=store,
        )

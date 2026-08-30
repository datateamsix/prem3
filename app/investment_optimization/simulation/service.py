"""Idempotent P6-09A simulation orchestration. HTTP does not run the engine."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    CorrelationAuthority,
    OutcomeEvaluatorKind,
    SimulationRunStatus,
)
from app.investment_optimization.errors import (
    LiveSimulationJobProofPendingError,
    PosteriorSimulationSourceUnavailableError,
    ScenarioDistributionNotGovernedError,
    SimulationCandidateInvalidError,
    SimulationInputNotReadyError,
    SimulationNotFoundError,
    SimulationRuntimeUnavailableError,
)
from app.investment_optimization.ids import (
    new_correlation_spec_id,
    new_distribution_set_id,
    new_simulation_run_id,
)
from app.investment_optimization.risk.models import CandidatePortfolio, CandidateShare
from app.investment_optimization.simulation.artifacts import write_draw_artifact
from app.investment_optimization.simulation.correlation import validate_correlation_spec
from app.investment_optimization.simulation.distributions import validate_variable
from app.investment_optimization.simulation.engine import run_engine
from app.investment_optimization.simulation.execution import SimulationExecutionAdapter
from app.investment_optimization.simulation.handoff import build_evidence_handoff
from app.investment_optimization.simulation.models import (
    MonteCarloSimulationPolicy,
    MonteCarloSimulationReceipt,
    PortfolioOutcomeDistribution,
    ScenarioCorrelationSpec,
    ScenarioDistributionSet,
    ScenarioVariableDistribution,
    SimulationEvidenceHandoff,
    SimulationRun,
    SimulationRunSpec,
)
from app.investment_optimization.simulation.policy import pin_simulation_policy
from app.investment_optimization.simulation.run_spec import compile_run_spec
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.fingerprint import metadata_fingerprint
from app.service.object_store import FakeObjectStore, ObjectStore


class SimulationService:
    def __init__(
        self,
        store: OptimizationMetadataStore,
        *,
        adapter: SimulationExecutionAdapter,
        object_store: ObjectStore | None = None,
        artifact_bucket: str = "prem3-test-artifacts",
    ) -> None:
        self._store = store
        self._adapter = adapter
        self._object_store = object_store or FakeObjectStore()
        self._artifact_bucket = artifact_bucket
        self._shares: dict[str, tuple[CandidateShare, ...]] = {}
        self._receipts: dict[str, MonteCarloSimulationReceipt] = {}
        self._handoffs: dict[str, SimulationEvidenceHandoff] = {}

    def create_distribution_set(
        self,
        *,
        tenant_id: str,
        project_id: str,
        effective_period: str,
        as_of_time: datetime,
        variables: tuple[ScenarioVariableDistribution, ...],
        approval_state: str,
        source_refs: tuple[str, ...] = (),
    ) -> ScenarioDistributionSet:
        if not variables:
            raise ScenarioDistributionNotGovernedError("A distribution set requires variables.")
        for variable in variables:
            validate_variable(variable)
        created = datetime.now(UTC)
        payload = {
            "project_id": project_id,
            "effective_period": effective_period,
            "as_of_time": as_of_time.isoformat(),
            "variables": [item.fingerprint for item in variables],
            "approval_state": approval_state,
        }
        item = ScenarioDistributionSet(
            scenario_distribution_set_id=new_distribution_set_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            effective_period=effective_period,
            as_of_time=as_of_time,
            variables=variables,
            source_refs=source_refs,
            approval_state=approval_state,
            distribution_set_fingerprint=metadata_fingerprint(payload),
            created_at=created,
        )
        existing = self._store.get_distribution_set_by_fingerprint(
            tenant_id=tenant_id,
            project_id=project_id,
            fingerprint=item.distribution_set_fingerprint,
        )
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, ScenarioDistributionSet)
        return stored

    def create_correlation_spec(
        self,
        *,
        tenant_id: str,
        project_id: str,
        authority: CorrelationAuthority,
        variable_ids: tuple[str, ...],
        matrix: tuple[tuple[float, ...], ...] = (),
        source_refs: tuple[str, ...] = (),
        model_derived_artifact_ref: str | None = None,
    ) -> ScenarioCorrelationSpec:
        created = datetime.now(UTC)
        spec = ScenarioCorrelationSpec(
            correlation_spec_id=new_correlation_spec_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            authority=authority,
            variable_ids=variable_ids,
            matrix=matrix,
            source_refs=source_refs,
            model_derived_artifact_ref=model_derived_artifact_ref,
            fingerprint=metadata_fingerprint(
                {
                    "authority": authority.value,
                    "variable_ids": list(variable_ids),
                    "matrix": [list(row) for row in matrix],
                }
            ),
            created_at=created,
        )
        validate_correlation_spec(spec)
        existing = self._store.get_correlation_by_fingerprint(fingerprint=spec.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(spec)
        assert isinstance(stored, ScenarioCorrelationSpec)
        return stored

    def create_policy(self, **kwargs: object) -> MonteCarloSimulationPolicy:
        policy = pin_simulation_policy(**kwargs)  # type: ignore[arg-type]
        existing = self._store.get_simulation_policy_by_fingerprint(fingerprint=policy.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(policy)
        assert isinstance(stored, MonteCarloSimulationPolicy)
        return stored

    def create_run_spec(self, **kwargs: object) -> SimulationRunSpec:
        spec = compile_run_spec(**kwargs)  # type: ignore[arg-type]
        existing = self._store.get_run_spec_by_fingerprint(fingerprint=spec.input_fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(spec)
        assert isinstance(stored, SimulationRunSpec)
        return stored

    def register_candidate_shares(
        self, candidate_id: str, shares: tuple[CandidateShare, ...]
    ) -> None:
        self._shares[candidate_id] = shares

    def create_run(
        self,
        *,
        spec: SimulationRunSpec,
        policy: MonteCarloSimulationPolicy,
        distribution_set: ScenarioDistributionSet,
        correlation: ScenarioCorrelationSpec,
        candidates: tuple[CandidatePortfolio, ...],
    ) -> SimulationRun:
        if spec.project_id != policy.project_id:
            raise SimulationInputNotReadyError("Run spec and policy project do not match.")
        for variable in distribution_set.variables:
            validate_variable(variable)
        validate_correlation_spec(correlation)
        if policy.outcome_evaluator is OutcomeEvaluatorKind.ACCEPTED_POSTERIOR_EVALUATION:
            if not spec.posterior_artifact_ref:
                raise PosteriorSimulationSourceUnavailableError(
                    "Accepted posterior artifact is unavailable; "
                    "missing posterior is not zero uncertainty."
                )
        for candidate in candidates:
            if candidate.candidate_portfolio_id not in spec.candidate_set_ref:
                raise SimulationCandidateInvalidError("Candidate is not in the pinned set.")
            if not candidate.feasibility_receipt_id:
                raise SimulationCandidateInvalidError(
                    "Candidate lineage or fingerprint is invalid."
                )
        existing = self._store.get_simulation_run_by_fingerprint(
            fingerprint=spec.input_fingerprint
        )
        if existing is not None:
            return existing
        created = datetime.now(UTC)
        run = SimulationRun(
            simulation_run_id=new_simulation_run_id(),
            tenant_id=spec.tenant_id,
            project_id=spec.project_id,
            run_spec_id=spec.simulation_run_spec_id,
            policy_id=policy.policy_id,
            status=SimulationRunStatus.READY,
            number_of_draws=policy.number_of_draws,
            random_seed=policy.random_seed,
            as_of_time=spec.as_of_time,
            input_fingerprint=spec.input_fingerprint,
            created_at=created,
        )
        stored = self._store.put(run)
        assert isinstance(stored, SimulationRun)
        return stored

    def execute(self, *, simulation_run_id: str) -> SimulationRun:
        run = self.get_run(simulation_run_id)
        if run.status is SimulationRunStatus.COMPLETE:
            return run
        running = run.model_copy(update={"status": SimulationRunStatus.RUNNING})
        self._store.put(running)
        try:
            self._adapter.dispatch(simulation_run_id)
        except (SimulationRuntimeUnavailableError, LiveSimulationJobProofPendingError) as exc:
            failed = running.model_copy(
                update={
                    "status": SimulationRunStatus.FAILED,
                    "failure_code": exc.code,
                }
            )
            stored = self._store.put(failed)
            assert isinstance(stored, SimulationRun)
            return stored
        refreshed = self.get_run(simulation_run_id)
        return refreshed

    def get_candidate(self, candidate_id: str) -> CandidatePortfolio | None:
        return self._store.get_candidate(candidate_id)

    def execute_inline(
        self,
        *,
        simulation_run_id: str,
        spec: SimulationRunSpec,
        policy: MonteCarloSimulationPolicy,
        distribution_set: ScenarioDistributionSet,
        correlation: ScenarioCorrelationSpec,
        candidates: tuple[CandidatePortfolio, ...],
        baseline_shares: tuple[CandidateShare, ...],
    ) -> SimulationRun:
        run = self.get_run(simulation_run_id)
        if run.status is SimulationRunStatus.COMPLETE:
            return run
        distributions, artifacts, receipt = run_engine(
            run=run,
            spec=spec,
            policy=policy,
            distribution_set=distribution_set,
            correlation=correlation,
            candidates=candidates,
            share_lookup=self._shares,
            baseline_shares=baseline_shares,
        )
        for artifact in artifacts:
            write_draw_artifact(
                artifact, object_store=self._object_store, bucket=self._artifact_bucket
            )
        for distribution in distributions:
            self._store.put(distribution)
        self._receipts[receipt.receipt_id] = receipt
        self._store.put(receipt)
        handoff = build_evidence_handoff(
            spec=spec, receipt=receipt, distributions=distributions
        )
        self._handoffs[handoff.simulation_evidence_handoff_id] = handoff
        self._store.put(handoff)
        complete = run.model_copy(
            update={
                "status": SimulationRunStatus.COMPLETE,
                "simulation_fingerprint": receipt.simulation_fingerprint,
            }
        )
        stored = self._store.put(complete)
        assert isinstance(stored, SimulationRun)
        return stored

    def get_run(self, simulation_run_id: str) -> SimulationRun:
        run = self._store.get_simulation_run(simulation_run_id)
        if run is None:
            raise SimulationNotFoundError("Simulation run was not found.")
        return run

    def get_receipt(self, simulation_run_id: str) -> MonteCarloSimulationReceipt:
        receipt = self._store.get_simulation_receipt_for_run(simulation_run_id)
        if receipt is None:
            raise SimulationNotFoundError("Simulation receipt was not found.")
        return receipt

    def get_distributions(
        self, simulation_run_id: str
    ) -> tuple[PortfolioOutcomeDistribution, ...]:
        return self._store.list_outcome_distributions(simulation_run_id=simulation_run_id)

    def get_handoff(self, simulation_run_id: str) -> SimulationEvidenceHandoff:
        handoff = self._store.get_handoff_for_run(simulation_run_id)
        if handoff is None:
            raise SimulationNotFoundError("Simulation evidence handoff was not found.")
        return handoff

    def get_distribution_set(self, set_id: str) -> ScenarioDistributionSet:
        item = self._store.get_distribution_set(set_id)
        if item is None:
            raise SimulationNotFoundError("Scenario distribution set was not found.")
        return item

    def get_correlation(self, spec_id: str) -> ScenarioCorrelationSpec:
        item = self._store.get_correlation_spec(spec_id)
        if item is None:
            raise SimulationNotFoundError("Correlation spec was not found.")
        return item

    def get_policy(self, policy_id: str) -> MonteCarloSimulationPolicy:
        item = self._store.get_simulation_policy(policy_id)
        if item is None:
            raise SimulationNotFoundError("Simulation policy was not found.")
        return item

    def get_run_spec(self, spec_id: str) -> SimulationRunSpec:
        item = self._store.get_run_spec(spec_id)
        if item is None:
            raise SimulationNotFoundError("Simulation run spec was not found.")
        return item

"""Optimization metadata store. Amount-bearing payloads cannot be put."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from app.investment_optimization.contracts import (
    OPTIMIZATION_AMOUNT_BEARING_MODELS,
    OPTIMIZATION_METADATA_MODELS,
    AdvancedOptimizationReadinessReceipt,
    ConstraintSetRef,
    ModelConsumptionContract,
    OptimizationEvidenceCoverage,
    OptimizationExecutionPlan,
    OptimizationInputContract,
    OptimizationProposal,
    OptimizationProposalRef,
    OptimizationReadinessReceipt,
    OptimizationResultRef,
    OptimizationRun,
    PlanningDecisionRecord,
    PortfolioModelMapping,
    ProposalDecisionReceipt,
    ProposalReadinessReceipt,
    ScenarioArtifact,
    ScenarioAssumptionSetRef,
)
from app.investment_optimization.risk.models import (
    RISK_AMOUNT_BEARING_MODELS,
    RISK_METADATA_MODELS,
    CandidatePortfolio,
    FeasibilityReceipt,
    FrontierSelection,
    MarketingInvestmentFrontier,
    PortfolioRiskEvaluation,
    RiskEvaluationPolicy,
    RiskNeutralParityReceipt,
)
from app.investment_optimization.simulation.models import (
    SIMULATION_AMOUNT_BEARING_MODELS,
    SIMULATION_METADATA_MODELS,
    MonteCarloSimulationPolicy,
    MonteCarloSimulationReceipt,
    PortfolioOutcomeDistribution,
    ScenarioCorrelationSpec,
    ScenarioDistributionSet,
    SimulationEvidenceHandoff,
    SimulationRun,
    SimulationRunSpec,
)
from app.investment_planning.errors import PersistenceBarrierError

OptimizationMetadata = (
    OptimizationProposalRef
    | OptimizationExecutionPlan
    | ConstraintSetRef
    | ScenarioAssumptionSetRef
    |     ModelConsumptionContract
    | PortfolioModelMapping
    | OptimizationEvidenceCoverage
    | OptimizationInputContract
    | OptimizationReadinessReceipt
    | AdvancedOptimizationReadinessReceipt
    | OptimizationRun
    | OptimizationResultRef
    | ScenarioArtifact
    | OptimizationProposal
    | ProposalReadinessReceipt
    | ProposalDecisionReceipt
    | PlanningDecisionRecord
    | RiskEvaluationPolicy
    | CandidatePortfolio
    | FeasibilityReceipt
    | PortfolioRiskEvaluation
    | MarketingInvestmentFrontier
    | FrontierSelection
    | RiskNeutralParityReceipt
    | ScenarioDistributionSet
    | ScenarioCorrelationSpec
    | MonteCarloSimulationPolicy
    | SimulationRunSpec
    | SimulationRun
    | PortfolioOutcomeDistribution
    | MonteCarloSimulationReceipt
    | SimulationEvidenceHandoff
)

FORBIDDEN_AMOUNT_KEYS = frozenset(
    {
        "total_budget",
        "recommended_allocations",
        "recommended_totals",
        "amounts",
        "allocations",
        "future_cpm_by_channel",
        "revenue_per_kpi",
        "budget_vector",
        "recommended_rows",
        "baseline_amount",
        "recommended_amount",
        "pct_of_spend",
        "fixed_budget",
        "delta",
        "share_change",
        "largest_increases",
        "largest_decreases",
        "total_budget_bounds",
        "line_bounds",
        "locked_lines",
        "movement_limits",
        "market_constraints",
        "quarter_constraints",
        "funnel_constraints",
        "experiment_reserve",
        "contingency_reserve",
        "cost_per_media_unit",
        "flighting",
        "contribution_margin",
        "target_roi",
        "target_mroi",
        "B_min",
        "B_max",
        "recommended_total",
        "total_baseline_spend",
    }
)


def _walk_forbidden(value: Any) -> None:
    if isinstance(value, Decimal):
        raise PersistenceBarrierError(
            "Decimal budget values cannot be persisted to the optimization control plane.",
            code="PLANNING_PERSISTENCE_BARRIER",
        )
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_AMOUNT_KEYS:
                raise PersistenceBarrierError(
                    f"{key} is amount-bearing and cannot be persisted.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            _walk_forbidden(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _walk_forbidden(item)


def assert_optimization_metadata_only(value: object) -> OptimizationMetadata:
    if isinstance(
        value,
        OPTIMIZATION_AMOUNT_BEARING_MODELS
        + RISK_AMOUNT_BEARING_MODELS
        + SIMULATION_AMOUNT_BEARING_MODELS,
    ):
        raise PersistenceBarrierError(
            f"{type(value).__name__} is CUSTOMER_AMOUNT_TRANSIENT and cannot be "
            "persisted to the Planning control plane.",
            code="PLANNING_PERSISTENCE_BARRIER",
        )
    if not isinstance(
        value,
        OPTIMIZATION_METADATA_MODELS + RISK_METADATA_MODELS + SIMULATION_METADATA_MODELS,
    ):
        raise PersistenceBarrierError(
            f"{type(value).__name__} is not an optimization metadata contract.",
            code="PLANNING_PERSISTENCE_BARRIER",
        )
    dumped = value.model_dump()
    _walk_forbidden(dumped)
    return value


@runtime_checkable
class OptimizationMetadataStore(Protocol):
    def put(self, value: OptimizationMetadata) -> OptimizationMetadata: ...

    def get_mapping(self, mapping_id: str) -> PortfolioModelMapping | None: ...

    def list_mappings(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[PortfolioModelMapping, ...]: ...

    def latest_mapping(
        self, *, tenant_id: str, project_id: str
    ) -> PortfolioModelMapping | None: ...

    def get_receipt(self, receipt_id: str) -> OptimizationReadinessReceipt | None: ...

    def latest_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationReadinessReceipt | None: ...

    def get_input_contract(
        self, optimization_input_id: str
    ) -> OptimizationInputContract | None: ...

    def get_coverage(self, coverage_id: str) -> OptimizationEvidenceCoverage | None: ...

    def get_consumption_for_model(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> ModelConsumptionContract | None: ...

    def get_run(self, optimization_run_id: str) -> OptimizationRun | None: ...

    def list_runs(self, *, tenant_id: str, project_id: str) -> tuple[OptimizationRun, ...]: ...

    def latest_run(self, *, tenant_id: str, project_id: str) -> OptimizationRun | None: ...

    def get_run_by_idempotency(
        self, *, tenant_id: str, project_id: str, idempotency_key: str
    ) -> OptimizationRun | None: ...

    def get_result_ref(self, result_id: str) -> OptimizationResultRef | None: ...

    def get_result_ref_for_run(self, optimization_run_id: str) -> OptimizationResultRef | None: ...

    def latest_completed_result(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationResultRef | None: ...

    def get_scenario(self, scenario_id: str) -> ScenarioArtifact | None: ...

    def list_scenarios(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ScenarioArtifact, ...]: ...

    def get_proposal(self, proposal_id: str) -> OptimizationProposal | None: ...

    def list_proposals(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[OptimizationProposal, ...]: ...

    def get_proposal_readiness(
        self, receipt_id: str
    ) -> ProposalReadinessReceipt | None: ...

    def get_proposal_readiness_for_proposal(
        self, proposal_id: str
    ) -> ProposalReadinessReceipt | None: ...

    def get_decision_receipt(
        self, decision_receipt_id: str
    ) -> ProposalDecisionReceipt | None: ...

    def get_decision_receipt_for_proposal(
        self, proposal_id: str
    ) -> ProposalDecisionReceipt | None: ...

    def get_decision_record(self, decision_id: str) -> PlanningDecisionRecord | None: ...

    def list_constraint_refs(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ConstraintSetRef, ...]: ...

    def list_assumption_refs(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ScenarioAssumptionSetRef, ...]: ...

    def list_advanced_receipts(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[AdvancedOptimizationReadinessReceipt, ...]: ...

    def get_risk_policy(self, policy_id: str) -> RiskEvaluationPolicy | None: ...

    def get_risk_policy_by_fingerprint(
        self, *, tenant_id: str, project_id: str, policy_fingerprint: str
    ) -> RiskEvaluationPolicy | None: ...

    def get_candidate(self, candidate_id: str) -> CandidatePortfolio | None: ...

    def get_candidate_by_fingerprint(
        self, *, tenant_id: str, project_id: str, candidate_fingerprint: str
    ) -> CandidatePortfolio | None: ...

    def get_evaluation(self, evaluation_id: str) -> PortfolioRiskEvaluation | None: ...

    def get_evaluation_by_fingerprint(
        self, *, evaluation_fingerprint: str
    ) -> PortfolioRiskEvaluation | None: ...

    def get_evaluation_for_candidate(
        self, candidate_id: str
    ) -> PortfolioRiskEvaluation | None: ...

    def get_frontier(self, frontier_id: str) -> MarketingInvestmentFrontier | None: ...

    def get_frontier_by_fingerprint(
        self, *, fingerprint: str
    ) -> MarketingInvestmentFrontier | None: ...

    def get_selection(self, selection_id: str) -> FrontierSelection | None: ...

    def get_selection_by_fingerprint(
        self, *, selection_fingerprint: str
    ) -> FrontierSelection | None: ...

    def get_parity_receipt(self, parity_receipt_id: str) -> RiskNeutralParityReceipt | None: ...

    def get_distribution_set(self, set_id: str) -> ScenarioDistributionSet | None: ...

    def get_distribution_set_by_fingerprint(
        self, *, tenant_id: str, project_id: str, fingerprint: str
    ) -> ScenarioDistributionSet | None: ...

    def get_correlation_spec(self, spec_id: str) -> ScenarioCorrelationSpec | None: ...

    def get_correlation_by_fingerprint(
        self, *, fingerprint: str
    ) -> ScenarioCorrelationSpec | None: ...

    def get_simulation_policy(self, policy_id: str) -> MonteCarloSimulationPolicy | None: ...

    def get_simulation_policy_by_fingerprint(
        self, *, fingerprint: str
    ) -> MonteCarloSimulationPolicy | None: ...

    def get_run_spec(self, spec_id: str) -> SimulationRunSpec | None: ...

    def get_run_spec_by_fingerprint(self, *, fingerprint: str) -> SimulationRunSpec | None: ...

    def get_simulation_run(self, simulation_run_id: str) -> SimulationRun | None: ...

    def get_simulation_run_by_fingerprint(self, *, fingerprint: str) -> SimulationRun | None: ...

    def list_outcome_distributions(
        self, *, simulation_run_id: str
    ) -> tuple[PortfolioOutcomeDistribution, ...]: ...

    def get_simulation_receipt_for_run(
        self, simulation_run_id: str
    ) -> MonteCarloSimulationReceipt | None: ...

    def get_handoff_for_run(self, simulation_run_id: str) -> SimulationEvidenceHandoff | None: ...


class InMemoryOptimizationMetadataStore:
    def __init__(self) -> None:
        self._rows: list[OptimizationMetadata] = []
        self._mappings: dict[str, PortfolioModelMapping] = {}
        self._receipts: dict[str, OptimizationReadinessReceipt] = {}
        self._inputs: dict[str, OptimizationInputContract] = {}
        self._coverage: dict[str, OptimizationEvidenceCoverage] = {}
        self._contracts: dict[str, ModelConsumptionContract] = {}
        self._runs: dict[str, OptimizationRun] = {}
        self._results: dict[str, OptimizationResultRef] = {}
        self._scenarios: dict[str, ScenarioArtifact] = {}
        self._proposals: dict[str, OptimizationProposal] = {}
        self._proposal_readiness: dict[str, ProposalReadinessReceipt] = {}
        self._decisions: dict[str, ProposalDecisionReceipt] = {}
        self._decision_records: dict[str, PlanningDecisionRecord] = {}
        self._constraint_refs: dict[str, ConstraintSetRef] = {}
        self._assumption_refs: dict[str, ScenarioAssumptionSetRef] = {}
        self._advanced_receipts: dict[str, AdvancedOptimizationReadinessReceipt] = {}
        self._risk_policies: dict[str, RiskEvaluationPolicy] = {}
        self._candidates: dict[str, CandidatePortfolio] = {}
        self._evaluations: dict[str, PortfolioRiskEvaluation] = {}
        self._frontiers: dict[str, MarketingInvestmentFrontier] = {}
        self._selections: dict[str, FrontierSelection] = {}
        self._parity: dict[str, RiskNeutralParityReceipt] = {}
        self._distribution_sets: dict[str, ScenarioDistributionSet] = {}
        self._correlations: dict[str, ScenarioCorrelationSpec] = {}
        self._simulation_policies: dict[str, MonteCarloSimulationPolicy] = {}
        self._run_specs: dict[str, SimulationRunSpec] = {}
        self._simulation_runs: dict[str, SimulationRun] = {}
        self._outcome_distributions: dict[str, PortfolioOutcomeDistribution] = {}
        self._simulation_receipts: dict[str, MonteCarloSimulationReceipt] = {}
        self._handoffs: dict[str, SimulationEvidenceHandoff] = {}

    def put(self, value: OptimizationMetadata) -> OptimizationMetadata:
        safe = assert_optimization_metadata_only(value)
        self._rows.append(safe)
        if isinstance(safe, PortfolioModelMapping):
            self._mappings[safe.mapping_id] = safe
        elif isinstance(safe, OptimizationReadinessReceipt):
            self._receipts[safe.receipt_id] = safe
        elif isinstance(safe, OptimizationInputContract):
            self._inputs[safe.optimization_input_id] = safe
        elif isinstance(safe, OptimizationEvidenceCoverage):
            self._coverage[safe.coverage_id] = safe
        elif isinstance(safe, ModelConsumptionContract):
            self._contracts[safe.consumption_contract_id] = safe
        elif isinstance(safe, OptimizationRun):
            self._runs[safe.optimization_run_id] = safe
        elif isinstance(safe, OptimizationResultRef):
            if safe.is_current:
                for result_id, existing in list(self._results.items()):
                    if (
                        existing.tenant_id == safe.tenant_id
                        and existing.project_id == safe.project_id
                        and existing.is_current
                    ):
                        self._results[result_id] = existing.model_copy(update={"is_current": False})
            self._results[safe.result_id] = safe
        elif isinstance(safe, ScenarioArtifact):
            existing_scenario = self._scenarios.get(safe.scenario_id)
            if existing_scenario is not None:
                raise PersistenceBarrierError(
                    "ScenarioArtifact is immutable after publish.",
                    code="SCENARIO_IMMUTABLE",
                )
            self._scenarios[safe.scenario_id] = safe
        elif isinstance(safe, OptimizationProposal):
            self._proposals[safe.proposal_id] = safe
        elif isinstance(safe, ProposalReadinessReceipt):
            self._proposal_readiness[safe.receipt_id] = safe
        elif isinstance(safe, ProposalDecisionReceipt):
            existing_decision = self._decisions.get(safe.decision_receipt_id)
            if existing_decision is not None:
                raise PersistenceBarrierError(
                    "ProposalDecisionReceipt is immutable.",
                    code="DECISION_RECEIPT_IMMUTABLE",
                )
            self._decisions[safe.decision_receipt_id] = safe
        elif isinstance(safe, PlanningDecisionRecord):
            existing_record = self._decision_records.get(safe.decision_id)
            if existing_record is not None:
                raise PersistenceBarrierError(
                    "PlanningDecisionRecord is immutable.",
                    code="DECISION_RECEIPT_IMMUTABLE",
                )
            self._decision_records[safe.decision_id] = safe
        elif isinstance(safe, ConstraintSetRef):
            self._constraint_refs[safe.constraint_set_id] = safe
        elif isinstance(safe, ScenarioAssumptionSetRef):
            self._assumption_refs[safe.assumption_set_id] = safe
        elif isinstance(safe, AdvancedOptimizationReadinessReceipt):
            self._advanced_receipts[safe.receipt_id] = safe
        elif isinstance(safe, RiskEvaluationPolicy):
            self._risk_policies[safe.risk_evaluation_policy_id] = safe
        elif isinstance(safe, CandidatePortfolio):
            self._candidates[safe.candidate_portfolio_id] = safe
        elif isinstance(safe, PortfolioRiskEvaluation):
            self._evaluations[safe.portfolio_risk_evaluation_id] = safe
        elif isinstance(safe, MarketingInvestmentFrontier):
            self._frontiers[safe.frontier_id] = safe
        elif isinstance(safe, FrontierSelection):
            self._selections[safe.selection_id] = safe
        elif isinstance(safe, RiskNeutralParityReceipt):
            self._parity[safe.parity_receipt_id] = safe
        elif isinstance(safe, ScenarioDistributionSet):
            self._distribution_sets[safe.scenario_distribution_set_id] = safe
        elif isinstance(safe, ScenarioCorrelationSpec):
            self._correlations[safe.correlation_spec_id] = safe
        elif isinstance(safe, MonteCarloSimulationPolicy):
            self._simulation_policies[safe.policy_id] = safe
        elif isinstance(safe, SimulationRunSpec):
            self._run_specs[safe.simulation_run_spec_id] = safe
        elif isinstance(safe, SimulationRun):
            self._simulation_runs[safe.simulation_run_id] = safe
        elif isinstance(safe, PortfolioOutcomeDistribution):
            self._outcome_distributions[safe.portfolio_outcome_distribution_id] = safe
        elif isinstance(safe, MonteCarloSimulationReceipt):
            self._simulation_receipts[safe.receipt_id] = safe
        elif isinstance(safe, SimulationEvidenceHandoff):
            self._handoffs[safe.simulation_evidence_handoff_id] = safe
        return safe

    def get_mapping(self, mapping_id: str) -> PortfolioModelMapping | None:
        return self._mappings.get(mapping_id)

    def list_mappings(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[PortfolioModelMapping, ...]:
        return tuple(
            item
            for item in self._mappings.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        )

    def latest_mapping(
        self, *, tenant_id: str, project_id: str
    ) -> PortfolioModelMapping | None:
        matches = self.list_mappings(tenant_id=tenant_id, project_id=project_id)
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_receipt(self, receipt_id: str) -> OptimizationReadinessReceipt | None:
        return self._receipts.get(receipt_id)

    def latest_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationReadinessReceipt | None:
        matches = [
            item
            for item in self._receipts.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_input_contract(
        self, optimization_input_id: str
    ) -> OptimizationInputContract | None:
        return self._inputs.get(optimization_input_id)

    def get_coverage(self, coverage_id: str) -> OptimizationEvidenceCoverage | None:
        return self._coverage.get(coverage_id)

    def get_consumption_for_model(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> ModelConsumptionContract | None:
        matches = [
            item
            for item in self._contracts.values()
            if item.tenant_id == tenant_id
            and item.project_id == project_id
            and item.model_version_id == model_version_id
        ]
        if not matches:
            return None
        return matches[-1]

    def get_run(self, optimization_run_id: str) -> OptimizationRun | None:
        return self._runs.get(optimization_run_id)

    def list_runs(self, *, tenant_id: str, project_id: str) -> tuple[OptimizationRun, ...]:
        matches = [
            item
            for item in self._runs.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def latest_run(self, *, tenant_id: str, project_id: str) -> OptimizationRun | None:
        matches = self.list_runs(tenant_id=tenant_id, project_id=project_id)
        return matches[0] if matches else None

    def get_run_by_idempotency(
        self, *, tenant_id: str, project_id: str, idempotency_key: str
    ) -> OptimizationRun | None:
        matches = [
            item
            for item in self._runs.values()
            if item.tenant_id == tenant_id
            and item.project_id == project_id
            and item.idempotency_key == idempotency_key
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_result_ref(self, result_id: str) -> OptimizationResultRef | None:
        return self._results.get(result_id)

    def get_result_ref_for_run(self, optimization_run_id: str) -> OptimizationResultRef | None:
        matches = [
            item
            for item in self._results.values()
            if item.optimization_run_id == optimization_run_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def latest_completed_result(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationResultRef | None:
        current = [
            item
            for item in self._results.values()
            if item.tenant_id == tenant_id and item.project_id == project_id and item.is_current
        ]
        if current:
            return max(current, key=lambda item: item.created_at)
        matches = [
            item
            for item in self._results.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_scenario(self, scenario_id: str) -> ScenarioArtifact | None:
        return self._scenarios.get(scenario_id)

    def list_scenarios(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ScenarioArtifact, ...]:
        matches = [
            item
            for item in self._scenarios.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def get_proposal(self, proposal_id: str) -> OptimizationProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[OptimizationProposal, ...]:
        matches = [
            item
            for item in self._proposals.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def get_proposal_readiness(self, receipt_id: str) -> ProposalReadinessReceipt | None:
        return self._proposal_readiness.get(receipt_id)

    def get_proposal_readiness_for_proposal(
        self, proposal_id: str
    ) -> ProposalReadinessReceipt | None:
        matches = [
            item
            for item in self._proposal_readiness.values()
            if item.proposal_id == proposal_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_decision_receipt(
        self, decision_receipt_id: str
    ) -> ProposalDecisionReceipt | None:
        return self._decisions.get(decision_receipt_id)

    def get_decision_receipt_for_proposal(
        self, proposal_id: str
    ) -> ProposalDecisionReceipt | None:
        matches = [
            item for item in self._decisions.values() if item.proposal_id == proposal_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_decision_record(self, decision_id: str) -> PlanningDecisionRecord | None:
        return self._decision_records.get(decision_id)

    def get_constraint_ref(self, constraint_set_id: str) -> ConstraintSetRef | None:
        return self._constraint_refs.get(constraint_set_id)

    def list_constraint_refs(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ConstraintSetRef, ...]:
        return tuple(
            item
            for item in self._constraint_refs.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        )

    def get_assumption_ref(self, assumption_set_id: str) -> ScenarioAssumptionSetRef | None:
        return self._assumption_refs.get(assumption_set_id)

    def list_assumption_refs(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ScenarioAssumptionSetRef, ...]:
        return tuple(
            item
            for item in self._assumption_refs.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        )

    def get_advanced_receipt(
        self, receipt_id: str
    ) -> AdvancedOptimizationReadinessReceipt | None:
        return self._advanced_receipts.get(receipt_id)

    def list_advanced_receipts(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[AdvancedOptimizationReadinessReceipt, ...]:
        return tuple(
            item
            for item in self._advanced_receipts.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        )

    def stored_types(self) -> tuple[str, ...]:
        return tuple(type(row).__name__ for row in self._rows)

    def get_risk_policy(self, policy_id: str) -> RiskEvaluationPolicy | None:
        return self._risk_policies.get(policy_id)

    def get_risk_policy_by_fingerprint(
        self, *, tenant_id: str, project_id: str, policy_fingerprint: str
    ) -> RiskEvaluationPolicy | None:
        for item in self._risk_policies.values():
            if (
                item.tenant_id == tenant_id
                and item.project_id == project_id
                and item.policy_fingerprint == policy_fingerprint
            ):
                return item
        return None

    def get_candidate(self, candidate_id: str) -> CandidatePortfolio | None:
        return self._candidates.get(candidate_id)

    def get_candidate_by_fingerprint(
        self, *, tenant_id: str, project_id: str, candidate_fingerprint: str
    ) -> CandidatePortfolio | None:
        for item in self._candidates.values():
            if (
                item.tenant_id == tenant_id
                and item.project_id == project_id
                and item.candidate_fingerprint == candidate_fingerprint
            ):
                return item
        return None

    def get_evaluation(self, evaluation_id: str) -> PortfolioRiskEvaluation | None:
        return self._evaluations.get(evaluation_id)

    def get_evaluation_by_fingerprint(
        self, *, evaluation_fingerprint: str
    ) -> PortfolioRiskEvaluation | None:
        for item in self._evaluations.values():
            if item.evaluation_fingerprint == evaluation_fingerprint:
                return item
        return None

    def get_evaluation_for_candidate(
        self, candidate_id: str
    ) -> PortfolioRiskEvaluation | None:
        matches = [
            item
            for item in self._evaluations.values()
            if item.candidate_portfolio_id == candidate_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_frontier(self, frontier_id: str) -> MarketingInvestmentFrontier | None:
        return self._frontiers.get(frontier_id)

    def get_frontier_by_fingerprint(
        self, *, fingerprint: str
    ) -> MarketingInvestmentFrontier | None:
        for item in self._frontiers.values():
            if item.fingerprint == fingerprint:
                return item
        return None

    def get_selection(self, selection_id: str) -> FrontierSelection | None:
        return self._selections.get(selection_id)

    def get_selection_by_fingerprint(
        self, *, selection_fingerprint: str
    ) -> FrontierSelection | None:
        for item in self._selections.values():
            if item.selection_fingerprint == selection_fingerprint:
                return item
        return None

    def get_parity_receipt(self, parity_receipt_id: str) -> RiskNeutralParityReceipt | None:
        return self._parity.get(parity_receipt_id)

    def get_distribution_set(self, set_id: str) -> ScenarioDistributionSet | None:
        return self._distribution_sets.get(set_id)

    def get_distribution_set_by_fingerprint(
        self, *, tenant_id: str, project_id: str, fingerprint: str
    ) -> ScenarioDistributionSet | None:
        for item in self._distribution_sets.values():
            if (
                item.tenant_id == tenant_id
                and item.project_id == project_id
                and item.distribution_set_fingerprint == fingerprint
            ):
                return item
        return None

    def get_correlation_spec(self, spec_id: str) -> ScenarioCorrelationSpec | None:
        return self._correlations.get(spec_id)

    def get_correlation_by_fingerprint(
        self, *, fingerprint: str
    ) -> ScenarioCorrelationSpec | None:
        for item in self._correlations.values():
            if item.fingerprint == fingerprint:
                return item
        return None

    def get_simulation_policy(self, policy_id: str) -> MonteCarloSimulationPolicy | None:
        return self._simulation_policies.get(policy_id)

    def get_simulation_policy_by_fingerprint(
        self, *, fingerprint: str
    ) -> MonteCarloSimulationPolicy | None:
        for item in self._simulation_policies.values():
            if item.fingerprint == fingerprint:
                return item
        return None

    def get_run_spec(self, spec_id: str) -> SimulationRunSpec | None:
        return self._run_specs.get(spec_id)

    def get_run_spec_by_fingerprint(self, *, fingerprint: str) -> SimulationRunSpec | None:
        for item in self._run_specs.values():
            if item.input_fingerprint == fingerprint:
                return item
        return None

    def get_simulation_run(self, simulation_run_id: str) -> SimulationRun | None:
        return self._simulation_runs.get(simulation_run_id)

    def get_simulation_run_by_fingerprint(self, *, fingerprint: str) -> SimulationRun | None:
        for item in self._simulation_runs.values():
            if item.input_fingerprint == fingerprint:
                return item
        return None

    def list_outcome_distributions(
        self, *, simulation_run_id: str
    ) -> tuple[PortfolioOutcomeDistribution, ...]:
        return tuple(
            item
            for item in self._outcome_distributions.values()
            if item.simulation_run_id == simulation_run_id
        )

    def get_simulation_receipt_for_run(
        self, simulation_run_id: str
    ) -> MonteCarloSimulationReceipt | None:
        for item in self._simulation_receipts.values():
            if item.simulation_run_id == simulation_run_id:
                return item
        return None

    def get_handoff_for_run(self, simulation_run_id: str) -> SimulationEvidenceHandoff | None:
        for item in self._handoffs.values():
            if item.simulation_run_id == simulation_run_id:
                return item
        return None

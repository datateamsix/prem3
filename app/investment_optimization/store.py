"""Optimization metadata store. Amount-bearing payloads cannot be put."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from app.investment_optimization.contracts import (
    OPTIMIZATION_AMOUNT_BEARING_MODELS,
    OPTIMIZATION_METADATA_MODELS,
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
    | OptimizationRun
    | OptimizationResultRef
    | ScenarioArtifact
    | OptimizationProposal
    | ProposalReadinessReceipt
    | ProposalDecisionReceipt
    | PlanningDecisionRecord
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
    if isinstance(value, OPTIMIZATION_AMOUNT_BEARING_MODELS):
        raise PersistenceBarrierError(
            f"{type(value).__name__} is CUSTOMER_AMOUNT_TRANSIENT and cannot be "
            "persisted to the Planning control plane.",
            code="PLANNING_PERSISTENCE_BARRIER",
        )
    if not isinstance(value, OPTIMIZATION_METADATA_MODELS):
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

    def stored_types(self) -> tuple[str, ...]:
        return tuple(type(row).__name__ for row in self._rows)

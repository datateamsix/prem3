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
    OptimizationProposalRef,
    OptimizationReadinessReceipt,
    PortfolioModelMapping,
    ScenarioAssumptionSetRef,
)
from app.investment_planning.errors import PersistenceBarrierError

OptimizationMetadata = (
    OptimizationProposalRef
    | OptimizationExecutionPlan
    | ConstraintSetRef
    | ScenarioAssumptionSetRef
    | ModelConsumptionContract
    | PortfolioModelMapping
    | OptimizationEvidenceCoverage
    | OptimizationInputContract
    | OptimizationReadinessReceipt
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


class InMemoryOptimizationMetadataStore:
    def __init__(self) -> None:
        self._rows: list[OptimizationMetadata] = []
        self._mappings: dict[str, PortfolioModelMapping] = {}
        self._receipts: dict[str, OptimizationReadinessReceipt] = {}
        self._inputs: dict[str, OptimizationInputContract] = {}
        self._coverage: dict[str, OptimizationEvidenceCoverage] = {}
        self._contracts: dict[str, ModelConsumptionContract] = {}

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

    def stored_types(self) -> tuple[str, ...]:
        return tuple(type(row).__name__ for row in self._rows)

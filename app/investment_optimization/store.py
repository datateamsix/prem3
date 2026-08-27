"""Optimization metadata store. Amount-bearing payloads cannot be put."""

from __future__ import annotations

from app.investment_optimization.contracts import (
    OPTIMIZATION_AMOUNT_BEARING_MODELS,
    OPTIMIZATION_METADATA_MODELS,
    ConstraintSetRef,
    OptimizationExecutionPlan,
    OptimizationProposalRef,
    ScenarioAssumptionSetRef,
)
from app.investment_planning.errors import PersistenceBarrierError

OptimizationMetadata = (
    OptimizationProposalRef
    | OptimizationExecutionPlan
    | ConstraintSetRef
    | ScenarioAssumptionSetRef
)


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
    return value


class InMemoryOptimizationMetadataStore:
    def __init__(self) -> None:
        self._rows: list[OptimizationMetadata] = []

    def put(self, value: OptimizationMetadata) -> OptimizationMetadata:
        safe = assert_optimization_metadata_only(value)
        self._rows.append(safe)
        return safe

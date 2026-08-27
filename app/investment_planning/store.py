"""Metadata-only Planning store. Amount-bearing models are type-rejected."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.investment_planning.contracts import (
    AMOUNT_BEARING_MODELS,
    METADATA_MODELS,
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    ExposureGuardrailRef,
    FrozenModel,
    InvestmentPlan,
    InvestmentPlanValidationReceipt,
    PortfolioDimensionMapping,
    PortfolioEvidenceCoverage,
    PortfolioObservation,
    PortfolioSnapshotRef,
    PortfolioSourceFreshness,
)
from app.investment_planning.errors import PersistenceBarrierError

InvestmentPlanningMetadata = (
    InvestmentPlan
    | BudgetDriveSourceVersion
    | BudgetColumnMapping
    | InvestmentPlanValidationReceipt
    | PortfolioDimensionMapping
    | PortfolioSnapshotRef
    | ExposureGuardrailRef
    | PortfolioEvidenceCoverage
    | PortfolioSourceFreshness
    | PortfolioObservation
)


def assert_metadata_only(value: object) -> InvestmentPlanningMetadata:
    if isinstance(value, AMOUNT_BEARING_MODELS):
        raise PersistenceBarrierError(
            f"{type(value).__name__} is CUSTOMER_AMOUNT_TRANSIENT and cannot be "
            "persisted to the Planning control plane.",
            code="PLANNING_PERSISTENCE_BARRIER",
        )
    if not isinstance(value, METADATA_MODELS):
        raise PersistenceBarrierError(
            f"{type(value).__name__} is not a Planning metadata contract.",
            code="PLANNING_PERSISTENCE_BARRIER",
        )
    return value


@runtime_checkable
class InvestmentPlanningMetadataStore(Protocol):
    def put(self, value: InvestmentPlanningMetadata) -> InvestmentPlanningMetadata: ...

    def get_plan(self, plan_id: str) -> InvestmentPlan | None: ...


class InMemoryInvestmentPlanningMetadataStore:
    """Process memory for contract tests. Not a production truth."""

    def __init__(self) -> None:
        self._plans: dict[str, InvestmentPlan] = {}
        self._rows: list[FrozenModel] = []

    def put(self, value: InvestmentPlanningMetadata) -> InvestmentPlanningMetadata:
        safe = assert_metadata_only(value)
        self._rows.append(safe)
        if isinstance(safe, InvestmentPlan):
            self._plans[safe.plan_id] = safe
        return safe

    def get_plan(self, plan_id: str) -> InvestmentPlan | None:
        return self._plans.get(plan_id)

    def stored_types(self) -> tuple[str, ...]:
        return tuple(type(row).__name__ for row in self._rows)

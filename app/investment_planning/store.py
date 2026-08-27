"""Metadata-only Planning store. Amount-bearing models are type-rejected."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.investment_planning.contracts import (
    AMOUNT_BEARING_MODELS,
    METADATA_MODELS,
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    BudgetValidationCheck,
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
    | BudgetValidationCheck
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

    def list_plans(self, *, tenant_id: str, project_id: str) -> tuple[InvestmentPlan, ...]: ...

    def get_source(self, source_version_id: str) -> BudgetDriveSourceVersion | None: ...

    def get_mapping(self, mapping_id: str) -> BudgetColumnMapping | None: ...

    def mapping_for_source(self, source_version_id: str) -> BudgetColumnMapping | None: ...

    def get_receipt(self, receipt_id: str) -> InvestmentPlanValidationReceipt | None: ...

    def latest_receipt(self, plan_id: str) -> InvestmentPlanValidationReceipt | None: ...


class InMemoryInvestmentPlanningMetadataStore:
    """Process memory for contract tests. Not a production truth."""

    def __init__(self) -> None:
        self._plans: dict[str, InvestmentPlan] = {}
        self._sources: dict[str, BudgetDriveSourceVersion] = {}
        self._mappings: dict[str, BudgetColumnMapping] = {}
        self._receipts: dict[str, InvestmentPlanValidationReceipt] = {}
        self._rows: list[FrozenModel] = []

    def put(self, value: InvestmentPlanningMetadata) -> InvestmentPlanningMetadata:
        safe = assert_metadata_only(value)
        self._rows.append(safe)
        if isinstance(safe, InvestmentPlan):
            self._plans[safe.plan_id] = safe
        elif isinstance(safe, BudgetDriveSourceVersion):
            self._sources[safe.source_version_id] = safe
        elif isinstance(safe, BudgetColumnMapping):
            self._mappings[safe.mapping_id] = safe
        elif isinstance(safe, InvestmentPlanValidationReceipt):
            self._receipts[safe.receipt_id] = safe
        return safe

    def get_plan(self, plan_id: str) -> InvestmentPlan | None:
        return self._plans.get(plan_id)

    def list_plans(self, *, tenant_id: str, project_id: str) -> tuple[InvestmentPlan, ...]:
        return tuple(
            plan
            for plan in self._plans.values()
            if plan.tenant_id == tenant_id and plan.project_id == project_id
        )

    def get_source(self, source_version_id: str) -> BudgetDriveSourceVersion | None:
        return self._sources.get(source_version_id)

    def get_mapping(self, mapping_id: str) -> BudgetColumnMapping | None:
        return self._mappings.get(mapping_id)

    def mapping_for_source(self, source_version_id: str) -> BudgetColumnMapping | None:
        matches = [
            mapping
            for mapping in self._mappings.values()
            if mapping.source_version_id == source_version_id
        ]
        if not matches:
            return None
        return matches[-1]

    def get_receipt(self, receipt_id: str) -> InvestmentPlanValidationReceipt | None:
        return self._receipts.get(receipt_id)

    def latest_receipt(self, plan_id: str) -> InvestmentPlanValidationReceipt | None:
        matches = [receipt for receipt in self._receipts.values() if receipt.plan_id == plan_id]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def stored_types(self) -> tuple[str, ...]:
        return tuple(type(row).__name__ for row in self._rows)

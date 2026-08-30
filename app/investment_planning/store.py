"""Metadata-only Planning store. Amount-bearing models are type-rejected."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.investment_planning.contracts import (
    AMOUNT_BEARING_MODELS as BASE_AMOUNT_BEARING_MODELS,
)
from app.investment_planning.contracts import (
    METADATA_MODELS as BASE_METADATA_MODELS,
)
from app.investment_planning.contracts import (
    ActualSpendQueryReceipt,
    ActualSpendSourceRef,
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
from app.investment_planning.exposure_evidence import DeliveryHealthEvidence, ExposureRiskPolicy
from app.investment_planning.exposure_guardrails import (
    ExposureGuardrail,
    ExposureGuardrailQualificationReceipt,
)
from app.investment_planning.exposure_handoff import ExposureRiskHandoff
from app.investment_planning.exposure_metrics import ExposureMetricDefinition
from app.investment_planning.exposure_observations import ExposureMetricObservation
from app.investment_planning.exposure_profile import (
    ExposureCoverageItem,
    PortfolioExposureCoverage,
    PortfolioExposureRiskProfile,
)
from app.investment_planning.exposure_scenarios import ExposureRiskScenario

METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    *BASE_METADATA_MODELS,
    ExposureMetricDefinition,
    ExposureRiskPolicy,
    DeliveryHealthEvidence,
    ExposureCoverageItem,
    PortfolioExposureCoverage,
    PortfolioExposureRiskProfile,
    ExposureGuardrail,
    ExposureGuardrailQualificationReceipt,
    ExposureRiskScenario,
    ExposureRiskHandoff,
)
AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (
    *BASE_AMOUNT_BEARING_MODELS,
    ExposureMetricObservation,
)

InvestmentPlanningMetadata = (
    InvestmentPlan
    | BudgetDriveSourceVersion
    | BudgetColumnMapping
    | BudgetValidationCheck
    | InvestmentPlanValidationReceipt
    | PortfolioDimensionMapping
    | PortfolioSnapshotRef
    | ExposureGuardrailRef
    | ActualSpendSourceRef
    | ActualSpendQueryReceipt
    | PortfolioEvidenceCoverage
    | PortfolioSourceFreshness
    | PortfolioObservation
    | ExposureMetricDefinition
    | ExposureRiskPolicy
    | DeliveryHealthEvidence
    | PortfolioExposureCoverage
    | PortfolioExposureRiskProfile
    | ExposureGuardrail
    | ExposureGuardrailQualificationReceipt
    | ExposureRiskScenario
    | ExposureRiskHandoff
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

    def get_snapshot(self, snapshot_id: str) -> PortfolioSnapshotRef | None: ...

    def latest_snapshot(
        self, *, tenant_id: str, project_id: str, fiscal_year: int | None = None
    ) -> PortfolioSnapshotRef | None: ...

    def get_actuals_source(self, actuals_source_id: str) -> ActualSpendSourceRef | None: ...


class InMemoryInvestmentPlanningMetadataStore:
    """Process memory for contract tests. Not a production truth."""

    def __init__(self) -> None:
        self._plans: dict[str, InvestmentPlan] = {}
        self._sources: dict[str, BudgetDriveSourceVersion] = {}
        self._mappings: dict[str, BudgetColumnMapping] = {}
        self._receipts: dict[str, InvestmentPlanValidationReceipt] = {}
        self._snapshots: dict[str, PortfolioSnapshotRef] = {}
        self._actuals_sources: dict[str, ActualSpendSourceRef] = {}
        self._query_receipts: dict[str, ActualSpendQueryReceipt] = {}
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
        elif isinstance(safe, PortfolioSnapshotRef):
            self._snapshots[safe.snapshot_id] = safe
        elif isinstance(safe, ActualSpendSourceRef):
            self._actuals_sources[safe.actuals_source_id] = safe
        elif isinstance(safe, ActualSpendQueryReceipt):
            self._query_receipts[safe.query_receipt_id] = safe
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

    def get_snapshot(self, snapshot_id: str) -> PortfolioSnapshotRef | None:
        return self._snapshots.get(snapshot_id)

    def latest_snapshot(
        self, *, tenant_id: str, project_id: str, fiscal_year: int | None = None
    ) -> PortfolioSnapshotRef | None:
        matches = [
            snapshot
            for snapshot in self._snapshots.values()
            if snapshot.tenant_id == tenant_id
            and snapshot.project_id == project_id
            and (fiscal_year is None or snapshot.fiscal_year == fiscal_year)
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_actuals_source(self, actuals_source_id: str) -> ActualSpendSourceRef | None:
        return self._actuals_sources.get(actuals_source_id)

    def get_query_receipt(self, query_receipt_id: str) -> ActualSpendQueryReceipt | None:
        return self._query_receipts.get(query_receipt_id)

    def stored_types(self) -> tuple[str, ...]:
        return tuple(type(row).__name__ for row in self._rows)

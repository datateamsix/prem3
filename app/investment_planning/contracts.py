"""Investment Plan and Portfolio contracts.

Firestore-safe models contain no allocation amounts. Amount-bearing views are
transient, Decimal, and classified CUSTOMER_AMOUNT_TRANSIENT.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.contracts import utc_now
from app.core.identifiers import validate_resource_identifier
from app.investment_planning.enums import (
    AmountKind,
    BudgetScope,
    BudgetSourceGrain,
    EvidenceCoverageLabel,
    ExposureGuardrailRole,
    InvestmentPlanReadyStatus,
    InvestmentPlanStatus,
    MappingMethod,
    PortfolioBaselineKind,
    SensitiveDataClass,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


_META = SensitiveDataClass.CONTROL_PLANE_METADATA
_AMOUNT = SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT


class InvestmentPlan(FrozenModel):
    """Metadata only. Declared annual budget and allocation rows stay in Drive."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    plan_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    name: str
    fiscal_year: int
    fiscal_start_month: int
    currency: str
    budget_scope: BudgetScope
    budget_scope_custom_text: str | None = None
    business_profile_snapshot_id: str
    business_profile_fingerprint: str
    active_source_version_id: str | None = None
    status: InvestmentPlanStatus
    revision: int
    predecessor_plan_id: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    approved_at: datetime | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def _project_is_workspace_alias(self) -> InvestmentPlan:
        if self.project_id != self.workspace_id:
            raise ValueError("project_id must equal workspace_id (Project/Workspace alias).")
        return self

    @model_validator(mode="after")
    def _ids(self) -> InvestmentPlan:
        validate_resource_identifier(self.plan_id, field="plan_id")
        validate_resource_identifier(self.tenant_id, field="tenant_id")
        validate_resource_identifier(self.project_id, field="project_id")
        return self


class BudgetDriveSourceVersion(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    source_version_id: str
    plan_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    drive_connection_id: str
    budgets_folder_id: str | None = None
    drive_file_id: str
    file_name: str
    mime_type: str
    drive_version: str | None = None
    head_revision_id: str | None = None
    md5_checksum: str | None = None
    modified_time: datetime | None = None
    schema_version: str
    mapping_version: str
    source_grain: BudgetSourceGrain
    predecessor_source_version_id: str | None = None
    created_at: datetime
    created_by: str

    @model_validator(mode="after")
    def _project_is_workspace_alias(self) -> BudgetDriveSourceVersion:
        if self.project_id != self.workspace_id:
            raise ValueError("project_id must equal workspace_id (Project/Workspace alias).")
        return self


class BudgetColumnMapping(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    mapping_id: str
    plan_id: str
    source_version_id: str
    market_column: str | None = None
    channel_column: str | None = None
    quarter_columns: tuple[str, ...] = ()
    initiative_column: str | None = None
    status_column: str | None = None
    mapping_method: MappingMethod = MappingMethod.EXPLICIT_USER_MAP
    confirmed: bool = False


class InvestmentPlanValidationReceipt(FrozenModel):
    """Safe row/header references only. Never cell contents or amounts."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    receipt_id: str
    plan_id: str
    source_version_id: str
    status: InvestmentPlanReadyStatus
    error_codes: tuple[str, ...] = ()
    flagged_row_indexes: tuple[int, ...] = ()
    flagged_headers: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)


class PortfolioDimensionMapping(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    mapping_id: str
    snapshot_id: str
    market_id: str
    channel_id: str
    channel_registry_version: int
    business_profile_channel_ref: str | None = None
    mmm_variable_refs: tuple[str, ...] = ()
    mta_grouping_refs: tuple[str, ...] = ()
    mapping_method: MappingMethod = MappingMethod.CHANNEL_REGISTRY


class PortfolioSnapshotRef(FrozenModel):
    """Durable metadata pointer. Amounts are never stored on this model."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    snapshot_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    fiscal_year: int
    baseline_kind: PortfolioBaselineKind
    investment_plan_id: str | None = None
    source_version_id: str | None = None
    business_profile_snapshot_id: str
    measurement_cycle_id: str | None = None
    accepted_mmm_result_ref: str | None = None
    mta_result_ref: str | None = None
    drive_artifact_file_id: str | None = None
    fingerprint: str
    created_at: datetime
    created_by: str

    @model_validator(mode="after")
    def _project_is_workspace_alias(self) -> PortfolioSnapshotRef:
        if self.project_id != self.workspace_id:
            raise ValueError("project_id must equal workspace_id (Project/Workspace alias).")
        return self


class ExposureGuardrailRef(FrozenModel):
    """Separately governed reach/frequency/exposure-integrity pointer."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    guardrail_id: str
    role: ExposureGuardrailRole
    evidence_ref: str
    methodologically_supported: bool


class PortfolioEvidenceCoverage(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    labels: tuple[EvidenceCoverageLabel, ...] = ()
    accepted_mmm: bool = False
    mta_available: bool = False
    exposure_integrity_available: bool = False
    stale: bool = False


class PortfolioSourceFreshness(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    plan_source_as_of: datetime | None = None
    actuals_as_of: datetime | None = None
    measurement_as_of: datetime | None = None


class PortfolioObservation(FrozenModel):
    """Deterministic observation code. Gemini may explain later; it does not own truth."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    code: str
    subject_market_id: str | None = None
    subject_channel_id: str | None = None
    fiscal_year: int | None = None
    quarter: int | None = None


class MoneyAmount(FrozenModel):
    """Transient Decimal amount. Missing is distinct from zero."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    kind: AmountKind
    currency: str
    value: Decimal | None
    missing: bool = False

    @model_validator(mode="after")
    def _missing_not_zero(self) -> MoneyAmount:
        if self.missing and self.value is not None:
            raise ValueError("MISSING amounts must not carry a numeric value.")
        if not self.missing and self.value is None:
            raise ValueError("Non-missing amounts require a Decimal value.")
        return self


class PortfolioAllocationView(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    fiscal_year: int
    quarter: Literal[1, 2, 3, 4]
    market_id: str
    channel_id: str
    channel_registry_version: int
    amounts: tuple[MoneyAmount, ...] = ()


class QuarterlyPortfolioView(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    fiscal_year: int
    quarter: Literal[1, 2, 3, 4]
    allocations: tuple[PortfolioAllocationView, ...] = ()


class PortfolioSummary(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    currency: str
    totals: tuple[MoneyAmount, ...] = ()


class PortfolioComparisonView(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    baseline_kind: PortfolioBaselineKind
    comparison_kind: AmountKind
    allocations: tuple[PortfolioAllocationView, ...] = ()


class PortfolioView(FrozenModel):
    """Transient assembled portfolio. Never persisted to Firestore or PreM3 GCS."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    snapshot_id: str
    tenant_id: str
    project_id: str
    fiscal_year: int
    currency: str
    baseline_kind: PortfolioBaselineKind
    summary: PortfolioSummary
    allocations: tuple[PortfolioAllocationView, ...] = ()
    quarterly: tuple[QuarterlyPortfolioView, ...] = ()
    coverage: PortfolioEvidenceCoverage
    freshness: PortfolioSourceFreshness
    observations: tuple[PortfolioObservation, ...] = ()


METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    InvestmentPlan,
    BudgetDriveSourceVersion,
    BudgetColumnMapping,
    InvestmentPlanValidationReceipt,
    PortfolioDimensionMapping,
    PortfolioSnapshotRef,
    ExposureGuardrailRef,
    PortfolioEvidenceCoverage,
    PortfolioSourceFreshness,
    PortfolioObservation,
)

AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (
    MoneyAmount,
    PortfolioAllocationView,
    QuarterlyPortfolioView,
    PortfolioSummary,
    PortfolioComparisonView,
    PortfolioView,
)

ACTUAL_SPEND_BASELINES: frozenset[PortfolioBaselineKind] = frozenset(
    {
        PortfolioBaselineKind.ACTUAL_YTD,
        PortfolioBaselineKind.GOVERNED_ACTUALS,
    }
)


def actual_spend_is_not_approved_budget(kind: PortfolioBaselineKind) -> bool:
    """Actual spend baselines are never an approved Investment Plan."""
    return kind in ACTUAL_SPEND_BASELINES

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
    ActualSpendAuthority,
    ActualSpendSourceKind,
    ActualSpendSourceStatus,
    AmountKind,
    BudgetScope,
    BudgetSourceGrain,
    EvidenceCoverageLabel,
    EvidenceCoverageScope,
    EvidenceCoverageStatus,
    ExposureGuardrailRole,
    InvestmentPlanReadyStatus,
    InvestmentPlanStatus,
    MappingMethod,
    ObservationSeverity,
    PortfolioBaselineKind,
    PortfolioObservationType,
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
    source_proposal_id: str | None = None
    source_decision_receipt_id: str | None = None
    source_scenario_id: str | None = None

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


class BudgetValidationCheck(FrozenModel):
    """Pass/fail plus safe row/header refs. Never amounts or cell contents."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    code: str
    passed: bool
    flagged_row_indexes: tuple[int, ...] = ()
    flagged_headers: tuple[str, ...] = ()


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
    checks: tuple[BudgetValidationCheck, ...] = ()
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
    actuals_source_id: str | None = None
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


class ActualSpendSourceRef(FrozenModel):
    """Firestore metadata for a governed actual-spend source. No spend rows."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    actuals_source_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    source_kind: ActualSpendSourceKind
    source_ref: str
    bq_project_id: str | None = None
    bq_dataset_id: str | None = None
    bq_table_or_view_id: str | None = None
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    as_of: datetime | None = None
    currency: str | None = None
    timezone: str | None = None
    market_mapping_version: str | None = None
    channel_registry_version: int | None = None
    authority: ActualSpendAuthority
    status: ActualSpendSourceStatus
    source_fingerprint: str
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _project_is_workspace_alias(self) -> ActualSpendSourceRef:
        if self.project_id != self.workspace_id:
            raise ValueError("project_id must equal workspace_id (Project/Workspace alias).")
        return self

    @model_validator(mode="after")
    def _ids(self) -> ActualSpendSourceRef:
        validate_resource_identifier(self.actuals_source_id, field="actuals_source_id")
        validate_resource_identifier(self.tenant_id, field="tenant_id")
        validate_resource_identifier(self.project_id, field="project_id")
        return self

    @model_validator(mode="after")
    def _test_only_is_synthetic(self) -> ActualSpendSourceRef:
        if self.authority is ActualSpendAuthority.TEST_ONLY:
            if self.source_kind is not ActualSpendSourceKind.SYNTHETIC:
                raise ValueError("TEST_ONLY actuals must use source_kind=SYNTHETIC.")
        if (
            self.source_kind is ActualSpendSourceKind.SYNTHETIC
            and self.authority is not ActualSpendAuthority.TEST_ONLY
        ):
            raise ValueError("SYNTHETIC actuals cannot be labeled customer-governed.")
        return self


class ActualSpendQueryReceipt(FrozenModel):
    """Metadata-only proof of a production actual-spend query. No amounts."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    query_receipt_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    actuals_source_id: str
    source_fingerprint: str
    period: str
    query_template_version: str
    mapping_fingerprint: str
    row_count: int
    as_of_time: datetime | None = None
    status: str
    issues: tuple[str, ...] = ()
    created_at: datetime
    fingerprint: str

    @model_validator(mode="after")
    def _project_is_workspace_alias(self) -> ActualSpendQueryReceipt:
        if self.project_id != self.workspace_id:
            raise ValueError("project_id must equal workspace_id (Project/Workspace alias).")
        return self

    @model_validator(mode="after")
    def _ids(self) -> ActualSpendQueryReceipt:
        validate_resource_identifier(self.query_receipt_id, field="query_receipt_id")
        validate_resource_identifier(self.tenant_id, field="tenant_id")
        validate_resource_identifier(self.project_id, field="project_id")
        return self

    @model_validator(mode="after")
    def _no_amount_fields(self) -> ActualSpendQueryReceipt:
        payload = self.model_dump()
        forbidden = {"amount", "spend", "allocations", "value"}
        if forbidden.intersection(payload):
            raise ValueError("ActualSpendQueryReceipt must not carry amount fields.")
        return self


class ActualSpendAllocation(FrozenModel):
    """Transient Decimal actual-spend row. Never persisted to Firestore."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    fiscal_year: int
    quarter: Literal[1, 2, 3, 4]
    market_id: str
    channel_id: str
    amount: Decimal | None
    currency: str
    source_ref: str
    as_of: datetime | None = None
    missing: bool = False

    @model_validator(mode="after")
    def _missing_not_zero(self) -> ActualSpendAllocation:
        if self.missing and self.amount is not None:
            raise ValueError("MISSING actuals must not carry a numeric value.")
        if not self.missing and self.amount is None:
            raise ValueError("Non-missing actuals require a Decimal value.")
        return self


class PortfolioEvidenceCoverageItem(FrozenModel):
    """One evidence category at an explicit scope. Metadata only."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    category: EvidenceCoverageLabel
    scope: EvidenceCoverageScope
    status: EvidenceCoverageStatus
    evidence_ref: str | None = None
    market_id: str | None = None
    channel_id: str | None = None
    fiscal_year: int | None = None
    quarter: Literal[1, 2, 3, 4] | None = None
    causal: bool = False


class PortfolioEvidenceCoverage(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    snapshot_id: str | None = None
    scope: EvidenceCoverageScope = EvidenceCoverageScope.PROJECT
    status: EvidenceCoverageStatus = EvidenceCoverageStatus.UNKNOWN
    labels: tuple[EvidenceCoverageLabel, ...] = ()
    items: tuple[PortfolioEvidenceCoverageItem, ...] = ()
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
    """Deterministic observation metadata. No amount arrays."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    observation_id: str
    project_id: str | None = None
    observation_type: PortfolioObservationType
    severity: ObservationSeverity
    subject_market_id: str | None = None
    subject_channel_id: str | None = None
    fiscal_year: int | None = None
    quarter: int | None = None
    message_key: str
    snapshot_fingerprint: str | None = None
    code: str = ""

    @model_validator(mode="after")
    def _code_matches_type(self) -> PortfolioObservation:
        if not self.code:
            object.__setattr__(self, "code", self.observation_type.value)
        return self


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
    BudgetValidationCheck,
    InvestmentPlanValidationReceipt,
    PortfolioDimensionMapping,
    PortfolioSnapshotRef,
    ExposureGuardrailRef,
    ActualSpendSourceRef,
    ActualSpendQueryReceipt,
    PortfolioEvidenceCoverageItem,
    PortfolioEvidenceCoverage,
    PortfolioSourceFreshness,
    PortfolioObservation,
)

AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (
    MoneyAmount,
    ActualSpendAllocation,
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

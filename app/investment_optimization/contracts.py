"""Optimization contracts: durable refs vs transient amount-bearing payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from app.investment_optimization.enums import (
    BudgetResolutionPath,
    DecisionRecordType,
    MappingAuthority,
    MappingCardinalityPolicy,
    MappingEntryStatus,
    MappingKind,
    MarketModelCompatibility,
    MaterialChangeFlag,
    ModelGeoSemantics,
    ModelVariableOptimizationEligibility,
    ModelVariableRole,
    OptimizationAmountKind,
    OptimizationEvidenceCoverageStatus,
    OptimizationExecutionPhase,
    OptimizationFailureClass,
    OptimizationInputStatus,
    OptimizationIssueCode,
    OptimizationObjectiveKind,
    OptimizationProposalLifecycleStatus,
    OptimizationProposalStatus,
    OptimizationReadinessCheckCode,
    OptimizationReadinessStatus,
    OptimizationRetrySemantics,
    OptimizationRunKind,
    OptimizationRunStatus,
    OptimizationSolverKind,
    OptimizerConstraintStatus,
    PortfolioModelMappingStatus,
    ProposalApprovalRole,
    ProposalDecision,
    ProposalLimitationCode,
    ProposalReadinessCheckCode,
    ProposalReadinessStatus,
    ScenarioStatus,
    ScenarioType,
    SpendSemantics,
    UnmappedVariableTreatment,
)
from app.investment_planning.contracts import MoneyAmount, PortfolioAllocationView
from app.investment_planning.enums import PortfolioBaselineKind, SensitiveDataClass


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


_META = SensitiveDataClass.CONTROL_PLANE_METADATA
_AMOUNT = SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT


class OptimizationProposalRef(FrozenModel):
    """Durable metadata. Recommended amounts live on the customer Drive artifact."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    proposal_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    baseline_snapshot_id: str
    status: OptimizationProposalStatus
    solver_kind: OptimizationSolverKind
    objective_kind: OptimizationObjectiveKind
    accepted_mmm_result_ref: str
    constraint_set_fingerprint: str
    assumption_set_fingerprint: str
    result_drive_file_id: str | None = None
    predecessor_proposal_id: str | None = None
    fingerprint: str
    created_at: datetime
    created_by: str
    approved_at: datetime | None = None
    approved_by: str | None = None


class OptimizationExecutionPlan(FrozenModel):
    """Fingerprints and refs only. Does not carry spend vectors."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    execution_plan_id: str
    proposal_id: str
    solver_kind: OptimizationSolverKind
    readiness: OptimizationReadinessStatus
    accepted_mmm_result_ref: str
    payload_fingerprint: str
    constraint_set_ref: str
    assumption_set_ref: str


class ConstraintSetRef(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    constraint_set_id: str
    fingerprint: str


class ScenarioAssumptionSetRef(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    assumption_set_id: str
    fingerprint: str


class ConstraintSetPayload(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    constraint_set_id: str
    total_budget: Decimal | None = None
    locked_line_ids: tuple[str, ...] = ()


class ScenarioAssumptionPayload(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    assumption_set_id: str
    future_cpm_by_channel: tuple[tuple[str, Decimal], ...] = ()
    revenue_per_kpi: Decimal | None = None


class OptimizationExecutionPayload(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    execution_plan_id: str
    recommended_allocations: tuple[PortfolioAllocationView, ...] = ()
    recommended_totals: tuple[MoneyAmount, ...] = ()


class OptimizationIssue(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    code: OptimizationIssueCode
    blocking: bool
    review_required: bool = False
    message_key: str
    subject_market_id: str | None = None
    subject_channel_id: str | None = None
    subject_variable_id: str | None = None


class OptimizationReadinessCheck(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    code: OptimizationReadinessCheckCode
    passed: bool


class ModelConsumptionVariable(FrozenModel):
    """One accepted-model variable. Canonical IDs are explicit bindings only."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    model_variable_id: str
    model_variable_name: str | None = None
    variable_role: ModelVariableRole
    eligibility: ModelVariableOptimizationEligibility
    spend_semantics: SpendSemantics | None = None
    canonical_channel_id: str | None = None
    canonical_market_id: str | None = None
    model_geo_scope: str | None = None


class ModelConsumptionContract(FrozenModel):
    """Planning projection of an accepted MMM. MMM remains source of truth."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    consumption_contract_id: str
    tenant_id: str
    project_id: str
    model_version_id: str
    model_plan_fingerprint: str
    model_consumption_contract_fingerprint: str
    model_acceptance_ref: str
    meridian_version: str
    runtime_mode: str
    accepted_model_state: str
    modeled_window_start: str
    modeled_window_end: str
    geo_semantics: ModelGeoSemantics
    currency: str
    kpi: str
    outcome_variable_id: str | None = None
    variables: tuple[ModelConsumptionVariable, ...] = ()
    optimizer_artifact_ref: str | None = None
    response_evidence_ref: str | None = None
    model_spec_ref: str | None = None
    future_horizon_allowed: bool = False
    complete: bool = False
    issues: tuple[OptimizationIssue, ...] = ()
    fingerprint: str


class MappingOverride(FrozenModel):
    """Governed custom mapping. Canonical IDs only; no budget amounts."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    market_id: str | None = None
    channel_id: str
    model_variable_ids: tuple[str, ...]
    authority: MappingAuthority
    policy: MappingCardinalityPolicy | None = None
    split_weights_bps: tuple[int, ...] = ()
    unmapped_treatment: UnmappedVariableTreatment | None = None


class UnmappedPortfolioCell(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    market_id: str
    channel_id: str
    issue_code: OptimizationIssueCode


class UnmappedModelVariable(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    model_variable_id: str
    treatment: UnmappedVariableTreatment
    issue_code: OptimizationIssueCode


class MappingConflict(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    kind: MappingKind
    channel_ids: tuple[str, ...] = ()
    model_variable_ids: tuple[str, ...] = ()
    issue_code: OptimizationIssueCode


class PortfolioModelMappingEntry(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    mapping_entry_id: str
    market_id: str
    channel_id: str
    model_variable_id: str
    model_variable_name: str | None = None
    model_market_ref: str | None = None
    model_geo_scope: str | None = None
    mapping_kind: MappingKind
    authority: MappingAuthority
    status: MappingEntryStatus
    market_compatibility: MarketModelCompatibility
    effective_period_start: str | None = None
    effective_period_end: str | None = None
    issues: tuple[OptimizationIssue, ...] = ()
    fingerprint: str


class PortfolioModelMapping(FrozenModel):
    """Metadata mapping. Never carries portfolio amount arrays."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    mapping_id: str
    tenant_id: str
    project_id: str
    portfolio_snapshot_id: str
    model_version_id: str
    baseline_kind: PortfolioBaselineKind = PortfolioBaselineKind.APPROVED_PLAN
    mapping_status: PortfolioModelMappingStatus
    mapping_entries: tuple[PortfolioModelMappingEntry, ...] = ()
    unmapped_portfolio_cells: tuple[UnmappedPortfolioCell, ...] = ()
    unmapped_model_variables: tuple[UnmappedModelVariable, ...] = ()
    conflicts: tuple[MappingConflict, ...] = ()
    portfolio_cells_total: int = 0
    mapped_cells: int = 0
    unmapped_cells: int = 0
    review_required_cells: int = 0
    model_variables_total: int = 0
    optimizable_model_variables: int = 0
    mapped_optimizable_variables: int = 0
    created_at: datetime
    created_by: str
    fingerprint: str

    @model_validator(mode="after")
    def _no_amount_fields(self) -> PortfolioModelMapping:
        dumped = self.model_dump()
        for key in (
            "amounts",
            "allocations",
            "total_budget",
            "recommended_allocations",
            "recommended_totals",
        ):
            if key in dumped:
                raise ValueError(f"{key} cannot appear on PortfolioModelMapping.")
        return self


class OptimizationEvidenceCoverage(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    coverage_id: str
    tenant_id: str
    project_id: str
    model_version_id: str
    portfolio_snapshot_id: str
    covered_channel_ids: tuple[str, ...] = ()
    uncovered_channel_ids: tuple[str, ...] = ()
    review_required_channel_ids: tuple[str, ...] = ()
    covered_market_ids: tuple[str, ...] = ()
    unsupported_market_ids: tuple[str, ...] = ()
    accepted_model_ref: str
    response_evidence_ref: str | None = None
    optimizer_artifact_ref: str | None = None
    mta_evidence_ref: str | None = None
    status: OptimizationEvidenceCoverageStatus
    issues: tuple[OptimizationIssue, ...] = ()
    fingerprint: str


class OptimizationInputContract(FrozenModel):
    """Metadata only. P6-05 re-resolves approved amounts from Drive/Portfolio."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    optimization_input_id: str
    tenant_id: str
    project_id: str
    portfolio_snapshot_id: str
    model_version_id: str
    mapping_id: str
    baseline_kind: PortfolioBaselineKind
    budget_period_start: str
    budget_period_end: str
    currency: str
    budget_resolution_path: BudgetResolutionPath = (
        BudgetResolutionPath.APPROVED_DRIVE_PLAN_TRANSIENT_VIEW
    )
    plan_id: str | None = None
    plan_version_fingerprint: str | None = None
    drive_file_id: str | None = None
    drive_version_fingerprint: str | None = None
    optimizable_variable_ids: tuple[str, ...] = ()
    fixed_variable_ids: tuple[str, ...] = ()
    excluded_variable_ids: tuple[str, ...] = ()
    mapping_fingerprint: str
    portfolio_fingerprint: str
    model_contract_fingerprint: str
    status: OptimizationInputStatus
    issues: tuple[OptimizationIssue, ...] = ()
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> OptimizationInputContract:
        dumped = self.model_dump()
        for key in (
            "amounts",
            "allocations",
            "total_budget",
            "recommended_allocations",
            "recommended_totals",
        ):
            if key in dumped:
                raise ValueError(f"{key} cannot appear on OptimizationInputContract.")
        return self


class OptimizationReadinessReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    receipt_id: str
    tenant_id: str
    project_id: str
    portfolio_snapshot_id: str | None = None
    model_version_id: str | None = None
    mapping_id: str | None = None
    optimization_input_id: str | None = None
    status: OptimizationReadinessStatus
    checks: tuple[OptimizationReadinessCheck, ...] = ()
    issues: tuple[OptimizationIssue, ...] = ()
    portfolio_fingerprint: str | None = None
    model_fingerprint: str | None = None
    mapping_fingerprint: str | None = None
    input_contract_fingerprint: str | None = None
    model_consumption_contract_fingerprint: str | None = None
    policy_version: str
    created_at: datetime
    expires_or_stales_on: datetime | None = None
    fingerprint: str

    @model_validator(mode="after")
    def _no_budget_values(self) -> OptimizationReadinessReceipt:
        dumped = self.model_dump()
        for key in (
            "amounts",
            "allocations",
            "total_budget",
            "recommended_allocations",
            "recommended_totals",
            "value",
        ):
            if key in dumped:
                raise ValueError(f"{key} cannot appear on OptimizationReadinessReceipt.")
        return self


def _reject_amount_keys(dumped: dict[str, object], *, owner: str) -> None:
    for key in (
        "amounts",
        "allocations",
        "total_budget",
        "recommended_allocations",
        "recommended_totals",
        "budget_vector",
        "recommended_rows",
        "baseline_amount",
        "recommended_amount",
        "pct_of_spend",
        "fixed_budget",
        "value",
    ):
        if key in dumped:
            raise ValueError(f"{key} cannot appear on {owner}.")


class OptimizationRun(FrozenModel):
    """Durable optimizer execution metadata. Never stores budget arrays."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    optimization_run_id: str
    tenant_id: str
    project_id: str
    run_kind: OptimizationRunKind = OptimizationRunKind.FIXED_BUDGET
    status: OptimizationRunStatus
    phase: OptimizationExecutionPhase | None = None
    readiness_receipt_id: str
    optimization_input_id: str | None = None
    mapping_id: str | None = None
    model_version_id: str | None = None
    portfolio_snapshot_id: str | None = None
    readiness_fingerprint: str | None = None
    input_contract_fingerprint: str | None = None
    mapping_fingerprint: str | None = None
    model_fingerprint: str | None = None
    plan_version_fingerprint: str | None = None
    runtime_version: str
    optimizer_defaults_fingerprint: str
    worker_ref: str | None = None
    artifact_object_name: str | None = None
    artifact_generation: str | None = None
    result_id: str | None = None
    result_fingerprint: str | None = None
    failure_class: OptimizationFailureClass | None = None
    failure_stage: OptimizationExecutionPhase | None = None
    retry_semantics: OptimizationRetrySemantics | None = None
    execution_key: str
    idempotency_key: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def _metadata_only(self) -> OptimizationRun:
        _reject_amount_keys(self.model_dump(), owner="OptimizationRun")
        return self


class OptimizationResultRef(FrozenModel):
    """Durable artifact pointer. Amounts live only on the GCS object."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    result_id: str
    optimization_run_id: str
    tenant_id: str
    project_id: str
    artifact_bucket: str
    artifact_object_name: str
    artifact_generation: str | None = None
    result_fingerprint: str
    schema_version: str
    runtime_version: str
    is_current: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> OptimizationResultRef:
        _reject_amount_keys(self.model_dump(), owner="OptimizationResultRef")
        return self


class OptimizerBudgetLine(FrozenModel):
    """In-memory baseline line. Never persisted."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    model_variable_id: str
    market_id: str
    channel_id: str
    baseline: Decimal
    eligibility: ModelVariableOptimizationEligibility


class OptimizerBudgetVector(FrozenModel):
    """Transient approved-plan spend vector for native Meridian."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    currency: str
    fixed_budget: Decimal
    lines: tuple[OptimizerBudgetLine, ...] = ()


class OptimizationOutcomeEstimate(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    name: str
    value: str
    amount_kind: OptimizationAmountKind = OptimizationAmountKind.MODEL_ESTIMATE


class OptimizationResultRow(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    model_variable_id: str
    market_id: str
    channel_id: str
    eligibility: ModelVariableOptimizationEligibility
    baseline: Decimal
    recommended: Decimal
    absolute_change: Decimal
    percent_change: Decimal | None = None
    percent_change_unavailable: bool = False
    constraint_status: OptimizerConstraintStatus = OptimizerConstraintStatus.WITHIN_BOUNDS
    amount_kind: OptimizationAmountKind = OptimizationAmountKind.MODEL_RECOMMENDED
    outcome_estimates: tuple[OptimizationOutcomeEstimate, ...] = ()


class OptimizationResultPayload(FrozenModel):
    """Transient amount-bearing result. Served privately; not a Firestore document."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    optimization_run_id: str
    result_id: str
    run_kind: OptimizationRunKind = OptimizationRunKind.FIXED_BUDGET
    amount_kind: OptimizationAmountKind = OptimizationAmountKind.MODEL_RECOMMENDED
    currency: str
    fixed_budget: Decimal
    recommended_total: Decimal
    rows: tuple[OptimizationResultRow, ...] = ()
    fingerprint: str
    schema_version: str


class NativeOptimizerChannelResult(FrozenModel):
    """Raw Meridian channel output before Decimal reconcile."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    model_variable_id: str
    recommended_spend: float
    outcome_estimates: tuple[OptimizationOutcomeEstimate, ...] = ()


class NativeOptimizerRawResult(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    channels: tuple[NativeOptimizerChannelResult, ...] = ()


class ScenarioArtifact(FrozenModel):
    """Durable scenario metadata. Allocation rows live on the GCS object."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    scenario_id: str
    tenant_id: str
    project_id: str
    scenario_type: ScenarioType = ScenarioType.OPTIMIZER_RECOMMENDATION
    status: ScenarioStatus = ScenarioStatus.AVAILABLE
    source_plan_id: str
    source_plan_revision: int
    source_plan_fingerprint: str
    optimization_run_id: str
    optimization_result_ref: str
    baseline_fingerprint: str
    recommendation_fingerprint: str
    period: str
    currency: str
    amount_kind: OptimizationAmountKind = OptimizationAmountKind.MODEL_RECOMMENDED
    artifact_bucket: str
    artifact_object_name: str
    artifact_generation: str | None = None
    artifact_fingerprint: str
    created_at: datetime
    created_by: str
    fingerprint: str

    @model_validator(mode="after")
    def _metadata_only(self) -> ScenarioArtifact:
        _reject_amount_keys(self.model_dump(), owner="ScenarioArtifact")
        return self


class OptimizationProposal(FrozenModel):
    """Committee proposal. Distinct from unused P6-00 OptimizationProposalRef."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    proposal_id: str
    tenant_id: str
    project_id: str
    scenario_id: str
    source_plan_id: str
    source_plan_revision: int
    source_plan_fingerprint: str
    optimization_run_id: str
    optimization_readiness_receipt_id: str
    model_version_id: str
    status: OptimizationProposalLifecycleStatus
    title: str | None = None
    summary: str | None = None
    decision_deadline: datetime | None = None
    decision_owner_user_id: str | None = None
    policy_version: str
    supersedes_proposal_id: str | None = None
    readiness_receipt_id: str | None = None
    decision_receipt_id: str | None = None
    plan_revision_plan_id: str | None = None
    submitted_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime
    created_by: str
    fingerprint: str

    @model_validator(mode="after")
    def _metadata_only(self) -> OptimizationProposal:
        _reject_amount_keys(self.model_dump(), owner="OptimizationProposal")
        return self


class ProposalReadinessCheck(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    code: ProposalReadinessCheckCode
    passed: bool


class ProposalReadinessReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    receipt_id: str
    proposal_id: str
    tenant_id: str
    project_id: str
    status: ProposalReadinessStatus
    checks: tuple[ProposalReadinessCheck, ...] = ()
    limitation_codes: tuple[ProposalLimitationCode, ...] = ()
    created_at: datetime
    fingerprint: str

    @model_validator(mode="after")
    def _metadata_only(self) -> ProposalReadinessReceipt:
        _reject_amount_keys(self.model_dump(), owner="ProposalReadinessReceipt")
        return self


class ProposalDecisionReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    decision_receipt_id: str
    proposal_id: str
    tenant_id: str
    project_id: str
    decision: ProposalDecision
    decided_by_user_id: str
    decided_at: datetime
    proposal_fingerprint: str
    scenario_fingerprint: str
    source_plan_fingerprint: str
    optimization_result_fingerprint: str
    comment: str | None = None
    reason_code: str | None = None
    created_at: datetime
    fingerprint: str

    @model_validator(mode="after")
    def _metadata_only(self) -> ProposalDecisionReceipt:
        _reject_amount_keys(self.model_dump(), owner="ProposalDecisionReceipt")
        return self


class ProposalApprovalPolicy(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    policy_version: str
    required_role: ProposalApprovalRole
    requires_distinct_plan_approval: bool
    requires_comment_on_rejection: bool
    requires_comment_on_large_change: bool = False
    approval_expiry: str | None = None


class PlanningDecisionRecord(FrozenModel):
    """Thin Decision Ledger seam. Refs only; no amounts."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    decision_id: str
    decision_type: DecisionRecordType = DecisionRecordType.OPTIMIZATION_PROPOSAL
    proposal_id: str
    tenant_id: str
    project_id: str
    decision: ProposalDecision
    owner: str
    evidence_refs: tuple[str, ...] = ()
    counter_evidence_refs: tuple[str, ...] = ()
    decided_at: datetime
    fingerprint: str

    @model_validator(mode="after")
    def _metadata_only(self) -> PlanningDecisionRecord:
        _reject_amount_keys(self.model_dump(), owner="PlanningDecisionRecord")
        return self


class ScenarioComparisonRow(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    market_id: str
    channel_id: str
    model_variable_id: str
    baseline_amount: Decimal
    recommended_amount: Decimal
    delta: Decimal
    share_change: Decimal | None = None
    percent_change: Decimal | None = None
    percent_change_unavailable: bool = False
    amount_kind: OptimizationAmountKind = OptimizationAmountKind.MODEL_RECOMMENDED
    model_estimate_delta: str | None = None


class ScenarioComparison(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    scenario_id: str
    currency: str
    amount_kind: OptimizationAmountKind = OptimizationAmountKind.MODEL_RECOMMENDED
    rows: tuple[ScenarioComparisonRow, ...] = ()
    fingerprint: str


class ProposalChangeSummary(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    proposal_id: str
    total_budget: Decimal
    changed_cell_count: int
    increase_count: int
    decrease_count: int
    unchanged_count: int
    largest_increases: tuple[ScenarioComparisonRow, ...] = ()
    largest_decreases: tuple[ScenarioComparisonRow, ...] = ()
    material_change_flags: tuple[MaterialChangeFlag, ...] = ()
    limitation_codes: tuple[ProposalLimitationCode, ...] = ()
    fingerprint: str


DEFAULT_PROPOSAL_APPROVAL_POLICY = ProposalApprovalPolicy(
    policy_version="p6-06/v1",
    required_role=ProposalApprovalRole.AUTHENTICATED_HUMAN_MEMBER,
    requires_distinct_plan_approval=True,
    requires_comment_on_rejection=True,
    requires_comment_on_large_change=False,
    approval_expiry=None,
)


OPTIMIZATION_METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    OptimizationProposalRef,
    OptimizationExecutionPlan,
    ConstraintSetRef,
    ScenarioAssumptionSetRef,
    OptimizationIssue,
    OptimizationReadinessCheck,
    ModelConsumptionVariable,
    ModelConsumptionContract,
    MappingOverride,
    UnmappedPortfolioCell,
    UnmappedModelVariable,
    MappingConflict,
    PortfolioModelMappingEntry,
    PortfolioModelMapping,
    OptimizationEvidenceCoverage,
    OptimizationInputContract,
    OptimizationReadinessReceipt,
    OptimizationRun,
    OptimizationResultRef,
    ScenarioArtifact,
    OptimizationProposal,
    ProposalReadinessCheck,
    ProposalReadinessReceipt,
    ProposalDecisionReceipt,
    ProposalApprovalPolicy,
    PlanningDecisionRecord,
)

OPTIMIZATION_AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (
    ConstraintSetPayload,
    ScenarioAssumptionPayload,
    OptimizationExecutionPayload,
    OptimizerBudgetLine,
    OptimizerBudgetVector,
    OptimizationOutcomeEstimate,
    OptimizationResultRow,
    OptimizationResultPayload,
    NativeOptimizerChannelResult,
    NativeOptimizerRawResult,
    ScenarioComparisonRow,
    ScenarioComparison,
    ProposalChangeSummary,
)


class MeridianBudgetOptimizerAdapter(Protocol):
    """P6-05 implements native Meridian BudgetOptimizer. P6-00 freezes the seam."""

    def optimize(
        self,
        plan: OptimizationExecutionPlan,
        payload: OptimizationExecutionPayload,
    ) -> OptimizationExecutionPayload: ...

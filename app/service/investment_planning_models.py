"""Presentation contracts for Investment Plan HTTP. Metadata only; no amounts."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.investment_planning.enums import BudgetScope
from app.service.models import ApiModel


class CreateInvestmentPlanRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    fiscal_year: int
    currency: str = "USD"
    budget_scope: BudgetScope = BudgetScope.PAID_MEDIA_ONLY


class BindDriveBudgetSourceRequest(ApiModel):
    drive_file_id: str = Field(min_length=1, max_length=128)


class ConfirmBudgetMappingRequest(ApiModel):
    mapping_id: str
    market_column: str | None = None
    channel_column: str | None = None
    quarter_columns: tuple[str, ...] | None = None


class ValidateInvestmentPlanRequest(ApiModel):
    mapping_id: str | None = None
    blanks_acknowledged: bool = False


class ApproveInvestmentPlanRequest(ApiModel):
    receipt_id: str


class InvestmentPlanResponse(ApiModel):
    plan_id: str
    project_id: str
    workspace_id: str
    name: str
    fiscal_year: int
    fiscal_start_month: int
    currency: str
    budget_scope: str
    business_profile_snapshot_id: str
    business_profile_fingerprint: str
    active_source_version_id: str | None = None
    status: str
    revision: int
    predecessor_plan_id: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    approved_at: datetime | None = None
    approved_by: str | None = None


class InvestmentPlanListResponse(ApiModel):
    items: tuple[InvestmentPlanResponse, ...]


class BudgetSourceResponse(ApiModel):
    source_version_id: str
    plan_id: str
    drive_file_id: str
    file_name: str
    mime_type: str
    drive_version: str | None = None
    head_revision_id: str | None = None
    md5_checksum: str | None = None
    schema_version: str
    predecessor_source_version_id: str | None = None
    created_at: datetime
    created_by: str


class BudgetMappingResponse(ApiModel):
    mapping_id: str
    plan_id: str
    source_version_id: str
    market_column: str | None = None
    channel_column: str | None = None
    quarter_columns: tuple[str, ...] = ()
    initiative_column: str | None = None
    confirmed: bool
    ambiguous: tuple[str, ...] = ()


class BudgetDriveSourceAcceptedResponse(ApiModel):
    source: BudgetSourceResponse
    mapping: BudgetMappingResponse


class InvestmentPlanValidationResponse(ApiModel):
    receipt_id: str
    plan_id: str
    source_version_id: str
    status: str
    error_codes: tuple[str, ...] = ()
    flagged_row_indexes: tuple[int, ...] = ()
    flagged_headers: tuple[str, ...] = ()


class InvestmentPlanReadyResponse(ApiModel):
    plan_id: str
    status: str
    receipt_id: str | None = None
    error_codes: tuple[str, ...] = ()


class MoneyAmountResponse(ApiModel):
    kind: str
    currency: str
    value: str | None = None
    missing: bool = False


class PortfolioAllocationResponse(ApiModel):
    fiscal_year: int
    quarter: int
    market_id: str
    channel_id: str
    channel_registry_version: int
    amounts: tuple[MoneyAmountResponse, ...] = ()


class PortfolioDimensionTotalResponse(ApiModel):
    market_id: str | None = None
    channel_id: str | None = None
    amount: MoneyAmountResponse


class QuarterlyPortfolioResponse(ApiModel):
    quarter: int
    summary: tuple[MoneyAmountResponse, ...] = ()


class PortfolioFreshnessResponse(ApiModel):
    plan_source_as_of: datetime | None = None
    actuals_as_of: datetime | None = None
    measurement_as_of: datetime | None = None


class PortfolioEvidenceCoverageItemResponse(ApiModel):
    category: str
    scope: str
    status: str
    evidence_ref: str | None = None
    market_id: str | None = None
    channel_id: str | None = None
    fiscal_year: int | None = None
    quarter: int | None = None
    causal: bool = False


class PortfolioEvidenceCoverageResponse(ApiModel):
    scope: str
    status: str
    labels: tuple[str, ...] = ()
    items: tuple[PortfolioEvidenceCoverageItemResponse, ...] = ()
    accepted_mmm: bool = False
    mta_available: bool = False
    exposure_integrity_available: bool = False
    stale: bool = False


class PortfolioObservationResponse(ApiModel):
    observation_id: str
    observation_type: str
    severity: str
    market_id: str | None = None
    channel_id: str | None = None
    fiscal_year: int | None = None
    quarter: int | None = None
    message_key: str
    snapshot_fingerprint: str | None = None


class PortfolioVarianceResponse(ApiModel):
    currency: str
    value: str | None = None
    missing: bool = True
    percent: str | None = None


class InvestmentPortfolioResponse(ApiModel):
    coverage_state: str
    snapshot_id: str | None = None
    project_id: str
    workspace_id: str
    fiscal_year: int | None = None
    currency: str | None = None
    baseline_kind: str | None = None
    actuals_source_id: str | None = None
    summary: tuple[MoneyAmountResponse, ...] = ()
    remaining: MoneyAmountResponse | None = None
    variance: PortfolioVarianceResponse | None = None
    allocations: tuple[PortfolioAllocationResponse, ...] = ()
    channel_allocation: tuple[PortfolioDimensionTotalResponse, ...] = ()
    market_allocation: tuple[PortfolioDimensionTotalResponse, ...] = ()
    quarterly: tuple[QuarterlyPortfolioResponse, ...] = ()
    coverage: PortfolioEvidenceCoverageResponse | None = None
    observations: tuple[PortfolioObservationResponse, ...] = ()
    freshness: PortfolioFreshnessResponse | None = None


class MappingOverrideRequest(ApiModel):
    market_id: str | None = None
    channel_id: str
    model_variable_ids: tuple[str, ...]
    authority: str
    policy: str | None = None
    split_weights_bps: tuple[int, ...] = ()
    unmapped_treatment: str | None = None


class CreatePortfolioModelMappingRequest(ApiModel):
    portfolio_snapshot_id: str
    model_version_id: str | None = None
    mapping_overrides: tuple[MappingOverrideRequest, ...] = ()


class EvaluateOptimizationReadinessRequest(ApiModel):
    portfolio_snapshot_id: str | None = None
    model_version_id: str | None = None
    mapping_overrides: tuple[MappingOverrideRequest, ...] = ()


class CreateOptimizationRunRequest(ApiModel):
    readiness_receipt_id: str
    idempotency_key: str | None = None


class OptimizationIssueResponse(ApiModel):
    code: str
    blocking: bool
    review_required: bool = False
    message_key: str
    market_id: str | None = None
    channel_id: str | None = None
    variable_id: str | None = None


class OptimizationReadinessCheckResponse(ApiModel):
    code: str
    passed: bool


class PortfolioModelMappingEntryResponse(ApiModel):
    mapping_entry_id: str
    market_id: str
    channel_id: str
    model_variable_id: str
    mapping_kind: str
    authority: str
    status: str
    market_compatibility: str
    fingerprint: str


class PortfolioModelMappingResponse(ApiModel):
    mapping_id: str
    project_id: str
    portfolio_snapshot_id: str
    model_version_id: str
    baseline_kind: str
    mapping_status: str
    mapping_entries: tuple[PortfolioModelMappingEntryResponse, ...] = ()
    unmapped_portfolio_cells: tuple[str, ...] = ()
    unmapped_model_variables: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    portfolio_cells_total: int = 0
    mapped_cells: int = 0
    unmapped_cells: int = 0
    review_required_cells: int = 0
    fingerprint: str
    created_at: datetime


class PortfolioModelMappingListResponse(ApiModel):
    items: tuple[PortfolioModelMappingResponse, ...]


class OptimizationCoverageSummaryResponse(ApiModel):
    status: str
    covered_channel_ids: tuple[str, ...] = ()
    uncovered_channel_ids: tuple[str, ...] = ()
    review_required_channel_ids: tuple[str, ...] = ()
    covered_market_ids: tuple[str, ...] = ()
    unsupported_market_ids: tuple[str, ...] = ()
    accepted_model_ref: str | None = None
    mta_evidence_ref: str | None = None


class OptimizationReadinessResponse(ApiModel):
    status: str
    receipt_id: str
    project_id: str
    portfolio_snapshot_id: str | None = None
    model_version_id: str | None = None
    mapping_id: str | None = None
    optimization_input_id: str | None = None
    checks: tuple[OptimizationReadinessCheckResponse, ...] = ()
    issues: tuple[OptimizationIssueResponse, ...] = ()
    coverage: OptimizationCoverageSummaryResponse | None = None
    fingerprint: str
    created_at: datetime


class OptimizationRunResponse(ApiModel):
    optimization_run_id: str
    project_id: str
    run_kind: str
    status: str
    phase: str | None = None
    readiness_receipt_id: str
    result_id: str | None = None
    failure_class: str | None = None
    retry_semantics: str | None = None
    runtime_version: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class OptimizationRunListResponse(ApiModel):
    items: tuple[OptimizationRunResponse, ...]


class OptimizationResultRowResponse(ApiModel):
    model_variable_id: str
    market_id: str
    channel_id: str
    eligibility: str
    baseline: str
    recommended: str
    absolute_change: str
    percent_change: str | None = None
    percent_change_unavailable: bool = False
    constraint_status: str
    amount_kind: str
    outcome_estimates: tuple[dict[str, str], ...] = ()


class OptimizationResultResponse(ApiModel):
    optimization_run_id: str
    result_id: str
    run_kind: str
    amount_kind: str
    currency: str
    fixed_budget: str
    recommended_total: str
    rows: tuple[OptimizationResultRowResponse, ...] = ()
    fingerprint: str
    schema_version: str


class CreateScenarioRequest(ApiModel):
    optimization_run_id: str


class ScenarioResponse(ApiModel):
    scenario_id: str
    project_id: str
    scenario_type: str
    status: str
    source_plan_id: str
    source_plan_revision: int
    optimization_run_id: str
    optimization_result_ref: str
    amount_kind: str
    currency: str
    period: str
    fingerprint: str
    created_at: datetime


class ScenarioListResponse(ApiModel):
    items: tuple[ScenarioResponse, ...]


class ScenarioComparisonRowResponse(ApiModel):
    market_id: str
    channel_id: str
    model_variable_id: str
    baseline_amount: str
    recommended_amount: str
    delta: str
    share_change: str | None = None
    percent_change: str | None = None
    percent_change_unavailable: bool = False
    amount_kind: str


class ScenarioComparisonResponse(ApiModel):
    scenario_id: str
    currency: str
    amount_kind: str
    rows: tuple[ScenarioComparisonRowResponse, ...] = ()
    fingerprint: str


class CreateProposalRequest(ApiModel):
    scenario_id: str
    title: str | None = None
    summary: str | None = None
    decision_owner_user_id: str | None = None
    supersedes_proposal_id: str | None = None


class ProposalResponse(ApiModel):
    proposal_id: str
    project_id: str
    scenario_id: str
    source_plan_id: str
    source_plan_revision: int
    optimization_run_id: str
    optimization_readiness_receipt_id: str
    model_version_id: str
    status: str
    title: str | None = None
    decision_receipt_id: str | None = None
    plan_revision_plan_id: str | None = None
    fingerprint: str
    created_at: datetime
    submitted_at: datetime | None = None
    decided_at: datetime | None = None


class ProposalListResponse(ApiModel):
    items: tuple[ProposalResponse, ...]


class ProposalDecisionRequest(ApiModel):
    action: str
    comment: str | None = None


class ProposalDecisionResponse(ApiModel):
    proposal: ProposalResponse
    decision_receipt_id: str
    decision: str
    decided_by_user_id: str
    decided_at: datetime


class PlanRevisionFromProposalResponse(ApiModel):
    plan_id: str
    predecessor_plan_id: str | None = None
    revision: int
    status: str
    source_proposal_id: str | None = None
    source_decision_receipt_id: str | None = None
    source_scenario_id: str | None = None

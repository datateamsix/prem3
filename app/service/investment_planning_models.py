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
    budget_mode: str | None = None
    objective_mode: str | None = None
    constraint_set_id: str | None = None
    assumption_set_id: str | None = None
    advanced_readiness_receipt_id: str | None = None
    target_roi: float | None = None
    target_mroi: float | None = None


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
    objective_mode: str | None = None
    budget_mode: str | None = None
    constraint_set_id: str | None = None
    assumption_set_id: str | None = None
    advanced_readiness_receipt_id: str | None = None
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
    total_baseline_spend: str | None = None
    objective_mode: str | None = None
    budget_mode: str | None = None
    target_hurdle: str | None = None
    assumption_set_id: str | None = None
    constraint_set_id: str | None = None
    binding_constraints: tuple[dict[str, str | None], ...] = ()
    model_estimated_outcome: str | None = None
    roi: str | None = None
    mroi: str | None = None
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


class MediaUnitCostRequest(ApiModel):
    ref_id: str
    kind: str
    unit: str
    currency: str
    period: str
    market_id: str | None = None
    channel_id: str
    source: str
    freshness: str
    value: str


class FlightingAssumptionRequest(ApiModel):
    ref_id: str
    market_id: str | None = None
    channel_id: str
    period: str
    weight: str
    source: str
    authority: str


class UnitValueRequest(ApiModel):
    ref_id: str
    source: str
    scope: str
    currency: str
    time_horizon: str
    freshness: str
    value: str


class CreateAssumptionSetRequest(ApiModel):
    period_start: str | None = None
    period_end: str | None = None
    cost_per_media_unit: tuple[MediaUnitCostRequest, ...] = ()
    flighting: tuple[FlightingAssumptionRequest, ...] = ()
    revenue_per_kpi: UnitValueRequest | None = None
    contribution_margin: UnitValueRequest | None = None
    source_refs: tuple[str, ...] = ()
    authority: str = "HUMAN_CONFIRMED"


class AssumptionSetRefResponse(ApiModel):
    assumption_set_id: str
    project_id: str | None = None
    fingerprint: str
    created_at: datetime | None = None


class AssumptionSetRefListResponse(ApiModel):
    items: tuple[AssumptionSetRefResponse, ...]


class ConstraintAuthorityRequest(ApiModel):
    source: str
    authority: str
    scope: str
    period: str
    reason: str


class MoneyBoundsRequest(ApiModel):
    lower: str | None = None
    upper: str | None = None
    currency: str = "USD"


class LineConstraintRequest(ApiModel):
    constraint_id: str
    family: str
    line_id: str
    market_id: str
    channel_id: str
    period: str
    lower: str | None = None
    upper: str | None = None
    currency: str = "USD"
    authority: ConstraintAuthorityRequest


class LockedLineRequest(ApiModel):
    constraint_id: str
    line_id: str
    market_id: str
    channel_id: str
    period: str
    baseline: str
    currency: str = "USD"
    reason: str
    authority: ConstraintAuthorityRequest


class MovementConstraintRequest(ApiModel):
    constraint_id: str
    family: str
    line_id: str
    market_id: str
    channel_id: str
    period: str
    max_absolute_move: str | None = None
    max_percent_move: str | None = None
    percent_unavailable: bool = False
    currency: str = "USD"
    authority: ConstraintAuthorityRequest


class GroupConstraintRequest(ApiModel):
    constraint_id: str
    family: str
    group_id: str
    member_line_ids: tuple[str, ...] = ()
    lower: str | None = None
    upper: str | None = None
    currency: str = "USD"
    period: str
    authority: ConstraintAuthorityRequest


class FunnelConstraintRequest(ApiModel):
    constraint_id: str
    family: str
    group_id: str
    member_weights: tuple[tuple[str, str], ...] = ()
    lower: str | None = None
    upper: str | None = None
    currency: str = "USD"
    period: str
    authority: ConstraintAuthorityRequest


class ReserveConstraintRequest(ApiModel):
    constraint_id: str
    family: str
    amount: str
    currency: str = "USD"
    period: str
    reason: str
    authority: ConstraintAuthorityRequest


class CreateConstraintSetRequest(ApiModel):
    currency: str = "USD"
    period_start: str | None = None
    period_end: str | None = None
    total_budget: str | None = None
    total_budget_bounds: MoneyBoundsRequest | None = None
    line_bounds: tuple[LineConstraintRequest, ...] = ()
    locked_lines: tuple[LockedLineRequest, ...] = ()
    locked_line_ids: tuple[str, ...] = ()
    movement_limits: tuple[MovementConstraintRequest, ...] = ()
    market_constraints: tuple[GroupConstraintRequest, ...] = ()
    quarter_constraints: tuple[GroupConstraintRequest, ...] = ()
    funnel_constraints: tuple[FunnelConstraintRequest, ...] = ()
    experiment_reserve: ReserveConstraintRequest | None = None
    contingency_reserve: ReserveConstraintRequest | None = None
    unsupported_channel_policies: tuple[tuple[str, str], ...] = ()


class ConstraintSetRefResponse(ApiModel):
    constraint_set_id: str
    project_id: str | None = None
    fingerprint: str
    created_at: datetime | None = None


class ConstraintSetRefListResponse(ApiModel):
    items: tuple[ConstraintSetRefResponse, ...]


class ConstraintValidationCheckResponse(ApiModel):
    code: str
    passed: bool


class ConstraintValidationResponse(ApiModel):
    validation_id: str
    constraint_set_id: str
    constraint_set_fingerprint: str
    status: str
    checks: tuple[ConstraintValidationCheckResponse, ...] = ()
    conflicting_constraint_ids: tuple[str, ...] = ()
    fingerprint: str
    created_at: datetime


class CreateAdvancedOptimizationReadinessRequest(ApiModel):
    base_readiness_receipt_id: str
    objective_mode: str
    assumption_set_id: str | None = None
    constraint_set_id: str | None = None
    target_roi: float | None = None
    target_mroi: float | None = None


class AdvancedOptimizationReadinessResponse(ApiModel):
    receipt_id: str
    project_id: str
    base_readiness_receipt_id: str
    objective_mode: str
    budget_mode: str
    assumption_set_id: str | None = None
    constraint_set_id: str | None = None
    status: str
    fingerprint: str
    created_at: datetime


class AdvancedOptimizationReadinessListResponse(ApiModel):
    items: tuple[AdvancedOptimizationReadinessResponse, ...]


class ExposureCoverageItemResponse(ApiModel):
    dimension: str
    status: str
    observed_count: int
    expected_count: int | None = None


class ExposureCoverageResponse(ApiModel):
    project_id: str
    period: str
    overall_status: str
    items: tuple[ExposureCoverageItemResponse, ...]
    fingerprint: str
    source_ready: bool


class ExposureRiskProfileResponse(ApiModel):
    profile_id: str
    project_id: str
    period: str
    market_id: str | None = None
    channel_id: str | None = None
    risk_flags: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    role_eligibility: tuple[str, ...] = ()
    coverage: ExposureCoverageResponse
    fingerprint: str
    source_ready: bool


class ExposureGuardrailResponse(ApiModel):
    guardrail_id: str
    metric_id: str
    role: str
    assigned_role: str | None = None
    issues: tuple[str, ...] = ()
    fingerprint: str


class QualifyExposureGuardrailRequest(ApiModel):
    metric_id: str
    role: str
    market_id: str | None = None
    channel_id: str | None = None
    period: str = "FY2027Q1"


class CreateExposureScenarioRequest(ApiModel):
    period: str
    scope: str = "portfolio"
    source_rationale: str
    metric_id: str
    delta_kind: str
    delta_ref: str
    rationale: str


class ExposureScenarioResponse(ApiModel):
    scenario_id: str
    project_id: str
    period: str
    scope: str
    source_rationale: str
    fingerprint: str


class CreateRiskEvaluationPolicyRequest(ApiModel):
    objective: str
    model_version_ref: str
    optimization_readiness_ref: str
    future_assumption_set_ref: str | None = None
    constraint_set_ref: str | None = None
    exposure_risk_handoff_ref: str | None = None
    tail_probability: float = 0.05
    risk_penalties_enabled: bool = True
    minimum_candidate_count: int = 3


class RiskEvaluationPolicyResponse(ApiModel):
    risk_evaluation_policy_id: str
    project_id: str
    policy_version: str
    objective: str
    policy_fingerprint: str


class CreateRiskCandidatesRequest(ApiModel):
    risk_evaluation_policy_id: str
    optimization_run_id: str
    base_approved_plan_ref: str
    input_fingerprint: str
    native_shares: tuple[dict[str, float | str], ...]


class CandidatePortfolioResponse(ApiModel):
    candidate_portfolio_id: str
    optimization_run_id: str
    native_optimum: bool
    candidate_fingerprint: str
    allocation_fingerprint: str


class CreateRiskEvaluationsRequest(ApiModel):
    risk_evaluation_policy_id: str
    candidate_ids: tuple[str, ...]
    baseline_shares: tuple[dict[str, float | str], ...]
    candidate_draws: dict[str, tuple[float, ...]] | None = None
    baseline_draws: tuple[float, ...] | None = None


class PortfolioRiskEvaluationResponse(ApiModel):
    portfolio_risk_evaluation_id: str
    candidate_portfolio_id: str
    expected_outcome: float | None
    lower_tail_metric: float | None
    limitations: tuple[str, ...]
    evaluation_fingerprint: str


class CreateFrontierRequest(ApiModel):
    risk_evaluation_policy_id: str
    evaluation_ids: tuple[str, ...]
    parity_receipt_id: str | None = None


class FrontierResponse(ApiModel):
    frontier_id: str
    non_dominated_candidate_ids: tuple[str, ...]
    readiness: str
    fingerprint: str


class SelectFrontierRequest(ApiModel):
    risk_posture: str


class FrontierSelectionResponse(ApiModel):
    selection_id: str
    frontier_id: str
    selected_candidate_ref: str
    risk_posture: str
    state: str
    selection_fingerprint: str
    parity_receipt_id: str | None = None


class ParityReceiptResponse(ApiModel):
    parity_receipt_id: str
    matched: bool
    native_allocation_fingerprint: str
    selected_allocation_fingerprint: str
    fingerprint: str


class CreateScenarioVariableRequest(ApiModel):
    semantic_type: str
    family: str
    parameters: dict[str, float | list[float]]
    source_authority: str
    source_refs: tuple[str, ...]
    unit: str = "1"
    scope: str = "portfolio"
    time_scope: str = "FY2027Q1"
    channel_id: str | None = None
    approval_state: str = "APPROVED"


class CreateDistributionSetRequest(ApiModel):
    effective_period: str
    as_of_time: str
    variables: tuple[CreateScenarioVariableRequest, ...]
    approval_state: str = "APPROVED"
    source_refs: tuple[str, ...] = ()


class DistributionSetResponse(ApiModel):
    scenario_distribution_set_id: str
    distribution_set_fingerprint: str
    approval_state: str


class CreateCorrelationSpecRequest(ApiModel):
    authority: str
    variable_ids: tuple[str, ...]
    matrix: tuple[tuple[float, ...], ...] = ()
    source_refs: tuple[str, ...] = ()


class CorrelationSpecResponse(ApiModel):
    correlation_spec_id: str
    authority: str
    fingerprint: str


class CreateSimulationPolicyRequest(ApiModel):
    number_of_draws: int
    random_seed: int
    batch_size: int
    distribution_set_ref: str
    correlation_spec_ref: str
    candidate_set_ref: tuple[str, ...]
    as_of_time: str
    variable_count: int
    tail_probability: float = 0.05


class SimulationPolicyResponse(ApiModel):
    policy_id: str
    fingerprint: str
    number_of_draws: int


class CreateSimulationRunSpecRequest(ApiModel):
    baseline_ref: str
    policy_id: str
    model_version_ref: str
    posterior_artifact_ref: str | None = None
    future_assumption_set_ref: str | None = None
    exposure_risk_handoff_ref: str | None = None


class SimulationRunSpecResponse(ApiModel):
    simulation_run_spec_id: str
    input_fingerprint: str
    as_of_time: str


class CreateSimulationRunRequest(ApiModel):
    run_spec_id: str


class SimulationRunResponse(ApiModel):
    simulation_run_id: str
    status: str
    input_fingerprint: str
    failure_code: str | None = None


class SimulationReceiptResponse(ApiModel):
    receipt_id: str
    simulation_run_id: str
    status: str
    draw_count: int
    simulation_fingerprint: str


class OutcomeDistributionResponse(ApiModel):
    portfolio_outcome_distribution_id: str
    candidate_portfolio_id: str
    mean: float
    median: float
    distribution_artifact_ref: str


class SimulationHandoffResponse(ApiModel):
    simulation_evidence_handoff_id: str
    simulation_run_id: str
    as_of_time: str
    input_fingerprint: str
    simulation_fingerprint: str
    limitations: tuple[str, ...]

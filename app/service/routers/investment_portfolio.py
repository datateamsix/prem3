"""Project-scoped Investment Portfolio API. Amounts are transient and private."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.control_plane.models import Workspace
from app.core.tenancy import require_tenant
from app.investment_optimization.contracts import (
    MappingOverride,
    OptimizationReadinessReceipt,
    PortfolioModelMapping,
    ScenarioArtifact,
)
from app.investment_optimization.enums import (
    MappingAuthority,
    MappingCardinalityPolicy,
    ProposalDecision,
    UnmappedVariableTreatment,
)
from app.investment_optimization.mapping import reject_forbidden_authority
from app.investment_optimization.proposal import ProposalGovernanceService
from app.investment_optimization.run_service import OptimizationRunService
from app.investment_optimization.service import OptimizationReadinessService
from app.investment_planning.contracts import (
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioSnapshotRef,
    PortfolioView,
)
from app.investment_planning.enums import AmountKind, PortfolioCoverageState
from app.investment_planning.errors import PlanningError
from app.investment_planning.portfolio import (
    remaining_amount,
    rollup_by_dimension,
    summarize_allocations,
    variance_amount,
    variance_percent,
)
from app.investment_planning.service import InvestmentPlanService
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    CreateOptimizationRunRequest,
    CreatePortfolioModelMappingRequest,
    CreateProposalRequest,
    CreateScenarioRequest,
    EvaluateOptimizationReadinessRequest,
    InvestmentPortfolioResponse,
    MappingOverrideRequest,
    MoneyAmountResponse,
    OptimizationCoverageSummaryResponse,
    OptimizationIssueResponse,
    OptimizationReadinessCheckResponse,
    OptimizationReadinessResponse,
    OptimizationResultResponse,
    OptimizationResultRowResponse,
    OptimizationRunListResponse,
    OptimizationRunResponse,
    PlanRevisionFromProposalResponse,
    PortfolioAllocationResponse,
    PortfolioDimensionTotalResponse,
    PortfolioEvidenceCoverageItemResponse,
    PortfolioEvidenceCoverageResponse,
    PortfolioFreshnessResponse,
    PortfolioModelMappingEntryResponse,
    PortfolioModelMappingListResponse,
    PortfolioModelMappingResponse,
    PortfolioObservationResponse,
    PortfolioVarianceResponse,
    ProposalDecisionRequest,
    ProposalDecisionResponse,
    ProposalListResponse,
    ProposalResponse,
    QuarterlyPortfolioResponse,
    ScenarioComparisonResponse,
    ScenarioComparisonRowResponse,
    ScenarioListResponse,
    ScenarioResponse,
)
from app.service.routers.investment_planning import (
    authorized_planning_scope,
    get_investment_planning,
    private_no_store,
)

canonical_portfolio_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-portfolio",
    tags=["investment-portfolio"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_portfolio_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-portfolio",
    tags=["investment-portfolio"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def _amount_response(amount: MoneyAmount) -> MoneyAmountResponse:
    return MoneyAmountResponse(
        kind=amount.kind.value,
        currency=amount.currency,
        value=None if amount.value is None else format(amount.value, "f"),
        missing=amount.missing,
    )


def _allocation_response(row: PortfolioAllocationView) -> PortfolioAllocationResponse:
    return PortfolioAllocationResponse(
        fiscal_year=row.fiscal_year,
        quarter=row.quarter,
        market_id=row.market_id,
        channel_id=row.channel_id,
        channel_registry_version=row.channel_registry_version,
        amounts=tuple(_amount_response(amount) for amount in row.amounts),
    )


def _portfolio_response(
    *,
    project_id: str,
    coverage_state: str,
    snapshot: PortfolioSnapshotRef | None,
    view: PortfolioView | None,
) -> InvestmentPortfolioResponse:
    snapshot_id = None if snapshot is None else snapshot.snapshot_id
    actuals_source_id = None if snapshot is None else snapshot.actuals_source_id
    if view is None:
        return InvestmentPortfolioResponse(
            coverage_state=coverage_state,
            snapshot_id=snapshot_id,
            project_id=project_id,
            workspace_id=project_id,
            actuals_source_id=actuals_source_id,
        )
    amount_kind = view.summary.totals[0].kind if view.summary.totals else AmountKind.APPROVED
    remaining = remaining_amount(view.allocations, currency=view.currency)
    if coverage_state == PortfolioCoverageState.ACTUALS_ONLY.value:
        remaining = remaining.model_copy(update={"missing": True, "value": None})
    variance = variance_amount(view.allocations, currency=view.currency)
    approved_total = next(
        (
            item
            for item in view.summary.totals
            if item.kind is AmountKind.APPROVED and not item.missing
        ),
        None,
    )
    actual_total = next(
        (
            item
            for item in view.summary.totals
            if item.kind is AmountKind.ACTUAL and not item.missing
        ),
        None,
    )
    percent = variance_percent(
        None if approved_total is None else approved_total.value,
        None if actual_total is None else actual_total.value,
    )
    if coverage_state != PortfolioCoverageState.PLAN_AND_ACTUALS.value:
        variance = variance.model_copy(update={"missing": True, "value": None})
        percent = None
    channel_rows = rollup_by_dimension(
        view.allocations, currency=view.currency, kind=amount_kind, by="channel"
    )
    market_rows = rollup_by_dimension(
        view.allocations, currency=view.currency, kind=amount_kind, by="market"
    )
    return InvestmentPortfolioResponse(
        coverage_state=coverage_state,
        snapshot_id=view.snapshot_id,
        project_id=view.project_id,
        workspace_id=view.project_id,
        fiscal_year=view.fiscal_year,
        currency=view.currency,
        baseline_kind=view.baseline_kind.value,
        actuals_source_id=actuals_source_id,
        summary=tuple(_amount_response(amount) for amount in view.summary.totals),
        remaining=_amount_response(remaining),
        variance=PortfolioVarianceResponse(
            currency=view.currency,
            value=(
                None
                if variance.missing or variance.value is None
                else format(variance.value, "f")
            ),
            missing=variance.missing,
            percent=None if percent is None else format(percent, "f"),
        ),
        allocations=tuple(_allocation_response(row) for row in view.allocations),
        channel_allocation=tuple(
            PortfolioDimensionTotalResponse(
                market_id=row.market_id,
                channel_id=row.channel_id,
                amount=_amount_response(row.amount),
            )
            for row in channel_rows
        ),
        market_allocation=tuple(
            PortfolioDimensionTotalResponse(
                market_id=row.market_id,
                channel_id=row.channel_id,
                amount=_amount_response(row.amount),
            )
            for row in market_rows
        ),
        quarterly=tuple(
            QuarterlyPortfolioResponse(
                quarter=bucket.quarter,
                summary=tuple(
                    _amount_response(amount)
                    for amount in summarize_allocations(
                        bucket.allocations, currency=view.currency, kind=amount_kind
                    ).totals
                ),
            )
            for bucket in view.quarterly
        ),
        coverage=PortfolioEvidenceCoverageResponse(
            scope=view.coverage.scope.value,
            status=view.coverage.status.value,
            labels=tuple(label.value for label in view.coverage.labels),
            items=tuple(
                PortfolioEvidenceCoverageItemResponse(
                    category=item.category.value,
                    scope=item.scope.value,
                    status=item.status.value,
                    evidence_ref=item.evidence_ref,
                    market_id=item.market_id,
                    channel_id=item.channel_id,
                    fiscal_year=item.fiscal_year,
                    quarter=item.quarter,
                    causal=item.causal,
                )
                for item in view.coverage.items
            ),
            accepted_mmm=view.coverage.accepted_mmm,
            mta_available=view.coverage.mta_available,
            exposure_integrity_available=view.coverage.exposure_integrity_available,
            stale=view.coverage.stale,
        ),
        observations=tuple(
            PortfolioObservationResponse(
                observation_id=item.observation_id,
                observation_type=item.observation_type.value,
                severity=item.severity.value,
                market_id=item.subject_market_id,
                channel_id=item.subject_channel_id,
                fiscal_year=item.fiscal_year,
                quarter=item.quarter,
                message_key=item.message_key,
                snapshot_fingerprint=item.snapshot_fingerprint,
            )
            for item in view.observations
        ),
        freshness=PortfolioFreshnessResponse(
            plan_source_as_of=view.freshness.plan_source_as_of,
            actuals_as_of=view.freshness.actuals_as_of,
            measurement_as_of=view.freshness.measurement_as_of,
        ),
    )


async def get_portfolio(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
    fiscal_year: Annotated[int | None, Query()] = None,
) -> InvestmentPortfolioResponse:
    try:
        state, snapshot, view = service.assemble_portfolio(
            project_id=workspace.workspace_id,
            fiscal_year=fiscal_year,
            actor_id=require_tenant().user_id or "unknown",
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _portfolio_response(
        project_id=workspace.workspace_id,
        coverage_state=state.value,
        snapshot=snapshot,
        view=view,
    )


canonical_portfolio_router.add_api_route(
    "",
    get_portfolio,
    methods=["GET"],
    operation_id="getInvestmentPortfolio",
    response_model=InvestmentPortfolioResponse,
)
workspace_alias_portfolio_router.add_api_route(
    "",
    get_portfolio,
    methods=["GET"],
    operation_id="getInvestmentPortfolioWorkspaceAlias",
    response_model=InvestmentPortfolioResponse,
    include_in_schema=False,
)


def get_optimization_readiness_service(request: Request) -> OptimizationReadinessService:
    service = getattr(request.app.state, "optimization_readiness", None)
    if service is None:
        raise RuntimeError("Optimization readiness service is not configured.")
    return service


def get_optimization_run_service(request: Request) -> OptimizationRunService:
    service = getattr(request.app.state, "optimization_runs", None)
    if service is None:
        raise RuntimeError("Optimization execution service is not configured.")
    return service


def get_proposal_governance(request: Request) -> ProposalGovernanceService:
    service = getattr(request.app.state, "proposal_governance", None)
    if service is None:
        raise RuntimeError("Proposal governance service is not configured.")
    return service


def _overrides(items: tuple[MappingOverrideRequest, ...]) -> tuple[MappingOverride, ...]:
    parsed: list[MappingOverride] = []
    for item in items:
        reject_forbidden_authority(item.authority)
        parsed.append(
            MappingOverride(
                market_id=item.market_id,
                channel_id=item.channel_id,
                model_variable_ids=item.model_variable_ids,
                authority=MappingAuthority(item.authority),
                policy=None if item.policy is None else MappingCardinalityPolicy(item.policy),
                split_weights_bps=item.split_weights_bps,
                unmapped_treatment=(
                    None
                    if item.unmapped_treatment is None
                    else UnmappedVariableTreatment(item.unmapped_treatment)
                ),
            )
        )
    return tuple(parsed)


def _mapping_response(mapping: PortfolioModelMapping) -> PortfolioModelMappingResponse:
    return PortfolioModelMappingResponse(
        mapping_id=mapping.mapping_id,
        project_id=mapping.project_id,
        portfolio_snapshot_id=mapping.portfolio_snapshot_id,
        model_version_id=mapping.model_version_id,
        baseline_kind=mapping.baseline_kind.value,
        mapping_status=mapping.mapping_status.value,
        mapping_entries=tuple(
            PortfolioModelMappingEntryResponse(
                mapping_entry_id=entry.mapping_entry_id,
                market_id=entry.market_id,
                channel_id=entry.channel_id,
                model_variable_id=entry.model_variable_id,
                mapping_kind=entry.mapping_kind.value,
                authority=entry.authority.value,
                status=entry.status.value,
                market_compatibility=entry.market_compatibility.value,
                fingerprint=entry.fingerprint,
            )
            for entry in mapping.mapping_entries
        ),
        unmapped_portfolio_cells=tuple(
            f"{cell.market_id}:{cell.channel_id}" for cell in mapping.unmapped_portfolio_cells
        ),
        unmapped_model_variables=tuple(
            item.model_variable_id for item in mapping.unmapped_model_variables
        ),
        conflicts=tuple(item.issue_code.value for item in mapping.conflicts),
        portfolio_cells_total=mapping.portfolio_cells_total,
        mapped_cells=mapping.mapped_cells,
        unmapped_cells=mapping.unmapped_cells,
        review_required_cells=mapping.review_required_cells,
        fingerprint=mapping.fingerprint,
        created_at=mapping.created_at,
    )


def _readiness_response(
    receipt: OptimizationReadinessReceipt,
    *,
    coverage: OptimizationCoverageSummaryResponse | None = None,
) -> OptimizationReadinessResponse:
    return OptimizationReadinessResponse(
        status=receipt.status.value,
        receipt_id=receipt.receipt_id,
        project_id=receipt.project_id,
        portfolio_snapshot_id=receipt.portfolio_snapshot_id,
        model_version_id=receipt.model_version_id,
        mapping_id=receipt.mapping_id,
        optimization_input_id=receipt.optimization_input_id,
        checks=tuple(
            OptimizationReadinessCheckResponse(code=item.code.value, passed=item.passed)
            for item in receipt.checks
        ),
        issues=tuple(
            OptimizationIssueResponse(
                code=item.code.value,
                blocking=item.blocking,
                review_required=item.review_required,
                message_key=item.message_key,
                market_id=item.subject_market_id,
                channel_id=item.subject_channel_id,
                variable_id=item.subject_variable_id,
            )
            for item in receipt.issues
        ),
        coverage=coverage,
        fingerprint=receipt.fingerprint,
        created_at=receipt.created_at,
    )


async def create_model_mapping(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[
        OptimizationReadinessService, Depends(get_optimization_readiness_service)
    ],
    body: CreatePortfolioModelMappingRequest,
) -> PortfolioModelMappingResponse:
    try:
        mapping = service.create_mapping(
            project_id=workspace.workspace_id,
            portfolio_snapshot_id=body.portfolio_snapshot_id,
            actor_id=require_tenant().user_id or "unknown",
            model_version_id=body.model_version_id,
            mapping_overrides=_overrides(body.mapping_overrides),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _mapping_response(mapping)


async def list_model_mappings(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[
        OptimizationReadinessService, Depends(get_optimization_readiness_service)
    ],
) -> PortfolioModelMappingListResponse:
    try:
        items = service.list_mappings(project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return PortfolioModelMappingListResponse(items=tuple(_mapping_response(item) for item in items))


async def get_model_mapping(
    mapping_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[
        OptimizationReadinessService, Depends(get_optimization_readiness_service)
    ],
) -> PortfolioModelMappingResponse:
    try:
        mapping = service.get_mapping(mapping_id=mapping_id, project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _mapping_response(mapping)


async def get_optimization_readiness(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[
        OptimizationReadinessService, Depends(get_optimization_readiness_service)
    ],
) -> OptimizationReadinessResponse:
    try:
        receipt = service.get_readiness(project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _readiness_response(receipt)


async def evaluate_optimization_readiness(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[
        OptimizationReadinessService, Depends(get_optimization_readiness_service)
    ],
    body: EvaluateOptimizationReadinessRequest,
) -> OptimizationReadinessResponse:
    try:
        receipt = service.evaluate(
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
            portfolio_snapshot_id=body.portfolio_snapshot_id,
            model_version_id=body.model_version_id,
            mapping_overrides=_overrides(body.mapping_overrides),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _readiness_response(receipt)


def _run_response(run) -> OptimizationRunResponse:
    return OptimizationRunResponse(
        optimization_run_id=run.optimization_run_id,
        project_id=run.project_id,
        run_kind=run.run_kind.value,
        status=run.status.value,
        phase=None if run.phase is None else run.phase.value,
        readiness_receipt_id=run.readiness_receipt_id,
        result_id=run.result_id,
        failure_class=None if run.failure_class is None else run.failure_class.value,
        retry_semantics=None if run.retry_semantics is None else run.retry_semantics.value,
        runtime_version=run.runtime_version,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def _result_response(payload) -> OptimizationResultResponse:
    return OptimizationResultResponse(
        optimization_run_id=payload.optimization_run_id,
        result_id=payload.result_id,
        run_kind=payload.run_kind.value,
        amount_kind=payload.amount_kind.value,
        currency=payload.currency,
        fixed_budget=format(payload.fixed_budget, "f"),
        recommended_total=format(payload.recommended_total, "f"),
        rows=tuple(
            OptimizationResultRowResponse(
                model_variable_id=row.model_variable_id,
                market_id=row.market_id,
                channel_id=row.channel_id,
                eligibility=row.eligibility.value,
                baseline=format(row.baseline, "f"),
                recommended=format(row.recommended, "f"),
                absolute_change=format(row.absolute_change, "f"),
                percent_change=(
                    None if row.percent_change is None else format(row.percent_change, "f")
                ),
                percent_change_unavailable=row.percent_change_unavailable,
                constraint_status=row.constraint_status.value,
                amount_kind=row.amount_kind.value,
                outcome_estimates=tuple(
                    {"name": item.name, "value": item.value, "amount_kind": item.amount_kind.value}
                    for item in row.outcome_estimates
                ),
            )
            for row in payload.rows
        ),
        fingerprint=payload.fingerprint,
        schema_version=payload.schema_version,
    )


async def create_optimization_run(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[OptimizationRunService, Depends(get_optimization_run_service)],
    body: CreateOptimizationRunRequest,
) -> OptimizationRunResponse:
    try:
        run = service.create_run(
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
            readiness_receipt_id=body.readiness_receipt_id,
            idempotency_key=body.idempotency_key,
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _run_response(run)


async def list_optimization_runs(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[OptimizationRunService, Depends(get_optimization_run_service)],
) -> OptimizationRunListResponse:
    try:
        items = service.list_runs(project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return OptimizationRunListResponse(items=tuple(_run_response(item) for item in items))


async def get_optimization_run(
    optimization_run_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[OptimizationRunService, Depends(get_optimization_run_service)],
) -> OptimizationRunResponse:
    try:
        run = service.get_run(
            optimization_run_id=optimization_run_id, project_id=workspace.workspace_id
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _run_response(run)


async def get_optimization_result(
    optimization_run_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[OptimizationRunService, Depends(get_optimization_run_service)],
) -> OptimizationResultResponse:
    try:
        payload = service.get_result(
            optimization_run_id=optimization_run_id, project_id=workspace.workspace_id
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _result_response(payload)


def _scenario_response(item: ScenarioArtifact) -> ScenarioResponse:
    return ScenarioResponse(
        scenario_id=item.scenario_id,
        project_id=item.project_id,
        scenario_type=item.scenario_type.value,
        status=item.status.value,
        source_plan_id=item.source_plan_id,
        source_plan_revision=item.source_plan_revision,
        optimization_run_id=item.optimization_run_id,
        optimization_result_ref=item.optimization_result_ref,
        amount_kind=item.amount_kind.value,
        currency=item.currency,
        period=item.period,
        fingerprint=item.fingerprint,
        created_at=item.created_at,
    )


def _proposal_response(item) -> ProposalResponse:
    return ProposalResponse(
        proposal_id=item.proposal_id,
        project_id=item.project_id,
        scenario_id=item.scenario_id,
        source_plan_id=item.source_plan_id,
        source_plan_revision=item.source_plan_revision,
        optimization_run_id=item.optimization_run_id,
        optimization_readiness_receipt_id=item.optimization_readiness_receipt_id,
        model_version_id=item.model_version_id,
        status=item.status.value,
        title=item.title,
        decision_receipt_id=item.decision_receipt_id,
        plan_revision_plan_id=item.plan_revision_plan_id,
        fingerprint=item.fingerprint,
        created_at=item.created_at,
        submitted_at=item.submitted_at,
        decided_at=item.decided_at,
    )


async def create_scenario(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
    body: CreateScenarioRequest,
) -> ScenarioResponse:
    try:
        item = service.create_scenario(
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
            optimization_run_id=body.optimization_run_id,
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _scenario_response(item)


async def list_scenarios(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ScenarioListResponse:
    try:
        items = service.list_scenarios(project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return ScenarioListResponse(items=tuple(_scenario_response(item) for item in items))


async def get_scenario(
    scenario_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ScenarioResponse:
    try:
        item = service.get_scenario(scenario_id=scenario_id, project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _scenario_response(item)


async def get_scenario_comparison(
    scenario_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ScenarioComparisonResponse:
    try:
        comparison = service.get_comparison(
            scenario_id=scenario_id, project_id=workspace.workspace_id
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return ScenarioComparisonResponse(
        scenario_id=comparison.scenario_id,
        currency=comparison.currency,
        amount_kind=comparison.amount_kind.value,
        rows=tuple(
            ScenarioComparisonRowResponse(
                market_id=row.market_id,
                channel_id=row.channel_id,
                model_variable_id=row.model_variable_id,
                baseline_amount=format(row.baseline_amount, "f"),
                recommended_amount=format(row.recommended_amount, "f"),
                delta=format(row.delta, "f"),
                share_change=None if row.share_change is None else format(row.share_change, "f"),
                percent_change=(
                    None if row.percent_change is None else format(row.percent_change, "f")
                ),
                percent_change_unavailable=row.percent_change_unavailable,
                amount_kind=row.amount_kind.value,
            )
            for row in comparison.rows
        ),
        fingerprint=comparison.fingerprint,
    )


async def create_proposal(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
    body: CreateProposalRequest,
) -> ProposalResponse:
    try:
        item = service.create_proposal(
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
            scenario_id=body.scenario_id,
            title=body.title,
            summary=body.summary,
            decision_owner_user_id=body.decision_owner_user_id,
            supersedes_proposal_id=body.supersedes_proposal_id,
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _proposal_response(item)


async def list_proposals(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ProposalListResponse:
    try:
        items = service.list_proposals(project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return ProposalListResponse(items=tuple(_proposal_response(item) for item in items))


async def get_proposal(
    proposal_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ProposalResponse:
    try:
        item = service.get_proposal(proposal_id=proposal_id, project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _proposal_response(item)


async def submit_proposal(
    proposal_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ProposalResponse:
    try:
        item = service.submit_proposal(
            proposal_id=proposal_id,
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _proposal_response(item)


async def review_proposal(
    proposal_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> ProposalResponse:
    try:
        item = service.review_proposal(
            proposal_id=proposal_id,
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _proposal_response(item)


async def decide_proposal(
    proposal_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
    body: ProposalDecisionRequest,
) -> ProposalDecisionResponse:
    try:
        proposal, receipt = service.decide(
            proposal_id=proposal_id,
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
            decision=ProposalDecision(body.action),
            comment=body.comment,
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return ProposalDecisionResponse(
        proposal=_proposal_response(proposal),
        decision_receipt_id=receipt.decision_receipt_id,
        decision=receipt.decision.value,
        decided_by_user_id=receipt.decided_by_user_id,
        decided_at=receipt.decided_at,
    )


async def create_plan_revision_from_proposal(
    proposal_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[ProposalGovernanceService, Depends(get_proposal_governance)],
) -> PlanRevisionFromProposalResponse:
    try:
        plan = service.create_plan_revision_from_proposal(
            proposal_id=proposal_id,
            project_id=workspace.workspace_id,
            actor_id=require_tenant().user_id or "unknown",
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return PlanRevisionFromProposalResponse(
        plan_id=plan.plan_id,
        predecessor_plan_id=plan.predecessor_plan_id,
        revision=plan.revision,
        status=plan.status.value,
        source_proposal_id=plan.source_proposal_id,
        source_decision_receipt_id=plan.source_decision_receipt_id,
        source_scenario_id=plan.source_scenario_id,
    )


canonical_portfolio_router.add_api_route(
    "/model-mapping",
    create_model_mapping,
    methods=["POST"],
    operation_id="createPortfolioModelMapping",
    response_model=PortfolioModelMappingResponse,
)
canonical_portfolio_router.add_api_route(
    "/model-mapping",
    list_model_mappings,
    methods=["GET"],
    operation_id="listPortfolioModelMappings",
    response_model=PortfolioModelMappingListResponse,
)
canonical_portfolio_router.add_api_route(
    "/model-mapping/{mapping_id}",
    get_model_mapping,
    methods=["GET"],
    operation_id="getPortfolioModelMapping",
    response_model=PortfolioModelMappingResponse,
)
canonical_portfolio_router.add_api_route(
    "/optimization-readiness",
    get_optimization_readiness,
    methods=["GET"],
    operation_id="getOptimizationReadiness",
    response_model=OptimizationReadinessResponse,
)
canonical_portfolio_router.add_api_route(
    "/optimization-readiness/evaluate",
    evaluate_optimization_readiness,
    methods=["POST"],
    operation_id="evaluateOptimizationReadiness",
    response_model=OptimizationReadinessResponse,
)
canonical_portfolio_router.add_api_route(
    "/optimizations",
    create_optimization_run,
    methods=["POST"],
    status_code=202,
    operation_id="createOptimizationRun",
    response_model=OptimizationRunResponse,
)
canonical_portfolio_router.add_api_route(
    "/optimizations",
    list_optimization_runs,
    methods=["GET"],
    operation_id="listOptimizationRuns",
    response_model=OptimizationRunListResponse,
)
canonical_portfolio_router.add_api_route(
    "/optimizations/{optimization_run_id}",
    get_optimization_run,
    methods=["GET"],
    operation_id="getOptimizationRun",
    response_model=OptimizationRunResponse,
)
canonical_portfolio_router.add_api_route(
    "/optimizations/{optimization_run_id}/result",
    get_optimization_result,
    methods=["GET"],
    operation_id="getOptimizationResult",
    response_model=OptimizationResultResponse,
)
canonical_portfolio_router.add_api_route(
    "/scenarios",
    create_scenario,
    methods=["POST"],
    status_code=201,
    operation_id="createOptimizationScenario",
    response_model=ScenarioResponse,
)
canonical_portfolio_router.add_api_route(
    "/scenarios",
    list_scenarios,
    methods=["GET"],
    operation_id="listOptimizationScenarios",
    response_model=ScenarioListResponse,
)
canonical_portfolio_router.add_api_route(
    "/scenarios/{scenario_id}",
    get_scenario,
    methods=["GET"],
    operation_id="getOptimizationScenario",
    response_model=ScenarioResponse,
)
canonical_portfolio_router.add_api_route(
    "/scenarios/{scenario_id}/comparison",
    get_scenario_comparison,
    methods=["GET"],
    operation_id="getOptimizationScenarioComparison",
    response_model=ScenarioComparisonResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals",
    create_proposal,
    methods=["POST"],
    status_code=201,
    operation_id="createOptimizationProposal",
    response_model=ProposalResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals",
    list_proposals,
    methods=["GET"],
    operation_id="listOptimizationProposals",
    response_model=ProposalListResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals/{proposal_id}",
    get_proposal,
    methods=["GET"],
    operation_id="getOptimizationProposal",
    response_model=ProposalResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/submit",
    submit_proposal,
    methods=["POST"],
    operation_id="submitOptimizationProposal",
    response_model=ProposalResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/review",
    review_proposal,
    methods=["POST"],
    operation_id="reviewOptimizationProposal",
    response_model=ProposalResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/decision",
    decide_proposal,
    methods=["POST"],
    operation_id="decideOptimizationProposal",
    response_model=ProposalDecisionResponse,
)
canonical_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/create-plan-revision",
    create_plan_revision_from_proposal,
    methods=["POST"],
    status_code=201,
    operation_id="createPlanRevisionFromProposal",
    response_model=PlanRevisionFromProposalResponse,
)
workspace_alias_portfolio_router.add_api_route(
    "/model-mapping",
    create_model_mapping,
    methods=["POST"],
    operation_id="createPortfolioModelMappingWorkspaceAlias",
    response_model=PortfolioModelMappingResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/model-mapping",
    list_model_mappings,
    methods=["GET"],
    operation_id="listPortfolioModelMappingsWorkspaceAlias",
    response_model=PortfolioModelMappingListResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/model-mapping/{mapping_id}",
    get_model_mapping,
    methods=["GET"],
    operation_id="getPortfolioModelMappingWorkspaceAlias",
    response_model=PortfolioModelMappingResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/optimization-readiness",
    get_optimization_readiness,
    methods=["GET"],
    operation_id="getOptimizationReadinessWorkspaceAlias",
    response_model=OptimizationReadinessResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/optimization-readiness/evaluate",
    evaluate_optimization_readiness,
    methods=["POST"],
    operation_id="evaluateOptimizationReadinessWorkspaceAlias",
    response_model=OptimizationReadinessResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/optimizations",
    create_optimization_run,
    methods=["POST"],
    status_code=202,
    operation_id="createOptimizationRunWorkspaceAlias",
    response_model=OptimizationRunResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/optimizations",
    list_optimization_runs,
    methods=["GET"],
    operation_id="listOptimizationRunsWorkspaceAlias",
    response_model=OptimizationRunListResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/optimizations/{optimization_run_id}",
    get_optimization_run,
    methods=["GET"],
    operation_id="getOptimizationRunWorkspaceAlias",
    response_model=OptimizationRunResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/optimizations/{optimization_run_id}/result",
    get_optimization_result,
    methods=["GET"],
    operation_id="getOptimizationResultWorkspaceAlias",
    response_model=OptimizationResultResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/scenarios",
    create_scenario,
    methods=["POST"],
    status_code=201,
    operation_id="createOptimizationScenarioWorkspaceAlias",
    response_model=ScenarioResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/scenarios",
    list_scenarios,
    methods=["GET"],
    operation_id="listOptimizationScenariosWorkspaceAlias",
    response_model=ScenarioListResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/scenarios/{scenario_id}",
    get_scenario,
    methods=["GET"],
    operation_id="getOptimizationScenarioWorkspaceAlias",
    response_model=ScenarioResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/scenarios/{scenario_id}/comparison",
    get_scenario_comparison,
    methods=["GET"],
    operation_id="getOptimizationScenarioComparisonWorkspaceAlias",
    response_model=ScenarioComparisonResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals",
    create_proposal,
    methods=["POST"],
    status_code=201,
    operation_id="createOptimizationProposalWorkspaceAlias",
    response_model=ProposalResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals",
    list_proposals,
    methods=["GET"],
    operation_id="listOptimizationProposalsWorkspaceAlias",
    response_model=ProposalListResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals/{proposal_id}",
    get_proposal,
    methods=["GET"],
    operation_id="getOptimizationProposalWorkspaceAlias",
    response_model=ProposalResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/submit",
    submit_proposal,
    methods=["POST"],
    operation_id="submitOptimizationProposalWorkspaceAlias",
    response_model=ProposalResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/review",
    review_proposal,
    methods=["POST"],
    operation_id="reviewOptimizationProposalWorkspaceAlias",
    response_model=ProposalResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/decision",
    decide_proposal,
    methods=["POST"],
    operation_id="decideOptimizationProposalWorkspaceAlias",
    response_model=ProposalDecisionResponse,
    include_in_schema=False,
)
workspace_alias_portfolio_router.add_api_route(
    "/proposals/{proposal_id}/create-plan-revision",
    create_plan_revision_from_proposal,
    methods=["POST"],
    status_code=201,
    operation_id="createPlanRevisionFromProposalWorkspaceAlias",
    response_model=PlanRevisionFromProposalResponse,
    include_in_schema=False,
)

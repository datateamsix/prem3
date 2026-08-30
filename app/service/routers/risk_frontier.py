"""P6-09 risk-frontier routes. Server computes; client cannot submit scores."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Feature, Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.investment_optimization.enums import RiskPosture
from app.investment_optimization.errors import OptimizationError
from app.investment_optimization.risk.models import CandidateShare
from app.investment_optimization.risk.service import RiskFrontierService
from app.service.dependencies import get_control_plane
from app.service.entitlements import require_feature
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    CandidatePortfolioResponse,
    CreateFrontierRequest,
    CreateRiskCandidatesRequest,
    CreateRiskEvaluationPolicyRequest,
    CreateRiskEvaluationsRequest,
    FrontierResponse,
    FrontierSelectionResponse,
    ParityReceiptResponse,
    PortfolioRiskEvaluationResponse,
    RiskEvaluationPolicyResponse,
    SelectFrontierRequest,
)
from app.service.routers.investment_planning import (
    authorized_planning_scope,
    private_no_store,
)

canonical_risk_frontier_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-portfolio/risk-frontier",
    tags=["investment-portfolio"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_risk_frontier_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-portfolio/risk-frontier",
    tags=["investment-portfolio"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def get_risk_frontier_service(request: Request) -> RiskFrontierService:
    service = getattr(request.app.state, "risk_frontier", None)
    if service is None:
        raise RuntimeError("Risk frontier service is not configured.")
    return service


async def authorized_risk_scope(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> Workspace:
    require_feature(repo, Feature.PORTFOLIO_VIEW)
    return workspace


def _shares(rows: tuple[dict[str, float | str], ...]) -> tuple[CandidateShare, ...]:
    return tuple(
        CandidateShare(channel_id=str(row["channel_id"]), share=float(row["share"]))
        for row in rows
    )


def _reject_client_authority(body: object) -> None:
    dumped = body.model_dump() if hasattr(body, "model_dump") else {}
    forbidden = {
        "cvar",
        "hhi",
        "dominance",
        "frontier_membership",
        "selected_outcome",
        "portfolio_risk_score",
        "posterior_draws",
    }
    if any(key in dumped for key in forbidden):
        raise OptimizationError("Client cannot supply authoritative risk calculations.")


async def create_policy(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    body: CreateRiskEvaluationPolicyRequest,
) -> RiskEvaluationPolicyResponse:
    _reject_client_authority(body)
    service = get_risk_frontier_service(request)
    try:
        policy = service.create_policy(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            objective=body.objective,
            model_version_ref=body.model_version_ref,
            optimization_readiness_ref=body.optimization_readiness_ref,
            future_assumption_set_ref=body.future_assumption_set_ref,
            constraint_set_ref=body.constraint_set_ref,
            exposure_risk_handoff_ref=body.exposure_risk_handoff_ref,
            tail_probability=body.tail_probability,
            risk_penalties_enabled=body.risk_penalties_enabled,
            minimum_candidate_count=body.minimum_candidate_count,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return RiskEvaluationPolicyResponse(
        risk_evaluation_policy_id=policy.risk_evaluation_policy_id,
        project_id=policy.project_id,
        policy_version=policy.policy_version,
        objective=policy.objective,
        policy_fingerprint=policy.policy_fingerprint,
    )


async def get_policy(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    policy_id: str,
) -> RiskEvaluationPolicyResponse:
    del workspace
    try:
        policy = get_risk_frontier_service(request).get_policy(policy_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return RiskEvaluationPolicyResponse(
        risk_evaluation_policy_id=policy.risk_evaluation_policy_id,
        project_id=policy.project_id,
        policy_version=policy.policy_version,
        objective=policy.objective,
        policy_fingerprint=policy.policy_fingerprint,
    )


async def create_candidates(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    body: CreateRiskCandidatesRequest,
) -> tuple[CandidatePortfolioResponse, ...]:
    _reject_client_authority(body)
    service = get_risk_frontier_service(request)
    try:
        policy = service.get_policy(body.risk_evaluation_policy_id)
        if policy.project_id != workspace.workspace_id:
            raise OptimizationError("Risk policy is not in this project.")
        candidates = service.generate(
            policy=policy,
            native_shares=_shares(body.native_shares),
            optimization_run_id=body.optimization_run_id,
            base_approved_plan_ref=body.base_approved_plan_ref,
            input_fingerprint=body.input_fingerprint,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return tuple(
        CandidatePortfolioResponse(
            candidate_portfolio_id=item.candidate_portfolio_id,
            optimization_run_id=item.optimization_run_id,
            native_optimum=item.native_optimum,
            candidate_fingerprint=item.candidate_fingerprint,
            allocation_fingerprint=item.allocation_fingerprint,
        )
        for item in candidates
    )


async def get_candidate(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    candidate_id: str,
) -> CandidatePortfolioResponse:
    del workspace
    try:
        item = get_risk_frontier_service(request).get_candidate(candidate_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return CandidatePortfolioResponse(
        candidate_portfolio_id=item.candidate_portfolio_id,
        optimization_run_id=item.optimization_run_id,
        native_optimum=item.native_optimum,
        candidate_fingerprint=item.candidate_fingerprint,
        allocation_fingerprint=item.allocation_fingerprint,
    )


async def create_evaluations(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    body: CreateRiskEvaluationsRequest,
) -> tuple[PortfolioRiskEvaluationResponse, ...]:
    del workspace
    _reject_client_authority(body)
    service = get_risk_frontier_service(request)
    try:
        policy = service.get_policy(body.risk_evaluation_policy_id)
        results = []
        for candidate_id in body.candidate_ids:
            candidate = service.get_candidate(candidate_id)
            draws = None if body.candidate_draws is None else body.candidate_draws.get(candidate_id)
            results.append(
                service.evaluate(
                    policy=policy,
                    candidate=candidate,
                    baseline_shares=_shares(body.baseline_shares),
                    candidate_draws=draws,
                    baseline_draws=body.baseline_draws,
                )
            )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return tuple(
        PortfolioRiskEvaluationResponse(
            portfolio_risk_evaluation_id=item.portfolio_risk_evaluation_id,
            candidate_portfolio_id=item.candidate_portfolio_id,
            expected_outcome=item.expected_outcome,
            lower_tail_metric=item.lower_tail_metric,
            limitations=item.limitations,
            evaluation_fingerprint=item.evaluation_fingerprint,
        )
        for item in results
    )


async def get_evaluation(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    evaluation_id: str,
) -> PortfolioRiskEvaluationResponse:
    del workspace
    try:
        item = get_risk_frontier_service(request).get_evaluation(evaluation_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return PortfolioRiskEvaluationResponse(
        portfolio_risk_evaluation_id=item.portfolio_risk_evaluation_id,
        candidate_portfolio_id=item.candidate_portfolio_id,
        expected_outcome=item.expected_outcome,
        lower_tail_metric=item.lower_tail_metric,
        limitations=item.limitations,
        evaluation_fingerprint=item.evaluation_fingerprint,
    )


async def create_frontier(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    body: CreateFrontierRequest,
) -> FrontierResponse:
    del workspace
    _reject_client_authority(body)
    service = get_risk_frontier_service(request)
    try:
        policy = service.get_policy(body.risk_evaluation_policy_id)
        evaluations = tuple(service.get_evaluation(item) for item in body.evaluation_ids)
        parity = (
            None
            if body.parity_receipt_id is None
            else service.get_parity(body.parity_receipt_id)
        )
        frontier = service.build_frontier(
            policy=policy, evaluations=evaluations, parity=parity
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return FrontierResponse(
        frontier_id=frontier.frontier_id,
        non_dominated_candidate_ids=frontier.non_dominated_candidate_ids,
        readiness=frontier.readiness.value,
        fingerprint=frontier.fingerprint,
    )


async def get_frontier(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    frontier_id: str,
) -> FrontierResponse:
    del workspace
    try:
        frontier = get_risk_frontier_service(request).get_frontier(frontier_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return FrontierResponse(
        frontier_id=frontier.frontier_id,
        non_dominated_candidate_ids=frontier.non_dominated_candidate_ids,
        readiness=frontier.readiness.value,
        fingerprint=frontier.fingerprint,
    )


async def select_frontier(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    frontier_id: str,
    body: SelectFrontierRequest,
) -> FrontierSelectionResponse:
    del workspace
    _reject_client_authority(body)
    service = get_risk_frontier_service(request)
    try:
        frontier = service.get_frontier(frontier_id)
        policy = service.get_policy(frontier.risk_evaluation_policy_id)
        evaluations = service.evaluations_for_candidates(frontier.evaluated_candidate_ids)
        candidates = tuple(
            service.get_candidate(item_id) for item_id in frontier.evaluated_candidate_ids
        )
        native = next((item for item in candidates if item.native_optimum), None)
        selection, parity = service.select(
            frontier=frontier,
            evaluations=evaluations,
            policy=policy,
            posture=RiskPosture(body.risk_posture),
            native_candidate=native,
            candidates=candidates,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return FrontierSelectionResponse(
        selection_id=selection.selection_id,
        frontier_id=selection.frontier_id,
        selected_candidate_ref=selection.selected_candidate_ref,
        risk_posture=selection.risk_posture.value,
        state=selection.state.value,
        selection_fingerprint=selection.selection_fingerprint,
        parity_receipt_id=None if parity is None else parity.parity_receipt_id,
    )


async def get_selection(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    frontier_id: str,
    selection_id: str,
) -> FrontierSelectionResponse:
    del workspace, frontier_id
    try:
        selection = get_risk_frontier_service(request).get_selection(selection_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return FrontierSelectionResponse(
        selection_id=selection.selection_id,
        frontier_id=selection.frontier_id,
        selected_candidate_ref=selection.selected_candidate_ref,
        risk_posture=selection.risk_posture.value,
        state=selection.state.value,
        selection_fingerprint=selection.selection_fingerprint,
        parity_receipt_id=None,
    )


async def get_parity(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_risk_scope)],
    parity_id: str,
) -> ParityReceiptResponse:
    del workspace
    try:
        receipt = get_risk_frontier_service(request).get_parity(parity_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return ParityReceiptResponse(
        parity_receipt_id=receipt.parity_receipt_id,
        matched=receipt.matched,
        native_allocation_fingerprint=receipt.native_allocation_fingerprint,
        selected_allocation_fingerprint=receipt.selected_allocation_fingerprint,
        fingerprint=receipt.fingerprint,
    )


for _router in (canonical_risk_frontier_router, workspace_alias_risk_frontier_router):
    _router.add_api_route(
        "/risk-evaluation-policies",
        create_policy,
        methods=["POST"],
        response_model=RiskEvaluationPolicyResponse,
        operation_id="createRiskEvaluationPolicy"
        if _router is canonical_risk_frontier_router
        else "createRiskEvaluationPolicyWorkspace",
    )
    _router.add_api_route(
        "/risk-evaluation-policies/{policy_id}",
        get_policy,
        methods=["GET"],
        response_model=RiskEvaluationPolicyResponse,
        operation_id="getRiskEvaluationPolicy"
        if _router is canonical_risk_frontier_router
        else "getRiskEvaluationPolicyWorkspace",
    )
    _router.add_api_route(
        "/candidates",
        create_candidates,
        methods=["POST"],
        response_model=tuple[CandidatePortfolioResponse, ...],
        operation_id="createRiskCandidates"
        if _router is canonical_risk_frontier_router
        else "createRiskCandidatesWorkspace",
    )
    _router.add_api_route(
        "/candidates/{candidate_id}",
        get_candidate,
        methods=["GET"],
        response_model=CandidatePortfolioResponse,
        operation_id="getRiskCandidate"
        if _router is canonical_risk_frontier_router
        else "getRiskCandidateWorkspace",
    )
    _router.add_api_route(
        "/evaluations",
        create_evaluations,
        methods=["POST"],
        response_model=tuple[PortfolioRiskEvaluationResponse, ...],
        operation_id="createRiskEvaluations"
        if _router is canonical_risk_frontier_router
        else "createRiskEvaluationsWorkspace",
    )
    _router.add_api_route(
        "/evaluations/{evaluation_id}",
        get_evaluation,
        methods=["GET"],
        response_model=PortfolioRiskEvaluationResponse,
        operation_id="getRiskEvaluation"
        if _router is canonical_risk_frontier_router
        else "getRiskEvaluationWorkspace",
    )
    _router.add_api_route(
        "/frontiers",
        create_frontier,
        methods=["POST"],
        response_model=FrontierResponse,
        operation_id="createRiskFrontier"
        if _router is canonical_risk_frontier_router
        else "createRiskFrontierWorkspace",
    )
    _router.add_api_route(
        "/frontiers/{frontier_id}",
        get_frontier,
        methods=["GET"],
        response_model=FrontierResponse,
        operation_id="getRiskFrontier"
        if _router is canonical_risk_frontier_router
        else "getRiskFrontierWorkspace",
    )
    _router.add_api_route(
        "/frontiers/{frontier_id}/select",
        select_frontier,
        methods=["POST"],
        response_model=FrontierSelectionResponse,
        operation_id="selectRiskFrontier"
        if _router is canonical_risk_frontier_router
        else "selectRiskFrontierWorkspace",
    )
    _router.add_api_route(
        "/frontiers/{frontier_id}/selections/{selection_id}",
        get_selection,
        methods=["GET"],
        response_model=FrontierSelectionResponse,
        operation_id="getRiskFrontierSelection"
        if _router is canonical_risk_frontier_router
        else "getRiskFrontierSelectionWorkspace",
    )
    _router.add_api_route(
        "/parity-receipts/{parity_id}",
        get_parity,
        methods=["GET"],
        response_model=ParityReceiptResponse,
        operation_id="getRiskNeutralParityReceipt"
        if _router is canonical_risk_frontier_router
        else "getRiskNeutralParityReceiptWorkspace",
    )

"""P6-10 outcome routes. Server computes; clients cannot submit scores."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Feature, Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.investment_optimization.enums import OutcomeSemanticType, OutcomeSourceAuthority
from app.investment_optimization.errors import OptimizationError
from app.investment_optimization.risk.models import CandidateShare
from app.investment_planning.outcomes.service import OutcomeService
from app.service.dependencies import get_control_plane
from app.service.entitlements import require_feature
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    BindInvestmentDecisionRequest,
    CreateExecutionAdherenceRequest,
    CreateLearningReceiptRequest,
    CreateOutcomeObservationRequest,
    CreateOutcomeReceiptRequest,
    CreatePredictionErrorRequest,
    CreatePredictionEvidenceRequest,
    CreateRecommendationAdherenceRequest,
    ExecutionAdherenceResponse,
    InvestmentDecisionResponse,
    LearningReceiptResponse,
    OutcomeObservationResponse,
    OutcomeReceiptResponse,
    PredictionErrorResponse,
    PredictionEvidenceResponse,
    RecommendationAdherenceResponse,
)
from app.service.routers.investment_planning import (
    authorized_planning_scope,
    private_no_store,
)

canonical_outcomes_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-portfolio/outcomes",
    tags=["investment-portfolio"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_outcomes_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-portfolio/outcomes",
    tags=["investment-portfolio"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def get_outcomes_service(request: Request) -> OutcomeService:
    service = getattr(request.app.state, "outcomes", None)
    if service is None:
        raise RuntimeError("Outcomes service is not configured.")
    return service


async def authorized_outcomes_scope(
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


def _amounts(raw: dict[str, float | None]) -> dict[str, Decimal | None]:
    return {key: None if value is None else Decimal(str(value)) for key, value in raw.items()}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _reject_client_authority(body: object) -> None:
    dumped = body.model_dump() if hasattr(body, "model_dump") else {}
    forbidden = {
        "l1_distance",
        "max_absolute_line_deviation",
        "max_percentage_deviation",
        "adherence_class",
        "signed_error",
        "absolute_error",
        "percentage_error",
        "directional_correct",
        "realized_percentile",
        "inside_expected_interval",
        "error_class",
        "prediction_error_class",
        "learning_candidate_type",
        "experience_boundary",
        "receipt_fingerprint",
        "decision_fingerprint",
        "observation_fingerprint",
        "fingerprint",
        "contributor_classes",
    }
    if any(key in dumped for key in forbidden):
        raise OptimizationError("Client cannot supply authoritative outcome calculations.")


async def bind_decision(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: BindInvestmentDecisionRequest,
) -> InvestmentDecisionResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        item = service.bind_decision_from_ids(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            proposal_decision_receipt_id=body.proposal_decision_receipt_id,
            planning_decision_record_id=body.planning_decision_record_id,
            frontier_selection_id=body.frontier_selection_id,
            recommended_portfolio_ref=body.recommended_portfolio_ref,
            decided_portfolio_ref=body.decided_portfolio_ref,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return InvestmentDecisionResponse(
        investment_decision_id=item.investment_decision_id,
        decision=item.decision.value,
        proposal_decision_receipt_id=item.proposal_decision_receipt_id,
        decision_fingerprint=item.decision_fingerprint,
    )


async def get_decision(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    decision_id: str,
) -> InvestmentDecisionResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_decision(decision_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return InvestmentDecisionResponse(
        investment_decision_id=item.investment_decision_id,
        decision=item.decision.value,
        proposal_decision_receipt_id=item.proposal_decision_receipt_id,
        decision_fingerprint=item.decision_fingerprint,
    )


async def create_recommendation_adherence(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreateRecommendationAdherenceRequest,
) -> RecommendationAdherenceResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        item = service.create_recommendation_adherence(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            investment_decision_ref=body.investment_decision_id,
            recommended_portfolio_ref=body.recommended_portfolio_ref,
            decided_portfolio_ref=body.decided_portfolio_ref,
            recommended=_shares(body.recommended_shares),
            decided=_shares(body.decided_shares),
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return RecommendationAdherenceResponse(
        recommendation_adherence_id=item.recommendation_adherence_id,
        l1_distance=item.l1_distance,
        adherence_class=item.adherence_class.value,
        fingerprint=item.fingerprint,
    )


async def get_recommendation_adherence(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    adherence_id: str,
) -> RecommendationAdherenceResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_recommendation_adherence(adherence_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return RecommendationAdherenceResponse(
        recommendation_adherence_id=item.recommendation_adherence_id,
        l1_distance=item.l1_distance,
        adherence_class=item.adherence_class.value,
        fingerprint=item.fingerprint,
    )


async def create_execution_adherence(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreateExecutionAdherenceRequest,
) -> ExecutionAdherenceResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        item = service.create_execution_adherence(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            approved_plan_ref=body.approved_plan_ref,
            planned=_amounts(body.planned),
            actual=_amounts(body.actual),
            actual_spend_source_ref=body.actual_spend_source_ref,
            exposure_handoff_ref=body.exposure_handoff_ref,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return ExecutionAdherenceResponse(
        execution_adherence_id=item.execution_adherence_id,
        status=item.status.value,
        adherence_class=item.adherence_class.value,
        fingerprint=item.fingerprint,
    )


async def get_execution_adherence(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    adherence_id: str,
) -> ExecutionAdherenceResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_execution_adherence(adherence_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return ExecutionAdherenceResponse(
        execution_adherence_id=item.execution_adherence_id,
        status=item.status.value,
        adherence_class=item.adherence_class.value,
        fingerprint=item.fingerprint,
    )


async def create_observation(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreateOutcomeObservationRequest,
) -> OutcomeObservationResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        item = service.create_observation(
            project_id=workspace.workspace_id,
            investment_decision_ref=body.investment_decision_ref,
            outcome_metric_id=body.outcome_metric_id,
            outcome_unit=body.outcome_unit,
            semantic_type=OutcomeSemanticType(body.semantic_type),
            observation_window_start=_parse_dt(body.observation_window_start),
            observation_window_end=_parse_dt(body.observation_window_end),
            as_of_time=_parse_dt(body.as_of_time),
            source_authority=OutcomeSourceAuthority(body.source_authority),
            source_refs=body.source_refs,
            observed_value=body.observed_value,
            approved_plan_ref=body.approved_plan_ref,
            supersedes_observation_id=body.supersedes_observation_id,
            decision_as_of_time=(
                _parse_dt(body.decision_as_of_time) if body.decision_as_of_time else None
            ),
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return OutcomeObservationResponse(
        decision_outcome_observation_id=item.decision_outcome_observation_id,
        observation_fingerprint=item.observation_fingerprint,
        semantic_type=item.semantic_type.value,
    )


async def get_observation(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    observation_id: str,
) -> OutcomeObservationResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_observation(observation_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return OutcomeObservationResponse(
        decision_outcome_observation_id=item.decision_outcome_observation_id,
        observation_fingerprint=item.observation_fingerprint,
        semantic_type=item.semantic_type.value,
    )


async def create_prediction_evidence(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreatePredictionEvidenceRequest,
) -> PredictionEvidenceResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        item = service.create_prediction_evidence(
            project_id=workspace.workspace_id,
            predicted_unit=body.predicted_unit,
            recommendation_as_of_time=_parse_dt(body.recommendation_as_of_time),
            decision_as_of_time=_parse_dt(body.decision_as_of_time),
            prediction_evidence_as_of_time=_parse_dt(body.prediction_evidence_as_of_time),
            predicted_value=body.predicted_value,
            frontier_selection_ref=body.frontier_selection_ref,
            portfolio_risk_evaluation_ref=body.portfolio_risk_evaluation_ref,
            simulation_evidence_handoff_ref=body.simulation_evidence_handoff_ref,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return PredictionEvidenceResponse(
        prediction_evidence_id=item.prediction_evidence_id,
        fingerprint=item.fingerprint,
        limitations=item.limitations,
    )


async def get_prediction_evidence(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    evidence_id: str,
) -> PredictionEvidenceResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_prediction_evidence(evidence_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return PredictionEvidenceResponse(
        prediction_evidence_id=item.prediction_evidence_id,
        fingerprint=item.fingerprint,
        limitations=item.limitations,
    )


async def create_prediction_error(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreatePredictionErrorRequest,
) -> PredictionErrorResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        evidence = service.get_prediction_evidence(body.prediction_evidence_id)
        observation = (
            service.get_observation(body.outcome_observation_id)
            if body.outcome_observation_id
            else None
        )
        item = service.create_prediction_error(evidence=evidence, observation=observation)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return PredictionErrorResponse(
        prediction_error_id=item.prediction_error_id,
        error_class=item.error_class.value,
        signed_error=item.signed_error,
        realized_percentile=item.realized_percentile,
        fingerprint=item.fingerprint,
    )


async def get_prediction_error(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    error_id: str,
) -> PredictionErrorResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_prediction_error(error_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return PredictionErrorResponse(
        prediction_error_id=item.prediction_error_id,
        error_class=item.error_class.value,
        signed_error=item.signed_error,
        realized_percentile=item.realized_percentile,
        fingerprint=item.fingerprint,
    )


async def create_receipt(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreateOutcomeReceiptRequest,
) -> OutcomeReceiptResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        decision = service.get_decision(body.investment_decision_id)
        prediction = (
            service.get_prediction_evidence(body.prediction_evidence_id)
            if body.prediction_evidence_id
            else None
        )
        observation = (
            service.get_observation(body.outcome_observation_id)
            if body.outcome_observation_id
            else None
        )
        rec_adh = (
            service.get_recommendation_adherence(body.recommendation_adherence_id)
            if body.recommendation_adherence_id
            else None
        )
        exec_adh = (
            service.get_execution_adherence(body.execution_adherence_id)
            if body.execution_adherence_id
            else None
        )
        error = (
            service.get_prediction_error(body.prediction_error_id)
            if body.prediction_error_id
            else None
        )
        item = service.create_receipt(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            decision=decision,
            prediction=prediction,
            observation=observation,
            recommendation_adherence=rec_adh,
            execution_adherence=exec_adh,
            prediction_error=error,
            approved_plan_ref=body.approved_plan_ref,
            outcome_not_observed=body.outcome_not_observed,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return OutcomeReceiptResponse(
        recommendation_outcome_receipt_id=item.recommendation_outcome_receipt_id,
        status=item.status.value,
        receipt_fingerprint=item.receipt_fingerprint,
        limitations=item.limitations,
    )


async def get_receipt(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    receipt_id: str,
) -> OutcomeReceiptResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_receipt(receipt_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return OutcomeReceiptResponse(
        recommendation_outcome_receipt_id=item.recommendation_outcome_receipt_id,
        status=item.status.value,
        receipt_fingerprint=item.receipt_fingerprint,
        limitations=item.limitations,
    )


async def create_learning_receipt(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    body: CreateLearningReceiptRequest,
) -> LearningReceiptResponse:
    _reject_client_authority(body)
    service = get_outcomes_service(request)
    try:
        receipt = service.get_receipt(body.recommendation_outcome_receipt_id)
        adherence = (
            service.get_recommendation_adherence(receipt.recommendation_adherence_ref)
            if receipt.recommendation_adherence_ref
            else None
        )
        error = (
            service.get_prediction_error(receipt.prediction_error_ref)
            if receipt.prediction_error_ref
            else None
        )
        item = service.create_learning_receipt(
            project_id=workspace.workspace_id,
            receipt=receipt,
            adherence=adherence,
            error=error,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return LearningReceiptResponse(
        learning_receipt_id=item.learning_receipt_id,
        learning_candidate_type=item.learning_candidate_type.value,
        experience_boundary=item.experience_boundary.value,
        fingerprint=item.fingerprint,
    )


async def get_learning_receipt(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_outcomes_scope)],
    receipt_id: str,
) -> LearningReceiptResponse:
    del workspace
    try:
        item = get_outcomes_service(request).get_learning_receipt(receipt_id)
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return LearningReceiptResponse(
        learning_receipt_id=item.learning_receipt_id,
        learning_candidate_type=item.learning_candidate_type.value,
        experience_boundary=item.experience_boundary.value,
        fingerprint=item.fingerprint,
    )


for _router in (canonical_outcomes_router, workspace_alias_outcomes_router):
    _canonical = _router is canonical_outcomes_router
    _router.add_api_route(
        "/decisions",
        bind_decision,
        methods=["POST"],
        response_model=InvestmentDecisionResponse,
        operation_id="bindInvestmentDecision" if _canonical else "bindInvestmentDecisionWorkspace",
    )
    _router.add_api_route(
        "/decisions/{decision_id}",
        get_decision,
        methods=["GET"],
        response_model=InvestmentDecisionResponse,
        operation_id="getInvestmentDecision" if _canonical else "getInvestmentDecisionWorkspace",
    )
    _router.add_api_route(
        "/recommendation-adherence",
        create_recommendation_adherence,
        methods=["POST"],
        response_model=RecommendationAdherenceResponse,
        operation_id="createRecommendationAdherence"
        if _canonical
        else "createRecommendationAdherenceWorkspace",
    )
    _router.add_api_route(
        "/recommendation-adherence/{adherence_id}",
        get_recommendation_adherence,
        methods=["GET"],
        response_model=RecommendationAdherenceResponse,
        operation_id="getRecommendationAdherence"
        if _canonical
        else "getRecommendationAdherenceWorkspace",
    )
    _router.add_api_route(
        "/execution-adherence",
        create_execution_adherence,
        methods=["POST"],
        response_model=ExecutionAdherenceResponse,
        operation_id=(
            "createExecutionAdherence" if _canonical else "createExecutionAdherenceWorkspace"
        ),
    )
    _router.add_api_route(
        "/execution-adherence/{adherence_id}",
        get_execution_adherence,
        methods=["GET"],
        response_model=ExecutionAdherenceResponse,
        operation_id="getExecutionAdherence" if _canonical else "getExecutionAdherenceWorkspace",
    )
    _router.add_api_route(
        "/outcome-observations",
        create_observation,
        methods=["POST"],
        response_model=OutcomeObservationResponse,
        operation_id=(
            "createOutcomeObservation" if _canonical else "createOutcomeObservationWorkspace"
        ),
    )
    _router.add_api_route(
        "/outcome-observations/{observation_id}",
        get_observation,
        methods=["GET"],
        response_model=OutcomeObservationResponse,
        operation_id="getOutcomeObservation" if _canonical else "getOutcomeObservationWorkspace",
    )
    _router.add_api_route(
        "/prediction-evidence",
        create_prediction_evidence,
        methods=["POST"],
        response_model=PredictionEvidenceResponse,
        operation_id=(
            "createPredictionEvidence" if _canonical else "createPredictionEvidenceWorkspace"
        ),
    )
    _router.add_api_route(
        "/prediction-evidence/{evidence_id}",
        get_prediction_evidence,
        methods=["GET"],
        response_model=PredictionEvidenceResponse,
        operation_id="getPredictionEvidence" if _canonical else "getPredictionEvidenceWorkspace",
    )
    _router.add_api_route(
        "/prediction-errors",
        create_prediction_error,
        methods=["POST"],
        response_model=PredictionErrorResponse,
        operation_id="createPredictionError" if _canonical else "createPredictionErrorWorkspace",
    )
    _router.add_api_route(
        "/prediction-errors/{error_id}",
        get_prediction_error,
        methods=["GET"],
        response_model=PredictionErrorResponse,
        operation_id="getPredictionError" if _canonical else "getPredictionErrorWorkspace",
    )
    _router.add_api_route(
        "/receipts",
        create_receipt,
        methods=["POST"],
        response_model=OutcomeReceiptResponse,
        operation_id="createOutcomeReceipt" if _canonical else "createOutcomeReceiptWorkspace",
    )
    _router.add_api_route(
        "/receipts/{receipt_id}",
        get_receipt,
        methods=["GET"],
        response_model=OutcomeReceiptResponse,
        operation_id="getOutcomeReceipt" if _canonical else "getOutcomeReceiptWorkspace",
    )
    _router.add_api_route(
        "/learning-receipts",
        create_learning_receipt,
        methods=["POST"],
        response_model=LearningReceiptResponse,
        operation_id="createLearningReceipt" if _canonical else "createLearningReceiptWorkspace",
    )
    _router.add_api_route(
        "/learning-receipts/{receipt_id}",
        get_learning_receipt,
        methods=["GET"],
        response_model=LearningReceiptResponse,
        operation_id="getLearningReceipt" if _canonical else "getLearningReceiptWorkspace",
    )

"""Canonical run lookup scoped to the authenticated tenant."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.service.dependencies import authenticated_tenant, get_evaluation_service
from app.service.evaluation_service import EvaluationService
from app.service.models import EvaluationResponse
from app.service.routers.evaluations import _to_response

router = APIRouter(prefix="/v1/runs", tags=["evaluations"])


@router.get(
    "/{run_id}",
    operation_id="getEvaluationByRunId",
    response_model=EvaluationResponse,
)
async def get_run(
    run_id: str,
    request: Request,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
) -> EvaluationResponse:
    evaluation = service.get_evaluation(run_id=run_id)
    resolver = getattr(request.app.state, "model_ready_resolver", None)
    return _to_response(evaluation, service=service, model_ready_resolver=resolver)

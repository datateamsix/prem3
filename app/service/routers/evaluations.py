"""Evaluation resource routes. Does not start ADK execution."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from app.control_plane.models import Dataset, DatasetEvaluationRef
from app.service.dependencies import (
    authenticated_tenant,
    authorized_dataset,
    get_evaluation_service,
)
from app.service.evaluation_progress import compose_execution_view
from app.service.evaluation_service import EvaluationService
from app.service.models import (
    CreateEvaluationRequest,
    EvaluationListResponse,
    EvaluationResponse,
)
from app.service.pagination import paginate_by_id

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations",
    tags=["evaluations"],
)


def _to_response(
    evaluation: DatasetEvaluationRef,
    *,
    service: EvaluationService | None = None,
    model_ready_resolver=None,
) -> EvaluationResponse:
    dispatch = None
    if service is not None:
        dispatch = service.get_dispatch_for_run(run_id=evaluation.run_id)
    execution = compose_execution_view(
        evaluation, dispatch, model_ready_resolver=model_ready_resolver
    )
    return EvaluationResponse(
        run_id=evaluation.run_id,
        dataset_id=evaluation.dataset_id,
        upload_id=evaluation.upload_id,
        status=evaluation.status.value,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
        package_fingerprint=evaluation.package_fingerprint,
        execution=execution,
    )


@router.post(
    "",
    operation_id="createEvaluation",
    response_model=EvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_evaluation(
    body: CreateEvaluationRequest,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EvaluationResponse:
    """Accept Evaluation creation. 202 means durable dispatch queued, not ADK complete."""
    evaluation = service.create_evaluation(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        upload_id=body.upload_id,
        idempotency_key=idempotency_key,
    )
    return _to_response(evaluation, service=service)


@router.get(
    "",
    operation_id="listEvaluations",
    response_model=EvaluationListResponse,
)
async def list_evaluations(
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
    cursor: str | None = None,
) -> EvaluationListResponse:
    rows = service.list_evaluations(
        workspace_id=dataset.workspace_id, dataset_id=dataset.dataset_id
    )
    page, next_cursor = paginate_by_id(
        rows, cursor=cursor, limit=limit, id_of=lambda item: item.run_id
    )
    return EvaluationListResponse(
        items=[_to_response(item, service=service) for item in page],
        next_cursor=next_cursor,
    )

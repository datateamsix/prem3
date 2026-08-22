"""Evaluation publish execution APIs. Destinations come from server bindings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Dataset
from app.publish_execution.contracts import PublishExecutionReceipt
from app.publish_execution.service import PublishExecutionService
from app.service.dependencies import authenticated_tenant, authorized_dataset
from app.service.models import (
    PublishDestinationResultResponse,
    PublishedArtifactResponse,
    PublishExecutionListResponse,
    PublishExecutionResponse,
)

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations/{run_id}",
    tags=["publish-execution"],
)


def get_publish_execution(request: Request) -> PublishExecutionService:
    service = getattr(request.app.state, "publish_execution", None)
    if service is None:
        raise RuntimeError("Publish execution service is not configured.")
    return service


def _artifact(item) -> PublishedArtifactResponse:
    return PublishedArtifactResponse(
        name=item.name,
        identity=item.identity,
        size_bytes=item.size_bytes,
        checksum=item.checksum,
        verified=item.verified,
    )


def _response(receipt: PublishExecutionReceipt) -> PublishExecutionResponse:
    return PublishExecutionResponse(
        publish_id=receipt.publish_id,
        receipt_id=receipt.receipt_id,
        run_id=receipt.run_id,
        status=receipt.status.value,
        model_ready_fingerprint=receipt.model_ready_fingerprint,
        publish_readiness_receipt_id=receipt.publish_readiness_receipt_id,
        publish_contract_fingerprint=receipt.publish_contract_fingerprint,
        destination_results=[
            PublishDestinationResultResponse(
                kind=item.kind.value,
                binding_id=item.binding_id,
                target_presentation_identity=item.target_presentation_identity,
                versioned_resource_identity=item.versioned_resource_identity,
                stable_pointer_identity=item.stable_pointer_identity,
                artifacts_written=[_artifact(row) for row in item.artifacts_written],
                artifacts_verified=[_artifact(row) for row in item.artifacts_verified],
                row_count=item.row_count,
                schema_fingerprint=item.schema_fingerprint,
                content_fingerprint=item.content_fingerprint,
                write_completed=item.write_completed,
                readback_verified=item.readback_verified,
                status=item.status.value,
                failure_code=item.failure_code,
                failure_detail=item.failure_detail,
            )
            for item in receipt.destination_results
        ],
        started_at=receipt.started_at,
        completed_at=receipt.completed_at,
        failure_code=receipt.failure_code,
        failure_detail=receipt.failure_detail,
    )


@router.post(
    "/publishes",
    operation_id="publishEvaluation",
    response_model=PublishExecutionResponse,
)
async def publish_evaluation(
    run_id: str,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[PublishExecutionService, Depends(get_publish_execution)],
) -> PublishExecutionResponse:
    receipt = service.publish(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        run_id=run_id,
    )
    return _response(receipt)


@router.get(
    "/publishes",
    operation_id="listEvaluationPublishes",
    response_model=PublishExecutionListResponse,
)
async def list_evaluation_publishes(
    run_id: str,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[PublishExecutionService, Depends(get_publish_execution)],
) -> PublishExecutionListResponse:
    items = service.list_publishes(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        run_id=run_id,
    )
    return PublishExecutionListResponse(items=[_response(item) for item in items])


@router.get(
    "/publishes/{publish_id}",
    operation_id="getEvaluationPublish",
    response_model=PublishExecutionResponse,
)
async def get_evaluation_publish(
    run_id: str,
    publish_id: str,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[PublishExecutionService, Depends(get_publish_execution)],
) -> PublishExecutionResponse:
    receipt = service.get_publish(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        run_id=run_id,
        publish_id=publish_id,
    )
    return _response(receipt)

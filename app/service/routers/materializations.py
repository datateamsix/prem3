"""Dataset source materialization APIs. No client storage authority."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Dataset
from app.materialization.contracts import SourceMaterializationReceipt
from app.materialization.service import MaterializationService
from app.service.dependencies import authenticated_tenant, authorized_dataset
from app.service.models import (
    MaterializeDatasetSourceRequest,
    SourceMaterializationListResponse,
    SourceMaterializationResponse,
    SourceObjectLineageResponse,
)

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/datasets/{dataset_id}/materializations",
    tags=["materialization"],
)


def get_materialization_service(request: Request) -> MaterializationService:
    service = getattr(request.app.state, "materialization", None)
    if service is None:
        raise RuntimeError("Materialization service is not configured.")
    return service


def _response(receipt: SourceMaterializationReceipt) -> SourceMaterializationResponse:
    versions = receipt.source_version_identities
    return SourceMaterializationResponse(
        materialization_id=receipt.materialization_id,
        receipt_id=receipt.receipt_id,
        dataset_id=receipt.dataset_id,
        source_type=receipt.source_type.value,
        source_binding_id=receipt.source_binding_id,
        provider=receipt.provider,
        business_role=receipt.business_role,
        history=receipt.history,
        refresh_cadence=receipt.refresh_cadence,
        freshness=receipt.freshness,
        grain=receipt.grain,
        geography=receipt.geography,
        metrics=list(receipt.metrics),
        source_version=versions[0] if versions else None,
        foundation_source_state=receipt.foundation_status,
        import_governance_state="IMPORT_READY",
        premodel_review_remaining=receipt.premodel_review_remaining,
        premodel_review_findings=list(receipt.premodel_review_findings),
        materialization_state=receipt.status.value,
        result_kind=None if receipt.result_kind is None else receipt.result_kind.value,
        upload_id=receipt.upload_id,
        upload_status=receipt.upload_status,
        upload_package_fingerprint=receipt.upload_package_fingerprint,
        import_receipt_id=receipt.import_receipt_id,
        import_manifest_fingerprint=receipt.import_manifest_fingerprint,
        source_objects=[
            SourceObjectLineageResponse(
                object_id=item.object_id,
                provider=item.provider,
                role=item.role,
                logical_name=item.logical_name,
                source_identity=item.source_identity,
                version_identity=item.version_identity,
                object_type=item.object_type,
                format=item.format,
                schema_fingerprint=item.schema_fingerprint,
                upload_file_id=item.upload_file_id,
                target_generation=item.target_generation,
                target_checksum=item.target_checksum,
            )
            for item in receipt.source_objects
        ],
        started_at=receipt.started_at,
        completed_at=receipt.completed_at,
        failure_code=receipt.failure_code,
        failure_detail=receipt.failure_detail,
    )


@router.post(
    "",
    operation_id="materializeDatasetSource",
    response_model=SourceMaterializationResponse,
)
async def materialize_dataset_source(
    body: MaterializeDatasetSourceRequest,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[MaterializationService, Depends(get_materialization_service)],
) -> SourceMaterializationResponse:
    receipt = service.materialize(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        idempotency_key=body.idempotency_key,
    )
    return _response(receipt)


@router.get(
    "",
    operation_id="listDatasetMaterializations",
    response_model=SourceMaterializationListResponse,
)
async def list_dataset_materializations(
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[MaterializationService, Depends(get_materialization_service)],
) -> SourceMaterializationListResponse:
    items = service.list_materializations(
        workspace_id=dataset.workspace_id, dataset_id=dataset.dataset_id
    )
    return SourceMaterializationListResponse(items=[_response(item) for item in items])


@router.get(
    "/{materialization_id}",
    operation_id="getDatasetMaterialization",
    response_model=SourceMaterializationResponse,
)
async def get_dataset_materialization(
    materialization_id: str,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[MaterializationService, Depends(get_materialization_service)],
) -> SourceMaterializationResponse:
    receipt = service.get_materialization(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        materialization_id=materialization_id,
    )
    return _response(receipt)

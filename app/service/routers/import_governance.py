"""Dataset import-binding and import/publish readiness APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Dataset
from app.governance.import_contract import ImportReadinessReceipt
from app.governance.publish_contract import PublishReadinessReceipt
from app.service.dependencies import authenticated_tenant, authorized_dataset
from app.service.errors import resource_not_found
from app.service.import_governance import ImportGovernanceService
from app.service.models import (
    DatasetImportBindingRequest,
    DatasetImportBindingResponse,
    GovernanceCheckResponse,
    ImportReadinessReceiptResponse,
    ImportRoleAssignmentRequest,
    PublishReadinessReceiptResponse,
)
from app.service.publish_governance import PublishGovernanceService

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/datasets/{dataset_id}",
    tags=["import-governance"],
)


def get_import_governance(request: Request) -> ImportGovernanceService:
    service = getattr(request.app.state, "import_governance", None)
    if service is None:
        raise RuntimeError("Import governance service is not configured.")
    return service


def get_publish_governance(request: Request) -> PublishGovernanceService:
    service = getattr(request.app.state, "publish_governance", None)
    if service is None:
        raise RuntimeError("Publish governance service is not configured.")
    return service


def _binding_response(selection) -> DatasetImportBindingResponse:
    return DatasetImportBindingResponse(
        source_type=selection.source_type,
        connection_id=selection.connection_id,
        upload_id=selection.upload_id,
        selected_object_ids=list(selection.selected_object_ids),
        role_assignments=[
            ImportRoleAssignmentRequest(
                object_id=item.get("object_id", ""),
                role=item.get("role", ""),
                provider=item.get("provider", ""),
            )
            for item in selection.role_assignments
        ],
        current_receipt_id=selection.current_receipt_id,
        updated_at=selection.updated_at,
    )


def _import_receipt_response(
    receipt: ImportReadinessReceipt, *, selected_object_count: int | None = None
) -> ImportReadinessReceiptResponse:
    return ImportReadinessReceiptResponse(
        receipt_id=receipt.receipt_id,
        contract_version=receipt.contract_version,
        tenant_id=receipt.tenant_id,
        workspace_id=receipt.workspace_id,
        dataset_id=receipt.dataset_id,
        source_type=receipt.source_type.value,
        status=receipt.status.value,
        check_results=[
            GovernanceCheckResponse(
                code=item.code.value,
                severity=item.severity.value,
                passed=item.passed,
                message=item.message,
                evidence=dict(item.evidence),
            )
            for item in receipt.check_results
        ],
        error_count=receipt.error_count,
        attention_count=receipt.attention_count,
        selected_object_count=selected_object_count,
        role_assignment_count=None
        if selected_object_count is None
        else selected_object_count,
        manifest_fingerprint=receipt.manifest_fingerprint,
        verified_at=receipt.verified_at,
        superseded=receipt.superseded,
    )


def _publish_receipt_response(
    receipt: PublishReadinessReceipt,
) -> PublishReadinessReceiptResponse:
    return PublishReadinessReceiptResponse(
        receipt_id=receipt.receipt_id,
        contract_version=receipt.contract_version,
        tenant_id=receipt.tenant_id,
        workspace_id=receipt.workspace_id,
        dataset_id=receipt.dataset_id,
        run_id=receipt.run_id,
        status=receipt.status.value,
        destination_summaries=list(receipt.destination_summaries),
        check_results=[
            GovernanceCheckResponse(
                code=item.code.value,
                severity=item.severity.value,
                passed=item.passed,
                message=item.message,
                evidence=dict(item.evidence),
            )
            for item in receipt.check_results
        ],
        model_ready_fingerprint=receipt.model_ready_fingerprint,
        contract_fingerprint=receipt.contract_fingerprint,
        verified_at=receipt.verified_at,
        published=receipt.published,
    )


@router.put(
    "/import-binding",
    operation_id="putDatasetImportBinding",
    response_model=DatasetImportBindingResponse,
)
async def put_import_binding(
    body: DatasetImportBindingRequest,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[ImportGovernanceService, Depends(get_import_governance)],
) -> DatasetImportBindingResponse:
    selection = service.put_selection(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        source_type=body.source_type,
        connection_id=body.connection_id,
        upload_id=body.upload_id,
        selected_object_ids=body.selected_object_ids,
        role_assignments=[item.model_dump() for item in body.role_assignments],
    )
    return _binding_response(selection)


@router.get(
    "/import-binding",
    operation_id="getDatasetImportBinding",
    response_model=DatasetImportBindingResponse,
)
async def get_import_binding(
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[ImportGovernanceService, Depends(get_import_governance)],
) -> DatasetImportBindingResponse:
    selection = service.get_selection(
        workspace_id=dataset.workspace_id, dataset_id=dataset.dataset_id
    )
    if selection is None:
        raise resource_not_found()
    return _binding_response(selection)


@router.post(
    "/import-readiness",
    operation_id="evaluateDatasetImportReadiness",
    response_model=ImportReadinessReceiptResponse,
)
async def evaluate_import_readiness_route(
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[ImportGovernanceService, Depends(get_import_governance)],
) -> ImportReadinessReceiptResponse:
    contract, receipt = service.evaluate(
        workspace_id=dataset.workspace_id, dataset_id=dataset.dataset_id
    )
    return _import_receipt_response(
        receipt,
        selected_object_count=len(contract.objects),
    )


@router.get(
    "/import-readiness",
    operation_id="getDatasetImportReadiness",
    response_model=ImportReadinessReceiptResponse,
)
async def get_import_readiness(
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[ImportGovernanceService, Depends(get_import_governance)],
) -> ImportReadinessReceiptResponse:
    receipt = service.current_receipt(
        workspace_id=dataset.workspace_id, dataset_id=dataset.dataset_id
    )
    if receipt is None:
        raise resource_not_found()
    selection = service.get_selection(
        workspace_id=dataset.workspace_id, dataset_id=dataset.dataset_id
    )
    count = len(selection.selected_object_ids) if selection is not None else None
    return _import_receipt_response(receipt, selected_object_count=count)


@router.post(
    "/evaluations/{run_id}/publish-readiness",
    operation_id="evaluatePublishReadiness",
    response_model=PublishReadinessReceiptResponse,
)
async def evaluate_publish_readiness_route(
    run_id: str,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[PublishGovernanceService, Depends(get_publish_governance)],
) -> PublishReadinessReceiptResponse:
    _contract, receipt = service.evaluate(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        run_id=run_id,
    )
    return _publish_receipt_response(receipt)


@router.get(
    "/evaluations/{run_id}/publish-readiness",
    operation_id="getPublishReadiness",
    response_model=PublishReadinessReceiptResponse,
)
async def get_publish_readiness_route(
    run_id: str,
    dataset: Annotated[Dataset, Depends(authorized_dataset)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    request: Request,
) -> PublishReadinessReceiptResponse:
    execution = getattr(request.app.state, "publish_execution", None)
    if execution is None:
        raise resource_not_found()
    receipt = execution.get_publish_readiness(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.dataset_id,
        run_id=run_id,
    )
    return _publish_receipt_response(receipt)

"""Workspace Google Drive and BigQuery binding / discovery APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.control_plane.models import Workspace
from app.service.dependencies import authenticated_tenant, authorized_workspace
from app.service.errors import resource_not_found
from app.service.google_bigquery import BigQueryBindingService
from app.service.google_drive import DriveBindingService
from app.service.models import (
    BigQueryBindingResponse,
    BigQueryBindingSetupRequest,
    BigQueryDatasetListResponse,
    BigQueryProjectListResponse,
    BigQueryTableListItem,
    BigQueryTableListResponse,
    DriveBindingResponse,
    DriveBindingSetupRequest,
)

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/integrations",
    tags=["google-integrations"],
)


def get_drive_bindings(request: Request) -> DriveBindingService:
    service = getattr(request.app.state, "drive_bindings", None)
    if service is None:
        raise RuntimeError("Drive binding service is not configured.")
    return service


def get_bq_bindings(request: Request) -> BigQueryBindingService:
    service = getattr(request.app.state, "bigquery_bindings", None)
    if service is None:
        raise RuntimeError("BigQuery binding service is not configured.")
    return service


def _drive_response(binding) -> DriveBindingResponse:
    return DriveBindingResponse(
        workspace_id=binding.workspace_id,
        connection_id=binding.connection_id,
        root_folder_id=binding.root_folder_id,
        root_folder_name=binding.root_folder_name,
        imports_folder_id=binding.imports_folder_id,
        exports_folder_id=binding.exports_folder_id,
        reports_folder_id=binding.reports_folder_id,
        budgets_folder_id=binding.budgets_folder_id,
        budget_templates_folder_id=binding.budget_templates_folder_id,
        budget_plans_folder_id=binding.budget_plans_folder_id,
        budget_scenarios_folder_id=binding.budget_scenarios_folder_id,
        budget_proposals_folder_id=binding.budget_proposals_folder_id,
        status=binding.status,
        import_enabled=binding.import_enabled,
        export_enabled=binding.export_enabled,
        updated_at=binding.updated_at,
        last_verified_at=binding.last_verified_at,
    )


def _bq_response(binding) -> BigQueryBindingResponse:
    return BigQueryBindingResponse(
        workspace_id=binding.workspace_id,
        connection_id=binding.connection_id,
        source_project_ids=list(binding.source_project_ids),
        source_dataset_ids=list(binding.source_dataset_ids),
        destination_project_id=binding.destination_project_id,
        destination_dataset_id=binding.destination_dataset_id,
        destination_friendly_name=binding.destination_friendly_name,
        location=binding.location,
        read_verified=binding.read_verified,
        write_verified=binding.write_verified,
        status=binding.status,
        updated_at=binding.updated_at,
        last_verified_at=binding.last_verified_at,
    )


@router.get(
    "/drive",
    operation_id="getDriveBinding",
    response_model=DriveBindingResponse,
)
async def get_drive_binding(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[DriveBindingService, Depends(get_drive_bindings)],
) -> DriveBindingResponse:
    binding = service.get_binding(workspace_id=workspace.workspace_id)
    if binding is None:
        raise resource_not_found()
    return _drive_response(binding)


@router.post(
    "/drive/setup",
    operation_id="setupDriveDepot",
    response_model=DriveBindingResponse,
)
async def setup_drive_depot(
    body: DriveBindingSetupRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[DriveBindingService, Depends(get_drive_bindings)],
) -> DriveBindingResponse:
    binding = service.setup(
        workspace_id=workspace.workspace_id,
        connection_id=body.connection_id,
        import_enabled=body.import_enabled,
        export_enabled=body.export_enabled,
    )
    return _drive_response(binding)


@router.post(
    "/drive/repair",
    operation_id="repairDriveBinding",
    response_model=DriveBindingResponse,
)
async def repair_drive_binding(
    body: DriveBindingSetupRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[DriveBindingService, Depends(get_drive_bindings)],
) -> DriveBindingResponse:
    return _drive_response(
        service.repair(workspace_id=workspace.workspace_id, connection_id=body.connection_id)
    )


@router.get(
    "/bigquery",
    operation_id="getBigQueryBinding",
    response_model=BigQueryBindingResponse,
)
async def get_bigquery_binding(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[BigQueryBindingService, Depends(get_bq_bindings)],
) -> BigQueryBindingResponse:
    binding = service.get_binding(workspace_id=workspace.workspace_id)
    if binding is None:
        raise resource_not_found()
    return _bq_response(binding)


@router.post(
    "/bigquery/setup",
    operation_id="setupBigQueryDepot",
    response_model=BigQueryBindingResponse,
)
async def setup_bigquery_depot(
    body: BigQueryBindingSetupRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[BigQueryBindingService, Depends(get_bq_bindings)],
) -> BigQueryBindingResponse:
    return _bq_response(
        service.setup(
            workspace_id=workspace.workspace_id,
            connection_id=body.connection_id,
            destination_project_id=body.destination_project_id,
            location=body.location,
            source_project_ids=body.source_project_ids,
            source_dataset_ids=body.source_dataset_ids,
            create_if_missing=body.create_if_missing,
        )
    )


@router.get(
    "/bigquery/projects",
    operation_id="listBigQueryProjects",
    response_model=BigQueryProjectListResponse,
)
async def list_bigquery_projects(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[BigQueryBindingService, Depends(get_bq_bindings)],
    connection_id: Annotated[str, Query()],
) -> BigQueryProjectListResponse:
    items = service.list_projects(
        workspace_id=workspace.workspace_id, connection_id=connection_id
    )
    return BigQueryProjectListResponse(items=items)


@router.get(
    "/bigquery/projects/{project_id}/datasets",
    operation_id="listBigQueryDatasets",
    response_model=BigQueryDatasetListResponse,
)
async def list_bigquery_datasets(
    project_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[BigQueryBindingService, Depends(get_bq_bindings)],
    connection_id: Annotated[str, Query()],
) -> BigQueryDatasetListResponse:
    items = service.list_datasets(
        workspace_id=workspace.workspace_id,
        connection_id=connection_id,
        project_id=project_id,
    )
    return BigQueryDatasetListResponse(items=items)


@router.get(
    "/bigquery/projects/{project_id}/datasets/{dataset_id}/tables",
    operation_id="listBigQueryTables",
    response_model=BigQueryTableListResponse,
)
async def list_bigquery_tables(
    project_id: str,
    dataset_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    _tenant: Annotated[object, Depends(authenticated_tenant)],
    service: Annotated[BigQueryBindingService, Depends(get_bq_bindings)],
    connection_id: Annotated[str, Query()],
) -> BigQueryTableListResponse:
    tables = service.list_tables(
        workspace_id=workspace.workspace_id,
        connection_id=connection_id,
        project_id=project_id,
        dataset_id=dataset_id,
    )
    return BigQueryTableListResponse(
        items=[
            BigQueryTableListItem(
                project_id=item.project_id,
                dataset_id=item.dataset_id,
                table_id=item.table_id,
                object_type=item.object_type,
                location=item.location,
            )
            for item in tables
        ]
    )

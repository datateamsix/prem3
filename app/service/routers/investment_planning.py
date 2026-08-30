"""Project-scoped Investment Plan API. Tenant is never accepted from the client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.control_plane.models import Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, WorkspaceContext, bind_workspace, require_tenant
from app.investment_planning.contracts import (
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    InvestmentPlan,
    InvestmentPlanValidationReceipt,
)
from app.investment_planning.enums import InvestmentPlanReadyStatus
from app.investment_planning.errors import PlanningError
from app.investment_planning.lifecycle import capability_ready_status
from app.investment_planning.privacy import amount_bearing_response_headers
from app.investment_planning.service import InvestmentPlanService
from app.service.dependencies import authenticated_tenant, get_control_plane
from app.service.errors import planning_error, resource_not_found
from app.service.investment_planning_models import (
    ApproveInvestmentPlanRequest,
    BindDriveBudgetSourceRequest,
    BudgetDriveSourceAcceptedResponse,
    BudgetMappingResponse,
    BudgetSourceResponse,
    ConfirmBudgetMappingRequest,
    CreateInvestmentPlanRequest,
    InvestmentPlanListResponse,
    InvestmentPlanReadyResponse,
    InvestmentPlanResponse,
    InvestmentPlanValidationResponse,
    ValidateInvestmentPlanRequest,
)

def private_no_store(response: Response) -> None:
    for key, value in amount_bearing_response_headers().items():
        response.headers[key] = value


canonical_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-plans",
    tags=["investment-plans"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-plans",
    tags=["investment-plans"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def get_investment_planning(request: Request) -> InvestmentPlanService:
    service = getattr(request.app.state, "investment_planning", None)
    if service is None:
        raise RuntimeError("Investment Plan service is not configured.")
    return service


async def authorized_planning_scope(
    request: Request,
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
) -> AsyncIterator[Workspace]:
    scope_id = request.path_params.get("project_id") or request.path_params.get("workspace_id")
    if not scope_id:
        raise resource_not_found()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=str(scope_id)
    )
    if workspace is None:
        raise resource_not_found()
    with bind_workspace(WorkspaceContext(workspace_id=workspace.workspace_id)) as _:
        yield workspace


def _plan_response(plan: InvestmentPlan) -> InvestmentPlanResponse:
    return InvestmentPlanResponse(
        plan_id=plan.plan_id,
        project_id=plan.project_id,
        workspace_id=plan.workspace_id,
        name=plan.name,
        fiscal_year=plan.fiscal_year,
        fiscal_start_month=plan.fiscal_start_month,
        currency=plan.currency,
        budget_scope=plan.budget_scope.value,
        business_profile_snapshot_id=plan.business_profile_snapshot_id,
        business_profile_fingerprint=plan.business_profile_fingerprint,
        active_source_version_id=plan.active_source_version_id,
        status=plan.status.value,
        revision=plan.revision,
        predecessor_plan_id=plan.predecessor_plan_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        created_by=plan.created_by,
        approved_at=plan.approved_at,
        approved_by=plan.approved_by,
    )


def _source_response(source: BudgetDriveSourceVersion) -> BudgetSourceResponse:
    return BudgetSourceResponse(
        source_version_id=source.source_version_id,
        plan_id=source.plan_id,
        drive_file_id=source.drive_file_id,
        file_name=source.file_name,
        mime_type=source.mime_type,
        drive_version=source.drive_version,
        head_revision_id=source.head_revision_id,
        md5_checksum=source.md5_checksum,
        schema_version=source.schema_version,
        predecessor_source_version_id=source.predecessor_source_version_id,
        created_at=source.created_at,
        created_by=source.created_by,
    )


def _mapping_response(
    mapping: BudgetColumnMapping, *, ambiguous: tuple[str, ...] = ()
) -> BudgetMappingResponse:
    return BudgetMappingResponse(
        mapping_id=mapping.mapping_id,
        plan_id=mapping.plan_id,
        source_version_id=mapping.source_version_id,
        market_column=mapping.market_column,
        channel_column=mapping.channel_column,
        quarter_columns=mapping.quarter_columns,
        initiative_column=mapping.initiative_column,
        confirmed=mapping.confirmed,
        ambiguous=ambiguous,
    )


def _receipt_response(receipt: InvestmentPlanValidationReceipt) -> InvestmentPlanValidationResponse:
    return InvestmentPlanValidationResponse(
        receipt_id=receipt.receipt_id,
        plan_id=receipt.plan_id,
        source_version_id=receipt.source_version_id,
        status=receipt.status.value,
        error_codes=receipt.error_codes,
        flagged_row_indexes=receipt.flagged_row_indexes,
        flagged_headers=receipt.flagged_headers,
    )


def _actor_id() -> str:
    return require_tenant().user_id or "unknown"


async def list_plans(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanListResponse:
    del tenant
    try:
        plans = service.list_plans(project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return InvestmentPlanListResponse(items=tuple(_plan_response(plan) for plan in plans))


async def create_plan(
    body: CreateInvestmentPlanRequest,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanResponse:
    del tenant
    try:
        plan = service.create_plan(
            project_id=workspace.workspace_id,
            name=body.name,
            fiscal_year=body.fiscal_year,
            currency=body.currency,
            budget_scope=body.budget_scope,
            actor_id=_actor_id(),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _plan_response(plan)


async def get_plan(
    plan_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanResponse:
    del tenant
    try:
        plan = service.get_plan(plan_id=plan_id, project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _plan_response(plan)


async def create_template(
    plan_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> BudgetSourceResponse:
    del tenant
    try:
        source = service.upload_template(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            actor_id=_actor_id(),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _source_response(source)


async def bind_drive_source(
    plan_id: str,
    body: BindDriveBudgetSourceRequest,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> BudgetDriveSourceAcceptedResponse:
    del tenant
    try:
        source, proposal = service.ingest_drive_file(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            drive_file_id=body.drive_file_id,
            actor_id=_actor_id(),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return BudgetDriveSourceAcceptedResponse(
        source=_source_response(source),
        mapping=_mapping_response(proposal.mapping, ambiguous=proposal.ambiguous),
    )


async def confirm_mapping(
    plan_id: str,
    body: ConfirmBudgetMappingRequest,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> BudgetMappingResponse:
    del tenant
    try:
        mapping = service.confirm_mapping(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            mapping_id=body.mapping_id,
            actor_id=_actor_id(),
            market_column=body.market_column,
            channel_column=body.channel_column,
            quarter_columns=body.quarter_columns,
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _mapping_response(mapping)


async def validate_plan(
    plan_id: str,
    body: ValidateInvestmentPlanRequest,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanValidationResponse:
    del tenant
    try:
        receipt = service.validate(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            mapping_id=body.mapping_id,
            blanks_acknowledged=body.blanks_acknowledged,
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _receipt_response(receipt)


async def save_version(
    plan_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> BudgetSourceResponse:
    del tenant
    try:
        source = service.save_version(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            actor_id=_actor_id(),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _source_response(source)


async def approve_plan(
    plan_id: str,
    body: ApproveInvestmentPlanRequest,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanResponse:
    del tenant
    try:
        plan = service.approve(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            receipt_id=body.receipt_id,
            actor_id=_actor_id(),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _plan_response(plan)


async def revise_plan(
    plan_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanResponse:
    del tenant
    try:
        plan = service.revise(
            plan_id=plan_id,
            project_id=workspace.workspace_id,
            actor_id=_actor_id(),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _plan_response(plan)


async def get_ready(
    plan_id: str,
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
) -> InvestmentPlanReadyResponse:
    del tenant
    try:
        plan, receipt = service.get_ready(plan_id=plan_id, project_id=workspace.workspace_id)
    except PlanningError as exc:
        raise planning_error(exc) from exc
    status = capability_ready_status(plan=plan, receipt=receipt)
    if receipt is None or status is not InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY:
        return InvestmentPlanReadyResponse(
            plan_id=plan_id,
            status=status.value,
            receipt_id=None if receipt is None else receipt.receipt_id,
            error_codes=() if receipt is None else receipt.error_codes,
        )
    return InvestmentPlanReadyResponse(
        plan_id=plan_id,
        status=status.value,
        receipt_id=receipt.receipt_id,
        error_codes=receipt.error_codes,
    )


_ROUTES: tuple[tuple[str, str, object, str, type | None], ...] = (
    ("", "GET", list_plans, "listInvestmentPlans", InvestmentPlanListResponse),
    ("", "POST", create_plan, "createInvestmentPlan", InvestmentPlanResponse),
    ("/{plan_id}", "GET", get_plan, "getInvestmentPlan", InvestmentPlanResponse),
    ("/{plan_id}/template", "POST", create_template, "createInvestmentPlanTemplate", BudgetSourceResponse),
    (
        "/{plan_id}/sources/drive",
        "POST",
        bind_drive_source,
        "bindInvestmentPlanDriveSource",
        BudgetDriveSourceAcceptedResponse,
    ),
    ("/{plan_id}/mapping", "POST", confirm_mapping, "confirmInvestmentPlanMapping", BudgetMappingResponse),
    (
        "/{plan_id}/validate",
        "POST",
        validate_plan,
        "validateInvestmentPlan",
        InvestmentPlanValidationResponse,
    ),
    ("/{plan_id}/save-version", "POST", save_version, "saveInvestmentPlanVersion", BudgetSourceResponse),
    ("/{plan_id}/approve", "POST", approve_plan, "approveInvestmentPlan", InvestmentPlanResponse),
    ("/{plan_id}/revise", "POST", revise_plan, "reviseInvestmentPlan", InvestmentPlanResponse),
    ("/{plan_id}/ready", "GET", get_ready, "getInvestmentPlanReady", InvestmentPlanReadyResponse),
)

for path, method, endpoint, operation_id, response_model in _ROUTES:
    canonical_router.add_api_route(
        path,
        endpoint,
        methods=[method],
        operation_id=operation_id,
        response_model=response_model,
    )
    workspace_alias_router.add_api_route(
        path,
        endpoint,
        methods=[method],
        operation_id=f"{operation_id}WorkspaceAlias",
        response_model=response_model,
        include_in_schema=False,
    )

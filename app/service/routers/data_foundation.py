"""Workspace-scoped Data Foundation API. Tenant is never accepted from the client."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Workspace
from app.core.tenancy import TenantContext, require_tenant
from app.data_foundation.context import DataFoundationContext, context_from_tenant
from datetime import UTC, datetime

from app.data_foundation.contracts import (
    BusinessProfileSnapshot,
    DiscoveryHints,
    SourceContinuityPlan,
    SourceContract,
)
from app.data_foundation.enums import (
    ConnectionLifecycle,
    CoverageView,
    CutoffOrigin,
    CycleCadence,
    FoundationPlanSection,
    TargetWindowStatus,
    TransformId,
)
from app.data_foundation.service import DataFoundationService
from app.service.data_foundation_models import (
    ApprovePlanRequest,
    BindSourceRequest,
    CompileFoundationPlanRequest,
    CompileTransformRequest,
    MaterializeDriveRequest,
    CreateCycleRequest,
    DataFoundationOverviewResponse,
    DiscoveryHintsRequest,
    ExecutePlanRequest,
    LoadSnapshotRequest,
    ReplaceSourceRequest,
    ResolveDecisionRequest,
    ReviseCycleRequest,
    TransitionRequest,
    UpdateCycleRequest,
)
from app.service.dependencies import authenticated_tenant, authorized_workspace
from app.service.errors import resource_not_found, validation_error

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/data-foundation",
    tags=["data-foundation"],
)


def get_data_foundation(request: Request) -> DataFoundationService:
    service = getattr(request.app.state, "data_foundation", None)
    if service is None:
        raise RuntimeError("Data Foundation service is not configured.")
    return service


def _context(
    workspace: Workspace,
    tenant: TenantContext,
    request: Request,
) -> DataFoundationContext:
    del tenant
    repo = request.app.state.control_plane
    tenant_id = require_tenant().tenant_id
    bq = repo.get_bigquery_binding(tenant_id=tenant_id, workspace_id=workspace.workspace_id)
    drive = repo.get_drive_binding(tenant_id=tenant_id, workspace_id=workspace.workspace_id)
    return context_from_tenant(
        workspace_id=workspace.workspace_id,
        destination_project_id=bq.destination_project_id if bq else None,
        destination_location=bq.location if bq else None,
        source_project_ids=bq.source_project_ids if bq else (),
        source_dataset_ids=bq.source_dataset_ids if bq else (),
        drive_root_folder_id=drive.root_folder_id if drive else None,
        google_connection_id=bq.connection_id if bq else (drive.connection_id if drive else None),
        bq_lifecycle=ConnectionLifecycle.AUTHORIZED if bq else ConnectionLifecycle.NOT_CONNECTED,
        drive_lifecycle=ConnectionLifecycle.AUTHORIZED
        if drive
        else ConnectionLifecycle.NOT_CONNECTED,
        write_verified=bool(bq and bq.write_verified),
        read_verified=bool(bq and bq.read_verified),
    )


@router.get(
    "", operation_id="getDataFoundationOverview", response_model=DataFoundationOverviewResponse
)
async def get_overview(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> DataFoundationOverviewResponse:
    overview = service.get_overview(_context(workspace, tenant, request))
    return DataFoundationOverviewResponse(
        workspace_id=overview.workspace_id,
        phase=overview.phase,
        requirement_count=overview.requirement_count,
        candidate_count=overview.candidate_count,
        source_ready_count=overview.source_ready_count,
        foundation_ready=overview.foundation_ready,
        live_cloud_proof=overview.live_cloud_proof,
        connections=[item.model_dump(mode="json") for item in overview.connections],
    )


@router.post("/requirements", operation_id="loadDataFoundationRequirements")
async def load_requirements(
    body: LoadSnapshotRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    snapshot = BusinessProfileSnapshot.model_validate(body.snapshot)
    compiled = service.load_business_snapshot(_context(workspace, tenant, request), snapshot)
    return compiled.model_dump(mode="json")


@router.get("/requirements", operation_id="getDataFoundationRequirements")
async def get_requirements(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_evidence_requirements(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/discover", operation_id="discoverDataFoundation")
async def discover(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.discover(_context(workspace, tenant, request)).model_dump(mode="json")
    except PermissionError as exc:
        raise validation_error([]) from exc


@router.get("/candidates", operation_id="listDataFoundationCandidates")
async def list_candidates(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.list_source_candidates(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/sources", operation_id="bindDataFoundationSource")
async def bind_source(
    body: BindSourceRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    contract = SourceContract(
        grain=body.grain,
        date_field=body.date_field,
        date_format=body.date_format,
        unique_keys=tuple(body.unique_keys),
        required_fields=tuple(body.required_fields),
        currency=body.currency,
        timezone=body.timezone,
    )
    binding = service.bind_source(
        _context(workspace, tenant, request),
        candidate_id=body.candidate_id,
        contract=contract,
        requirement_id=body.requirement_id,
        governance_import_ready=body.governance_import_ready,
    )
    return binding.model_dump(mode="json")


@router.post("/sources/{source_id}/assess", operation_id="assessDataFoundationSource")
async def assess_source(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.assess_source(_context(workspace, tenant, request), source_id).model_dump(
        mode="json"
    )


@router.post("/transformation-plans", operation_id="compileDataFoundationTransformPlan")
async def compile_transform(
    body: CompileTransformRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    actions = [TransformId(item) for item in body.action_ids]
    return service.compile_transformation_plan(
        _context(workspace, tenant, request),
        source_id=body.source_id,
        action_ids=actions,
        parameters=body.parameters,
    ).model_dump(mode="json")


@router.post("/plans", operation_id="compileDataFoundationPlan")
async def compile_foundation_plan(
    body: CompileFoundationPlanRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.compile_foundation_plan(
        _context(workspace, tenant, request),
        include_drive=body.include_drive,
        dv360=body.dv360,
    ).model_dump(mode="json")


@router.post("/drive/layout", operation_id="ensureDataFoundationDriveLayout")
async def ensure_drive_layout(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.ensure_drive_layout(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except PermissionError as exc:
        raise validation_error(str(exc)) from exc


@router.get("/drive/layout", operation_id="getDataFoundationDriveLayout")
async def get_drive_layout(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_drive_layout(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/sources/{source_id}/materialize-drive", operation_id="materializeDataFoundationDriveSource")
async def materialize_drive_source(
    source_id: str,
    body: MaterializeDriveRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.materialize_drive_source(
            _context(workspace, tenant, request),
            source_id=source_id,
            drive_file_id=body.drive_file_id,
            sheet_name=body.sheet_name,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/alignment", operation_id="getDataFoundationAlignment")
async def get_alignment(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.get_cross_source_alignment(_context(workspace, tenant, request)).model_dump(
        mode="json"
    )


@router.post("/plans/approve", operation_id="approveDataFoundationPlan")
async def approve_plan(
    body: ApprovePlanRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    sections = (
        tuple(FoundationPlanSection(item) for item in body.sections)
        if body.sections
        else None
    )
    return service.approve_plan(
        _context(workspace, tenant, request), plan_id=body.plan_id, sections=sections
    ).model_dump(mode="json")


@router.post("/plans/execute", operation_id="executeDataFoundationPlan")
async def execute_plan(
    body: ExecutePlanRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.execute_plan(
        _context(workspace, tenant, request), plan_id=body.plan_id
    ).model_dump(mode="json")


@router.post("/decisions", operation_id="resolveDataFoundationDecision")
async def resolve_decision(
    body: ResolveDecisionRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.resolve_user_decision(
        _context(workspace, tenant, request),
        source_id=body.source_id,
        kind=body.kind,
        value=body.value,
    ).model_dump(mode="json")


@router.post("/ready", operation_id="evaluateDataFoundationReady")
async def evaluate_ready(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.evaluate_data_foundation_ready(_context(workspace, tenant, request)).model_dump(
        mode="json"
    )


@router.post("/discover/hints", operation_id="setDataFoundationDiscoveryHints")
async def set_hints(
    body: DiscoveryHintsRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    hints = DiscoveryHints(
        tenant_id=require_tenant().tenant_id,
        workspace_id=workspace.workspace_id,
        datasets_to_prioritize=tuple(body.datasets_to_prioritize),
        only_inspect_prioritized_datasets=body.only_inspect_prioritized_datasets,
        drive_sources_or_paths_to_prioritize=tuple(body.drive_sources_or_paths_to_prioritize),
        persisted_at=datetime.now(UTC),
    )
    return service.set_discovery_hints(_context(workspace, tenant, request), hints).model_dump(
        mode="json"
    )


@router.post("/cycles", operation_id="createMeasurementCycle")
async def create_cycle(
    body: CreateCycleRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.create_cycle(
        _context(workspace, tenant, request),
        name=body.name,
        cadence=CycleCadence(body.cadence),
        business_profile_snapshot_id=body.business_profile_snapshot_id,
        data_cutoff=body.data_cutoff,
        cutoff_origin=CutoffOrigin(body.cutoff_origin) if body.cutoff_origin else None,
        target_window_start=body.target_window_start,
        target_window_end=body.target_window_end,
        target_window_status=TargetWindowStatus(body.target_window_status),
    ).model_dump(mode="json")


@router.get("/cycles", operation_id="listMeasurementCycles")
async def list_cycles(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    rows = service.list_cycles(_context(workspace, tenant, request))
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/cycles/{cycle_id}", operation_id="getMeasurementCycle")
async def get_cycle(
    cycle_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_cycle(_context(workspace, tenant, request), cycle_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.patch("/cycles/{cycle_id}", operation_id="updateMeasurementCycle")
async def update_cycle(
    cycle_id: str,
    body: UpdateCycleRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    updates = {key: value for key, value in body.model_dump(mode="json").items() if value is not None}
    if "cadence" in updates:
        updates["cadence"] = CycleCadence(updates["cadence"])
    if "cutoff_origin" in updates:
        updates["cutoff_origin"] = CutoffOrigin(updates["cutoff_origin"])
    if "target_window_status" in updates:
        updates["target_window_status"] = TargetWindowStatus(updates["target_window_status"])
    try:
        return service.update_cycle(
            _context(workspace, tenant, request), cycle_id, **updates
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc
    except PermissionError as exc:
        raise validation_error([]) from exc


@router.post("/cycles/{cycle_id}/coverage", operation_id="computeMeasurementCycleCoverage")
async def compute_coverage(
    cycle_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
    view: str = "REQUIRED_EVIDENCE",
) -> dict[str, Any]:
    try:
        return service.compute_coverage(
            _context(workspace, tenant, request),
            cycle_id,
            view=CoverageView(view),
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/cycles/{cycle_id}/coverage", operation_id="getMeasurementCycleCoverage")
async def get_coverage(
    cycle_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_coverage(_context(workspace, tenant, request), cycle_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/cycles/{cycle_id}/shared-window", operation_id="getMeasurementCycleSharedWindow")
async def get_shared_window(
    cycle_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_shared_window(_context(workspace, tenant, request), cycle_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/cycles/{cycle_id}/coverage/gaps/{gap_id}", operation_id="getMeasurementCycleCoverageGap")
async def get_gap(
    cycle_id: str,
    gap_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_coverage_gap(
            _context(workspace, tenant, request), cycle_id, gap_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/cycles/{cycle_id}/revise", operation_id="reviseMeasurementCycle")
async def revise_cycle(
    cycle_id: str,
    body: ReviseCycleRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.revise_cycle(
            _context(workspace, tenant, request),
            cycle_id,
            name=body.name,
            business_profile_snapshot_id=body.business_profile_snapshot_id,
            data_cutoff=body.data_cutoff,
            cutoff_origin=CutoffOrigin(body.cutoff_origin) if body.cutoff_origin else None,
            target_window_start=body.target_window_start,
            target_window_end=body.target_window_end,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/cycles/{cycle_id}/requirements", operation_id="getMeasurementCycleRequirements")
async def get_cycle_requirements(
    cycle_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        service.get_cycle(_context(workspace, tenant, request), cycle_id)
        return service.get_evidence_requirements(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/sources/{source_id}/preview", operation_id="previewDataFoundationSource")
async def preview_source(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.preview_source(_context(workspace, tenant, request), source_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/sources/{source_id}/scope", operation_id="getDataFoundationSourceScope")
async def get_scope(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_source_scope(_context(workspace, tenant, request), source_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/sources/{source_id}/physical", operation_id="getDataFoundationSourcePhysical")
async def get_physical(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_physical_metadata(
            _context(workspace, tenant, request), source_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/sources/{source_id}/ready", operation_id="evaluateDataFoundationSourceReady")
async def source_ready(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.evaluate_source_ready(
            _context(workspace, tenant, request), source_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/transitions", operation_id="putDataFoundationSourceTransition")
async def put_transition(
    body: TransitionRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.put_transition(
        _context(workspace, tenant, request),
        SourceContinuityPlan(
            historical_source_id=body.historical_source_id,
            ongoing_source_id=body.ongoing_source_id,
            cutoff=body.cutoff,
            overlap_handling=body.overlap_handling,
            reconciliation_required=body.reconciliation_required,
            canonical_precedence=body.canonical_precedence,
        ),
    ).model_dump(mode="json")


@router.get("/canonical-preview", operation_id="getDataFoundationCanonicalPreview")
async def canonical_preview(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.canonical_preview(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except (KeyError, PermissionError) as exc:
        if isinstance(exc, KeyError):
            raise resource_not_found() from exc
        raise validation_error([]) from exc


@router.get("/sources/{source_id}/quality-overview", operation_id="getDataFoundationQualityOverview")
async def quality_overview(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_quality_overview(_context(workspace, tenant, request), source_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/sources/{source_id}/health", operation_id="getDataFoundationSourceHealth")
async def source_health(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        payload = service.get_source_health(_context(workspace, tenant, request), source_id)
    except KeyError as exc:
        raise resource_not_found() from exc
    return {
        key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for key, value in payload.items()
    }


@router.post("/sources/{source_id}/retire", operation_id="retireDataFoundationSource")
async def retire_source(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.retire_source(_context(workspace, tenant, request), source_id).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/sources/{source_id}/replace", operation_id="replaceDataFoundationSource")
async def replace_source(
    source_id: str,
    body: ReplaceSourceRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    contract = SourceContract(
        grain=body.grain,
        date_field=body.date_field,
        date_format=body.date_format,
        unique_keys=tuple(body.unique_keys),
        required_fields=tuple(body.required_fields),
        currency=body.currency,
        timezone=body.timezone,
    )
    try:
        return service.replace_source(
            _context(workspace, tenant, request),
            source_id=source_id,
            candidate_id=body.candidate_id,
            contract=contract,
            governance_import_ready=body.governance_import_ready,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/sources/{source_id}/reauthorize", operation_id="reauthorizeDataFoundationSource")
async def reauthorize_source(
    source_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        result = service.reauthorize_source(_context(workspace, tenant, request), source_id)
    except KeyError as exc:
        raise resource_not_found() from exc
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else {"status": "ok"}


@router.get("/file-series", operation_id="listDataFoundationFileSeries")
async def list_file_series(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    rows = service.list_file_series(_context(workspace, tenant, request))
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/intelligence-brief", operation_id="getDataIntelligenceBrief")
async def get_intelligence_brief(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    try:
        return service.get_intelligence_brief(_context(workspace, tenant, request)).model_dump(
            mode="json"
        )
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/intelligence-brief", operation_id="compileDataIntelligenceBrief")
async def compile_intelligence_brief(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    return service.compile_intelligence_brief(_context(workspace, tenant, request)).model_dump(
        mode="json"
    )


@router.get("/receipts", operation_id="listDataFoundationReceipts")
async def list_receipts(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[DataFoundationService, Depends(get_data_foundation)],
) -> dict[str, Any]:
    rows = service.get_receipts(_context(workspace, tenant, request))
    return {
        "items": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in rows
        ]
    }

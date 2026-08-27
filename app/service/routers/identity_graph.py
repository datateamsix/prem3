"""Project-scoped Marketing Identity Graph API. Tenant is never accepted from the client."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import TenantContext, require_tenant
from app.identity_graph.enums import (
    AudienceRefreshCadence,
    AudienceSourceKind,
    AudienceStatus,
    AudienceType,
    CampaignOwnerType,
    CampaignStatus,
    GA4TopologyKind,
    MarketKind,
    PersonaStatus,
    SourceOverlapPolicy,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.service import CampaignIdentityService
from app.service.dependencies import authenticated_tenant, get_control_plane
from app.service.errors import ProblemFieldError, resource_not_found, validation_error
from app.service.identity_graph_models import (
    CreateIdentityGraphAudienceRequest,
    CreateIdentityGraphCampaignRequest,
    CreateIdentityGraphMarketRequest,
    CreateIdentityGraphPersonaRequest,
    CreateIdentityGraphSourceRequest,
    DiscoverIdentityGraphSourcesRequest,
    PatchIdentityGraphAudienceRequest,
    PatchIdentityGraphCampaignRequest,
    PatchIdentityGraphPersonaRequest,
)

router = APIRouter(
    prefix="/v1/projects/{project_id}/identity-graph",
    tags=["identity-graph"],
)


def get_identity_graph(request: Request) -> CampaignIdentityService:
    service = getattr(request.app.state, "identity_graph", None)
    if service is None:
        raise RuntimeError("Identity Graph service is not configured.")
    return service


def _require_project(
    *,
    tenant: TenantContext,
    repo: ControlPlaneRepository,
    project_id: str,
) -> None:
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=project_id
    )
    if workspace is None:
        raise resource_not_found()


def _raise_identity_graph_error(exc: IdentityGraphError) -> None:
    if exc.code in {
        "UNKNOWN_CAMPAIGN",
        "UNKNOWN_BINDING",
        "UNKNOWN_PERSONA",
        "UNKNOWN_AUDIENCE",
    }:
        raise resource_not_found() from exc
    raise validation_error(
        [ProblemFieldError(field="campaign", message=str(exc))]
    ) from exc


@router.get("", operation_id="getIdentityGraph")
async def get_identity_graph_overview(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    return service.overview(
        tenant_id=tenant.tenant_id, project_id=project_id
    ).model_dump(mode="json")


@router.get("/campaigns", operation_id="listIdentityGraphCampaigns")
async def list_campaigns(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    market_id: str | None = None,
    channel_id: str | None = None,
    parent_campaign_id: str | None = None,
    planned_start_date: str | None = None,
    planned_end_date: str | None = None,
    owner_ref: str | None = None,
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    status_value = None
    if status_filter is not None:
        try:
            status_value = CampaignStatus(status_filter)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported campaign status.")]
            ) from exc
    rows = service.list_campaigns(
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        status=status_value,
        market_id=market_id,
        channel_id=channel_id,
        parent_campaign_id=parent_campaign_id,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        owner_ref=owner_ref,
    )
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post(
    "/campaigns",
    operation_id="createIdentityGraphCampaign",
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    project_id: str,
    body: CreateIdentityGraphCampaignRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    status_value = CampaignStatus.PLANNED
    if body.status is not None:
        try:
            status_value = CampaignStatus(body.status)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported campaign status.")]
            ) from exc
    owner_type = None
    if body.owner_type is not None:
        try:
            owner_type = CampaignOwnerType(body.owner_type)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="owner_type", message="Unsupported owner type.")]
            ) from exc
    try:
        result = service.create_campaign(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            name=body.name,
            actor_id=ctx.user_id or "unknown",
            description=body.description,
            status=status_value,
            market_ids=tuple(body.market_ids),
            channel_ids=tuple(body.channel_ids),
            parent_campaign_id=body.parent_campaign_id,
            planned_start_date=body.planned_start_date,
            planned_end_date=body.planned_end_date,
            utm_campaign=body.utm_campaign,
            owner_type=owner_type,
            owner_ref=body.owner_ref,
            owner_label=body.owner_label,
            objective_ref=body.objective_ref,
            objective_label=body.objective_label,
            persona_ids=tuple(body.persona_ids),
            audience_ids=tuple(body.audience_ids),
        )
    except IdentityGraphError as exc:
        _raise_identity_graph_error(exc)
        raise
    return result.model_dump(mode="json")


@router.get("/campaigns/{campaign_id}", operation_id="getIdentityGraphCampaign")
async def get_campaign(
    project_id: str,
    campaign_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        campaign = service.get_campaign(
            tenant_id=tenant.tenant_id, project_id=project_id, campaign_id=campaign_id
        )
    except IdentityGraphError as exc:
        _raise_identity_graph_error(exc)
        raise
    return campaign.model_dump(mode="json")


@router.patch("/campaigns/{campaign_id}", operation_id="patchIdentityGraphCampaign")
async def patch_campaign(
    project_id: str,
    campaign_id: str,
    body: PatchIdentityGraphCampaignRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    updates = body.model_dump(exclude_unset=True)
    try:
        campaign = service.update_campaign(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            campaign_id=campaign_id,
            updates=updates,
        )
    except IdentityGraphError as exc:
        _raise_identity_graph_error(exc)
        raise
    return campaign.model_dump(mode="json")


@router.get("/campaigns/{campaign_id}/tracking", operation_id="getIdentityGraphCampaignTracking")
async def get_campaign_tracking(
    project_id: str,
    campaign_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        instructions = service.tracking_instructions(
            tenant_id=tenant.tenant_id, project_id=project_id, campaign_id=campaign_id
        )
    except IdentityGraphError as exc:
        _raise_identity_graph_error(exc)
        raise
    return instructions.model_dump(mode="json")


@router.get("/campaigns/{campaign_id}/children", operation_id="getIdentityGraphCampaignChildren")
async def get_campaign_children(
    project_id: str,
    campaign_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        rows = service.children(
            tenant_id=tenant.tenant_id, project_id=project_id, campaign_id=campaign_id
        )
    except IdentityGraphError as exc:
        _raise_identity_graph_error(exc)
        raise
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/campaigns/{campaign_id}/lineage", operation_id="getIdentityGraphCampaignLineage")
async def get_campaign_lineage(
    project_id: str,
    campaign_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        lineage = service.lineage(
            tenant_id=tenant.tenant_id, project_id=project_id, campaign_id=campaign_id
        )
    except IdentityGraphError as exc:
        _raise_identity_graph_error(exc)
        raise
    return lineage.model_dump(mode="json")


@router.get("/sources", operation_id="listIdentityGraphSources")
async def list_sources(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    rows = service.list_sources(tenant_id=tenant.tenant_id, project_id=project_id)
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post(
    "/sources",
    operation_id="createIdentityGraphSource",
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    project_id: str,
    body: CreateIdentityGraphSourceRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    overlap = None
    if body.overlap_policy is not None:
        try:
            overlap = SourceOverlapPolicy(body.overlap_policy)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="overlap_policy", message="Unsupported overlap policy.")]
            ) from exc
    try:
        source = service.upsert_ga4_source(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            ga4_property_id=body.ga4_property_id,
            bq_project_id=body.bq_project_id,
            bq_dataset_id=body.bq_dataset_id,
            bq_location=body.bq_location,
            stream_ids=tuple(body.stream_ids),
            declared_market_ids=tuple(body.declared_market_ids),
            coverage_start=body.coverage_start,
            coverage_end=body.coverage_end,
            traffic_source_capability=body.traffic_source_capability,
            freshness_state=body.freshness_state,
            overlap_policy=overlap,
        )
        if body.topology_kind is not None:
            try:
                kind = GA4TopologyKind(body.topology_kind)
            except ValueError as exc:
                raise validation_error(
                    [ProblemFieldError(field="topology_kind", message="Unsupported topology kind.")]
                ) from exc
            service.upsert_topology(
                tenant_id=ctx.tenant_id,
                project_id=project_id,
                topology_kind=kind,
                source_binding_ids=(source.ga4_source_binding_id,),
                overlap_policy=overlap,
            )
    except IdentityGraphError as exc:
        raise validation_error(
            [ProblemFieldError(field="source", message=str(exc))]
        ) from exc
    return source.model_dump(mode="json")


@router.post("/sources/discover", operation_id="discoverIdentityGraphSources")
async def discover_sources(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
    body: DiscoverIdentityGraphSourcesRequest | None = None,
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    payload = body or DiscoverIdentityGraphSourcesRequest()
    tables = tuple(item.model_dump(mode="json") for item in payload.tables)
    result = service.discover_ga4_sources(
        tenant_id=ctx.tenant_id,
        project_id=project_id,
        tables=tables,
    )
    return result.model_dump(mode="json")


@router.get("/markets", operation_id="listIdentityGraphMarkets")
async def list_markets(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    rows = service.list_markets(tenant_id=tenant.tenant_id, project_id=project_id)
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post(
    "/markets",
    operation_id="createIdentityGraphMarket",
    status_code=status.HTTP_201_CREATED,
)
async def create_market(
    project_id: str,
    body: CreateIdentityGraphMarketRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    kind = MarketKind.CUSTOM
    if body.market_kind is not None:
        try:
            kind = MarketKind(body.market_kind)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="market_kind", message="Unsupported market kind.")]
            ) from exc
    try:
        market = service.create_market(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            name=body.name,
            actor_id=ctx.user_id or "unknown",
            description=body.description,
            market_kind=kind,
            country_codes=tuple(body.country_codes),
            region_codes=tuple(body.region_codes),
        )
    except IdentityGraphError as exc:
        raise validation_error(
            [ProblemFieldError(field="market", message=str(exc))]
        ) from exc
    return market.model_dump(mode="json")


@router.get("/ga4-topology", operation_id="getIdentityGraphGa4Topology")
async def get_ga4_topology(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    topology = service.get_ga4_topology(tenant_id=tenant.tenant_id, project_id=project_id)
    receipt = service.store.get_topology_receipt(
        tenant_id=tenant.tenant_id, project_id=project_id
    )
    return {
        "topology": None if topology is None else topology.model_dump(mode="json"),
        "receipt": None if receipt is None else receipt.model_dump(mode="json"),
        "issues": () if topology is not None else ("TOPOLOGY_NOT_CONFIGURED",),
    }


@router.post("/ga4-topology/validate", operation_id="validateIdentityGraphGa4Topology")
async def validate_ga4_topology(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    receipt = service.validate_ga4_topology(tenant_id=ctx.tenant_id, project_id=project_id)
    return receipt.model_dump(mode="json")


@router.get("/mappings", operation_id="listIdentityGraphMappings")
async def list_mappings(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    rows = service.list_mappings(tenant_id=tenant.tenant_id, project_id=project_id)
    return {"items": [item.model_dump(mode="json") for item in rows]}


def _parse_owner_type(value: str | None) -> CampaignOwnerType | None:
    if value is None:
        return None
    try:
        return CampaignOwnerType(value)
    except ValueError as exc:
        raise validation_error(
            [ProblemFieldError(field="owner_type", message="Unsupported owner type.")]
        ) from exc


@router.get("/personas", operation_id="listIdentityGraphPersonas")
async def list_personas(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    market_id: str | None = None,
    owner_ref: str | None = None,
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    status_value = None
    if status_filter is not None:
        try:
            status_value = PersonaStatus(status_filter)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported persona status.")]
            ) from exc
    rows = service.list_personas(
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        status=status_value,
        market_id=market_id,
        owner_ref=owner_ref,
    )
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post(
    "/personas",
    operation_id="createIdentityGraphPersona",
    status_code=status.HTTP_201_CREATED,
)
async def create_persona(
    project_id: str,
    body: CreateIdentityGraphPersonaRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    status_value = PersonaStatus.DRAFT
    if body.status is not None:
        try:
            status_value = PersonaStatus(body.status)
        except ValueError as extra:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported persona status.")]
            ) from extra
    try:
        persona = service.create_persona(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            name=body.name,
            actor_id=ctx.user_id or "unknown",
            description=body.description,
            status=status_value,
            market_ids=tuple(body.market_ids),
            lifecycle_stage_refs=tuple(body.lifecycle_stage_refs),
            business_segment_ref=body.business_segment_ref,
            business_profile_snapshot_id=body.business_profile_snapshot_id,
            owner_type=_parse_owner_type(body.owner_type),
            owner_ref=body.owner_ref,
            owner_label=body.owner_label,
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return persona.model_dump(mode="json")


@router.get("/personas/{persona_id}", operation_id="getIdentityGraphPersona")
async def get_persona(
    project_id: str,
    persona_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        persona = service.get_persona(
            tenant_id=tenant.tenant_id, project_id=project_id, persona_id=persona_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return persona.model_dump(mode="json")


@router.patch("/personas/{persona_id}", operation_id="patchIdentityGraphPersona")
async def patch_persona(
    project_id: str,
    persona_id: str,
    body: PatchIdentityGraphPersonaRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    updates = body.model_dump(exclude_unset=True)
    try:
        persona = service.update_persona(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            persona_id=persona_id,
            updates=updates,
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return persona.model_dump(mode="json")


@router.get("/personas/{persona_id}/audiences", operation_id="listIdentityGraphPersonaAudiences")
async def list_persona_audiences(
    project_id: str,
    persona_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        rows = service.persona_audiences(
            tenant_id=tenant.tenant_id, project_id=project_id, persona_id=persona_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/personas/{persona_id}/campaigns", operation_id="listIdentityGraphPersonaCampaigns")
async def list_persona_campaigns(
    project_id: str,
    persona_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        rows = service.persona_campaigns(
            tenant_id=tenant.tenant_id, project_id=project_id, persona_id=persona_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/audiences", operation_id="listIdentityGraphAudiences")
async def list_audiences(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    audience_type: str | None = None,
    source_kind: str | None = None,
    market_id: str | None = None,
    persona_id: str | None = None,
    owner_ref: str | None = None,
    parent_audience_id: str | None = None,
    effective_start_date: str | None = None,
    effective_end_date: str | None = None,
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    status_value = None
    if status_filter is not None:
        try:
            status_value = AudienceStatus(status_filter)
        except ValueError as extra:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported audience status.")]
            ) from extra
    type_value = None
    if audience_type is not None:
        try:
            type_value = AudienceType(audience_type)
        except ValueError as extra:
            raise validation_error(
                [ProblemFieldError(field="audience_type", message="Unsupported audience type.")]
            ) from extra
    kind_value = None
    if source_kind is not None:
        try:
            kind_value = AudienceSourceKind(source_kind)
        except ValueError as extra:
            raise validation_error(
                [ProblemFieldError(field="source_kind", message="Unsupported source kind.")]
            ) from extra
    rows = service.list_audiences(
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        status=status_value,
        audience_type=type_value,
        source_kind=kind_value,
        market_id=market_id,
        persona_id=persona_id,
        owner_ref=owner_ref,
        parent_audience_id=parent_audience_id,
        effective_start_date=effective_start_date,
        effective_end_date=effective_end_date,
    )
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post(
    "/audiences",
    operation_id="createIdentityGraphAudience",
    status_code=status.HTTP_201_CREATED,
)
async def create_audience(
    project_id: str,
    body: CreateIdentityGraphAudienceRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        type_value = AudienceType(body.audience_type)
    except ValueError as extra:
        raise validation_error(
            [ProblemFieldError(field="audience_type", message="Unsupported audience type.")]
        ) from extra
    try:
        kind_value = AudienceSourceKind(body.source_kind)
    except ValueError as extra:
        raise validation_error(
            [ProblemFieldError(field="source_kind", message="Unsupported source kind.")]
        ) from extra
    status_value = AudienceStatus.DRAFT
    if body.status is not None:
        try:
            status_value = AudienceStatus(body.status)
        except ValueError as extra:
            raise validation_error(
                [ProblemFieldError(field="status", message="Unsupported audience status.")]
            ) from extra
    cadence = None
    if body.refresh_cadence is not None:
        try:
            cadence = AudienceRefreshCadence(body.refresh_cadence)
        except ValueError as extra:
            raise validation_error(
                [
                    ProblemFieldError(
                        field="refresh_cadence", message="Unsupported refresh cadence."
                    )
                ]
            ) from extra
    try:
        audience = service.create_audience(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            name=body.name,
            actor_id=ctx.user_id or "unknown",
            audience_type=type_value,
            source_kind=kind_value,
            description=body.description,
            status=status_value,
            source_ref=body.source_ref,
            market_ids=tuple(body.market_ids),
            persona_ids=tuple(body.persona_ids),
            parent_audience_id=body.parent_audience_id,
            definition_summary=body.definition_summary,
            criteria_summary=body.criteria_summary,
            effective_start_date=body.effective_start_date,
            effective_end_date=body.effective_end_date,
            refresh_cadence=cadence,
            owner_type=_parse_owner_type(body.owner_type),
            owner_ref=body.owner_ref,
            owner_label=body.owner_label,
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return audience.model_dump(mode="json")


@router.get("/audiences/{audience_id}", operation_id="getIdentityGraphAudience")
async def get_audience(
    project_id: str,
    audience_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        audience = service.get_audience(
            tenant_id=tenant.tenant_id, project_id=project_id, audience_id=audience_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return audience.model_dump(mode="json")


@router.patch("/audiences/{audience_id}", operation_id="patchIdentityGraphAudience")
async def patch_audience(
    project_id: str,
    audience_id: str,
    body: PatchIdentityGraphAudienceRequest,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    ctx = require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    updates = body.model_dump(exclude_unset=True)
    try:
        audience = service.update_audience(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            audience_id=audience_id,
            updates=updates,
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return audience.model_dump(mode="json")


@router.get("/audiences/{audience_id}/personas", operation_id="listIdentityGraphAudiencePersonas")
async def list_audience_personas(
    project_id: str,
    audience_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        rows = service.audience_personas(
            tenant_id=tenant.tenant_id, project_id=project_id, audience_id=audience_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/audiences/{audience_id}/campaigns", operation_id="listIdentityGraphAudienceCampaigns")
async def list_audience_campaigns(
    project_id: str,
    audience_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        rows = service.audience_campaigns(
            tenant_id=tenant.tenant_id, project_id=project_id, audience_id=audience_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/audiences/{audience_id}/children", operation_id="listIdentityGraphAudienceChildren")
async def list_audience_children(
    project_id: str,
    audience_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        rows = service.audience_children(
            tenant_id=tenant.tenant_id, project_id=project_id, audience_id=audience_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/audiences/{audience_id}/lineage", operation_id="getIdentityGraphAudienceLineage")
async def get_audience_lineage(
    project_id: str,
    audience_id: str,
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
    service: Annotated[CampaignIdentityService, Depends(get_identity_graph)],
) -> dict[str, Any]:
    require_tenant()
    _require_project(tenant=tenant, repo=repo, project_id=project_id)
    try:
        lineage = service.audience_lineage(
            tenant_id=tenant.tenant_id, project_id=project_id, audience_id=audience_id
        )
    except IdentityGraphError as extra:
        _raise_identity_graph_error(extra)
        raise
    return lineage.model_dump(mode="json")

"""Workspace-scoped Business IQ API. Tenant is never accepted from the client."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.business_iq.enums import ClarificationAnswer
from app.business_iq.service import BusinessIqService
from app.control_plane.models import Workspace
from app.core.tenancy import TenantContext, require_tenant
from app.service.business_iq_models import (
    BusinessProfileRequest,
    ClarificationAnswerRequest,
    ClarificationCreateRequest,
    ProposalCreateRequest,
    ProposalDecideRequest,
)
from app.service.dependencies import authenticated_tenant, authorized_workspace
from app.service.errors import resource_not_found, validation_error

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/business-iq",
    tags=["business-iq"],
)


def get_business_iq(request: Request) -> BusinessIqService:
    service = getattr(request.app.state, "business_iq", None)
    if service is None:
        raise RuntimeError("Business IQ service is not configured.")
    return service


def _org_name(request: Request, tenant_id: str) -> str | None:
    repo = request.app.state.control_plane
    tenant = repo.get_tenant(tenant_id)
    return getattr(tenant, "display_name", None) if tenant is not None else None


@router.get("/profile", operation_id="getBusinessProfile")
async def get_profile(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        return service.get_profile(
            tenant_id=require_tenant().tenant_id, workspace_id=workspace.workspace_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/profile", operation_id="createBusinessProfile")
async def create_profile(
    body: BusinessProfileRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    request: Request,
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    ctx = require_tenant()
    try:
        return service.create_profile(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.workspace_id,
            actor_id=ctx.user_id or "unknown",
            payload=body.model_dump(mode="json"),
            organization_display_name=_org_name(request, ctx.tenant_id),
        ).model_dump(mode="json")
    except ValueError as exc:
        raise validation_error([]) from exc


@router.patch("/profile", operation_id="patchBusinessProfile")
async def patch_profile(
    body: BusinessProfileRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    ctx = require_tenant()
    payload = {key: value for key, value in body.model_dump(mode="json").items() if value not in (None, [])}
    try:
        return service.patch_profile(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.workspace_id,
            actor_id=ctx.user_id or "unknown",
            payload=payload,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/profile/versions", operation_id="listBusinessProfileVersions")
async def list_versions(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        rows = service.list_versions(
            tenant_id=require_tenant().tenant_id, workspace_id=workspace.workspace_id
        )
    except KeyError as exc:
        raise resource_not_found() from exc
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.get("/profile/snapshots/{snapshot_id}", operation_id="getBusinessProfileSnapshot")
async def get_snapshot(
    snapshot_id: str,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del workspace, tenant
    try:
        return service.get_snapshot(
            tenant_id=require_tenant().tenant_id, snapshot_id=snapshot_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/ready", operation_id="evaluateBusinessContextReady")
async def evaluate_ready(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        return service.evaluate_ready(
            tenant_id=require_tenant().tenant_id, workspace_id=workspace.workspace_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/brief", operation_id="getBusinessIntelligenceBrief")
async def get_brief(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        return service.get_brief(
            tenant_id=require_tenant().tenant_id, workspace_id=workspace.workspace_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/brief", operation_id="regenerateBusinessIntelligenceBrief")
async def regenerate_brief(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        return service.regenerate_brief(
            tenant_id=require_tenant().tenant_id, workspace_id=workspace.workspace_id
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.get("/proposals", operation_id="listBusinessProfileProposals")
async def list_proposals(
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        rows = service.list_proposals(
            tenant_id=require_tenant().tenant_id, workspace_id=workspace.workspace_id
        )
    except KeyError as exc:
        raise resource_not_found() from exc
    return {"items": [item.model_dump(mode="json") for item in rows]}


@router.post("/proposals", operation_id="createBusinessProfileProposal")
async def create_proposal(
    body: ProposalCreateRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    ctx = require_tenant()
    try:
        return service.create_proposal(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.workspace_id,
            actor_id=ctx.user_id or "unknown",
            previous_fact=body.previous_fact,
            observed_evidence=body.observed_evidence,
            proposed_fact=body.proposed_fact,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post("/proposals/{proposal_id}/decide", operation_id="decideBusinessProfileProposal")
async def decide_proposal(
    proposal_id: str,
    body: ProposalDecideRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    ctx = require_tenant()
    try:
        return service.decide_proposal(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.workspace_id,
            proposal_id=proposal_id,
            actor_id=ctx.user_id or "unknown",
            accept=body.accept,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc
    except ValueError as exc:
        raise validation_error([]) from exc


@router.post("/clarifications", operation_id="createBusinessClarification")
async def create_clarification(
    body: ClarificationCreateRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    try:
        return service.create_clarification(
            tenant_id=require_tenant().tenant_id,
            workspace_id=workspace.workspace_id,
            coverage_gap_id=body.coverage_gap_id,
            fact_id=body.fact_id,
            question=body.question,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise resource_not_found() from exc


@router.post(
    "/clarifications/{clarification_id}/answer", operation_id="answerBusinessClarification"
)
async def answer_clarification(
    clarification_id: str,
    body: ClarificationAnswerRequest,
    workspace: Annotated[Workspace, Depends(authorized_workspace)],
    tenant: Annotated[TenantContext, Depends(authenticated_tenant)],
    service: Annotated[BusinessIqService, Depends(get_business_iq)],
) -> dict[str, Any]:
    del tenant
    ctx = require_tenant()
    try:
        return service.answer_clarification(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.workspace_id,
            clarification_id=clarification_id,
            actor_id=ctx.user_id or "unknown",
            answer=ClarificationAnswer(body.answer),
            observed_evidence=body.observed_evidence,
        ).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        if isinstance(exc, KeyError):
            raise resource_not_found() from exc
        raise validation_error([]) from exc

"""Exposure-risk portfolio routes. Evidence only; no raw provider rows."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Feature, Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.investment_planning.enums import ExposureGuardrailRole
from app.investment_planning.errors import PlanningError
from app.investment_planning.exposure_guardrails import new_guardrail
from app.investment_planning.exposure_observations import ProductionExposureObservationAdapter
from app.investment_planning.exposure_service import ExposureRiskService
from app.service.dependencies import get_control_plane
from app.service.entitlements import require_feature
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    CreateExposureScenarioRequest,
    ExposureCoverageItemResponse,
    ExposureCoverageResponse,
    ExposureGuardrailResponse,
    ExposureRiskProfileResponse,
    ExposureScenarioResponse,
    QualifyExposureGuardrailRequest,
)
from app.service.routers.investment_planning import (
    authorized_planning_scope,
    private_no_store,
)

canonical_exposure_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-portfolio/exposure-risk",
    tags=["investment-portfolio"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_exposure_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-portfolio/exposure-risk",
    tags=["investment-portfolio"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def get_exposure_risk_service(request: Request) -> ExposureRiskService:
    service = getattr(request.app.state, "exposure_risk", None)
    if service is None:
        raise RuntimeError("Exposure risk service is not configured.")
    return service


async def authorized_exposure_scope(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> Workspace:
    require_feature(repo, Feature.PORTFOLIO_VIEW)
    return workspace


def _known_markets(request: Request, project_id: str) -> frozenset[str]:
    planning = getattr(request.app.state, "investment_planning", None)
    if planning is None:
        return frozenset()
    tenant_id = require_tenant().tenant_id
    return planning._markets.known_market_ids(tenant_id=tenant_id, project_id=project_id)


def _coverage_response(coverage, *, source_ready: bool) -> ExposureCoverageResponse:
    return ExposureCoverageResponse(
        project_id=coverage.project_id,
        period=coverage.period,
        overall_status=coverage.overall_status.value,
        items=tuple(
            ExposureCoverageItemResponse(
                dimension=item.dimension.value,
                status=item.status.value,
                observed_count=item.observed_count,
                expected_count=item.expected_count,
            )
            for item in coverage.items
        ),
        fingerprint=coverage.fingerprint,
        source_ready=source_ready,
    )


def _profile_response(profile, coverage, *, source_ready: bool) -> ExposureRiskProfileResponse:
    return ExposureRiskProfileResponse(
        profile_id=profile.profile_id,
        project_id=profile.project_id,
        period=profile.period,
        market_id=profile.market_id,
        channel_id=profile.channel_id,
        risk_flags=tuple(item.value for item in profile.risk_flags),
        limitations=profile.limitations,
        role_eligibility=tuple(item.value for item in profile.role_eligibility),
        coverage=_coverage_response(coverage, source_ready=source_ready),
        fingerprint=profile.fingerprint,
        source_ready=source_ready,
    )


def _assemble(
    request: Request,
    workspace: Workspace,
    service: ExposureRiskService,
    *,
    period: str,
    market_id: str | None = None,
    channel_id: str | None = None,
):
    tenant = require_tenant()
    source_ready = not isinstance(service._observations, ProductionExposureObservationAdapter)
    profile, _evidence, coverage = service.assemble_profile(
        tenant_id=tenant.tenant_id,
        project_id=workspace.workspace_id,
        period=period,
        known_market_ids=_known_markets(request, workspace.workspace_id),
        known_channel_ids=frozenset(),
        market_id=market_id,
        channel_id=channel_id,
    )
    return profile, coverage, source_ready


async def get_exposure_risk(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
) -> ExposureRiskProfileResponse:
    try:
        profile, coverage, source_ready = _assemble(
            request, workspace, service, period="FY2027Q1"
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _profile_response(profile, coverage, source_ready=source_ready)


async def get_exposure_coverage(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
) -> ExposureCoverageResponse:
    try:
        _profile, coverage, source_ready = _assemble(
            request, workspace, service, period="FY2027Q1"
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _coverage_response(coverage, source_ready=source_ready)


async def get_exposure_channel(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
    channel_id: str,
) -> ExposureRiskProfileResponse:
    try:
        profile, coverage, source_ready = _assemble(
            request, workspace, service, period="FY2027Q1", channel_id=channel_id
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _profile_response(profile, coverage, source_ready=source_ready)


async def get_exposure_market(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
    market_id: str,
) -> ExposureRiskProfileResponse:
    try:
        profile, coverage, source_ready = _assemble(
            request, workspace, service, period="FY2027Q1", market_id=market_id
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _profile_response(profile, coverage, source_ready=source_ready)


async def list_exposure_guardrails(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
) -> tuple[ExposureGuardrailResponse, ...]:
    del request, service
    return ()


async def qualify_exposure_guardrail_http(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
    guardrail_id: str,
    body: QualifyExposureGuardrailRequest,
) -> ExposureGuardrailResponse:
    try:
        role = ExposureGuardrailRole(body.role)
        guardrail = new_guardrail(
            project_id=workspace.workspace_id,
            metric_id=body.metric_id,
            role=role,
            market_id=body.market_id,
            channel_id=body.channel_id,
        )
        del guardrail_id
        receipt = service.qualify(
            guardrail,
            tenant_id=require_tenant().tenant_id,
            project_id=workspace.workspace_id,
            period=body.period,
            known_market_ids=_known_markets(request, workspace.workspace_id),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return ExposureGuardrailResponse(
        guardrail_id=guardrail.guardrail_id,
        metric_id=guardrail.metric_id,
        role=guardrail.role.value,
        assigned_role=receipt.assigned_role.value,
        issues=receipt.issues,
        fingerprint=receipt.fingerprint,
    )


async def create_exposure_scenario(
    workspace: Annotated[Workspace, Depends(authorized_exposure_scope)],
    service: Annotated[ExposureRiskService, Depends(get_exposure_risk_service)],
    body: CreateExposureScenarioRequest,
) -> ExposureScenarioResponse:
    try:
        scenario = service.create_scenario(
            project_id=workspace.workspace_id,
            period=body.period,
            scope=body.scope,
            source_rationale=body.source_rationale,
            assumptions=((body.metric_id, body.delta_kind, body.delta_ref, body.rationale),),
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return ExposureScenarioResponse(
        scenario_id=scenario.scenario_id,
        project_id=scenario.project_id,
        period=scenario.period,
        scope=scenario.scope,
        source_rationale=scenario.source_rationale,
        fingerprint=scenario.fingerprint,
    )


for router, suffix in (
    (canonical_exposure_router, ""),
    (workspace_alias_exposure_router, "WorkspaceAlias"),
):
    hidden = bool(suffix)
    router.add_api_route(
        "",
        get_exposure_risk,
        methods=["GET"],
        operation_id=f"getExposureRisk{suffix}",
        response_model=ExposureRiskProfileResponse,
        include_in_schema=not hidden,
    )
    router.add_api_route(
        "/coverage",
        get_exposure_coverage,
        methods=["GET"],
        operation_id=f"getExposureCoverage{suffix}",
        response_model=ExposureCoverageResponse,
        include_in_schema=not hidden,
    )
    router.add_api_route(
        "/channels/{channel_id}",
        get_exposure_channel,
        methods=["GET"],
        operation_id=f"getExposureRiskChannel{suffix}",
        response_model=ExposureRiskProfileResponse,
        include_in_schema=not hidden,
    )
    router.add_api_route(
        "/markets/{market_id}",
        get_exposure_market,
        methods=["GET"],
        operation_id=f"getExposureRiskMarket{suffix}",
        response_model=ExposureRiskProfileResponse,
        include_in_schema=not hidden,
    )
    router.add_api_route(
        "/guardrails",
        list_exposure_guardrails,
        methods=["GET"],
        operation_id=f"listExposureGuardrails{suffix}",
        include_in_schema=not hidden,
    )
    router.add_api_route(
        "/guardrails/{guardrail_id}/qualify",
        qualify_exposure_guardrail_http,
        methods=["POST"],
        operation_id=f"qualifyExposureGuardrail{suffix}",
        response_model=ExposureGuardrailResponse,
        include_in_schema=not hidden,
    )
    router.add_api_route(
        "/scenarios",
        create_exposure_scenario,
        methods=["POST"],
        operation_id=f"createExposureScenario{suffix}",
        response_model=ExposureScenarioResponse,
        include_in_schema=not hidden,
    )

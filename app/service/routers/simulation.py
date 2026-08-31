"""P6-09A simulation routes. Server computes; client cannot submit draws."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.control_plane.models import Feature, Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.investment_optimization.enums import (
    CorrelationAuthority,
    DistributionAuthority,
    DistributionFamily,
    SimulationSemanticType,
)
from app.investment_optimization.errors import OptimizationError
from app.investment_optimization.simulation.distributions import pin_variable
from app.investment_optimization.simulation.service import SimulationService
from app.service.dependencies import get_control_plane
from app.service.entitlements import require_feature
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    CorrelationSpecResponse,
    CreateCorrelationSpecRequest,
    CreateDistributionSetRequest,
    CreateSimulationPolicyRequest,
    CreateSimulationRunRequest,
    CreateSimulationRunSpecRequest,
    DistributionSetResponse,
    OutcomeDistributionResponse,
    SimulationHandoffResponse,
    SimulationPolicyResponse,
    SimulationReceiptResponse,
    SimulationRunResponse,
    SimulationRunSpecResponse,
)
from app.service.routers.investment_planning import (
    authorized_planning_scope,
    private_no_store,
)

canonical_simulation_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-portfolio/simulations",
    tags=["investment-portfolio"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_simulation_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-portfolio/simulations",
    tags=["investment-portfolio"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def get_simulation_service(request: Request) -> SimulationService:
    service = getattr(request.app.state, "simulation", None)
    if service is None:
        raise RuntimeError("Simulation service is not configured.")
    return service


async def authorized_simulation_scope(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    repo: Annotated[ControlPlaneRepository, Depends(get_control_plane)],
) -> Workspace:
    require_feature(repo, Feature.PORTFOLIO_VIEW)
    return workspace


def _reject_client_authority(body: object) -> None:
    dumped = body.model_dump() if hasattr(body, "model_dump") else {}
    forbidden = {
        "random_draws",
        "simulation_outcomes",
        "quantiles",
        "correlation_results",
        "probability_of_improvement",
        "tail_losses",
        "simulation_fingerprint",
        "cvar",
    }
    if any(key in dumped for key in forbidden):
        raise OptimizationError("Client cannot supply authoritative simulation results.")


async def create_distribution_set(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    body: CreateDistributionSetRequest,
) -> DistributionSetResponse:
    _reject_client_authority(body)
    service = get_simulation_service(request)
    try:
        variables = tuple(
            pin_variable(
                semantic_type=SimulationSemanticType(item.semantic_type),
                family=DistributionFamily(item.family),
                parameters={
                    key: tuple(value) if isinstance(value, list) else value
                    for key, value in item.parameters.items()
                },
                source_authority=DistributionAuthority(item.source_authority),
                source_refs=item.source_refs,
                unit=item.unit,
                scope=item.scope,
                time_scope=item.time_scope,
                channel_id=item.channel_id,
                approval_state=item.approval_state,
            )
            for item in body.variables
        )
        created = service.create_distribution_set(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            effective_period=body.effective_period,
            as_of_time=datetime.fromisoformat(body.as_of_time),
            variables=variables,
            approval_state=body.approval_state,
            source_refs=body.source_refs,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return DistributionSetResponse(
        scenario_distribution_set_id=created.scenario_distribution_set_id,
        distribution_set_fingerprint=created.distribution_set_fingerprint,
        approval_state=created.approval_state,
    )


async def get_distribution_set(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    set_id: str,
) -> DistributionSetResponse:
    try:
        item = get_simulation_service(request).get_distribution_set(
            set_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return DistributionSetResponse(
        scenario_distribution_set_id=item.scenario_distribution_set_id,
        distribution_set_fingerprint=item.distribution_set_fingerprint,
        approval_state=item.approval_state,
    )


async def create_correlation(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    body: CreateCorrelationSpecRequest,
) -> CorrelationSpecResponse:
    _reject_client_authority(body)
    try:
        spec = get_simulation_service(request).create_correlation_spec(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            authority=CorrelationAuthority(body.authority),
            variable_ids=body.variable_ids,
            matrix=body.matrix,
            source_refs=body.source_refs,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return CorrelationSpecResponse(
        correlation_spec_id=spec.correlation_spec_id,
        authority=spec.authority.value,
        fingerprint=spec.fingerprint,
    )


async def get_correlation(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    spec_id: str,
) -> CorrelationSpecResponse:
    try:
        spec = get_simulation_service(request).get_correlation(
            spec_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return CorrelationSpecResponse(
        correlation_spec_id=spec.correlation_spec_id,
        authority=spec.authority.value,
        fingerprint=spec.fingerprint,
    )


async def create_policy(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    body: CreateSimulationPolicyRequest,
) -> SimulationPolicyResponse:
    _reject_client_authority(body)
    try:
        policy = get_simulation_service(request).create_policy(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            number_of_draws=body.number_of_draws,
            random_seed=body.random_seed,
            batch_size=body.batch_size,
            distribution_set_ref=body.distribution_set_ref,
            correlation_spec_ref=body.correlation_spec_ref,
            candidate_set_ref=body.candidate_set_ref,
            variable_count=body.variable_count,
            as_of_time=datetime.fromisoformat(body.as_of_time),
            tail_probability=body.tail_probability,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationPolicyResponse(
        policy_id=policy.policy_id,
        fingerprint=policy.fingerprint,
        number_of_draws=policy.number_of_draws,
    )


async def get_policy(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    policy_id: str,
) -> SimulationPolicyResponse:
    try:
        policy = get_simulation_service(request).get_policy(
            policy_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationPolicyResponse(
        policy_id=policy.policy_id,
        fingerprint=policy.fingerprint,
        number_of_draws=policy.number_of_draws,
    )


async def create_run_spec(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    body: CreateSimulationRunSpecRequest,
) -> SimulationRunSpecResponse:
    _reject_client_authority(body)
    service = get_simulation_service(request)
    scope = {"tenant_id": workspace.tenant_id, "project_id": workspace.workspace_id}
    try:
        policy = service.get_policy(body.policy_id, **scope)
        distribution = service.get_distribution_set(policy.distribution_set_ref, **scope)
        correlation = service.get_correlation(policy.correlation_spec_ref, **scope)
        spec = service.create_run_spec(
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
            baseline_ref=body.baseline_ref,
            policy=policy,
            distribution_set=distribution,
            correlation=correlation,
            model_version_ref=body.model_version_ref,
            posterior_artifact_ref=body.posterior_artifact_ref,
            future_assumption_set_ref=body.future_assumption_set_ref,
            exposure_risk_handoff_ref=body.exposure_risk_handoff_ref,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationRunSpecResponse(
        simulation_run_spec_id=spec.simulation_run_spec_id,
        input_fingerprint=spec.input_fingerprint,
        as_of_time=spec.as_of_time.isoformat(),
    )


async def get_run_spec(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    spec_id: str,
) -> SimulationRunSpecResponse:
    try:
        spec = get_simulation_service(request).get_run_spec(
            spec_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationRunSpecResponse(
        simulation_run_spec_id=spec.simulation_run_spec_id,
        input_fingerprint=spec.input_fingerprint,
        as_of_time=spec.as_of_time.isoformat(),
    )


async def create_run(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    body: CreateSimulationRunRequest,
) -> SimulationRunResponse:
    _reject_client_authority(body)
    service = get_simulation_service(request)
    scope = {"tenant_id": workspace.tenant_id, "project_id": workspace.workspace_id}
    try:
        spec = service.get_run_spec(body.run_spec_id, **scope)
        policy = service.get_policy(spec.simulation_policy_ref, **scope)
        distribution = service.get_distribution_set(spec.scenario_distribution_set_ref, **scope)
        correlation = service.get_correlation(spec.scenario_correlation_spec_ref, **scope)
        candidates = tuple(service.get_candidate(item, **scope) for item in spec.candidate_set_ref)
        if any(item is None for item in candidates):
            raise OptimizationError("Simulation candidate was not found.")
        run = service.create_run(
            spec=spec,
            policy=policy,
            distribution_set=distribution,
            correlation=correlation,
            candidates=candidates,  # type: ignore[arg-type]
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationRunResponse(
        simulation_run_id=run.simulation_run_id,
        status=run.status.value,
        input_fingerprint=run.input_fingerprint,
        failure_code=run.failure_code,
    )


async def get_run(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    run_id: str,
) -> SimulationRunResponse:
    try:
        run = get_simulation_service(request).get_run(
            run_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationRunResponse(
        simulation_run_id=run.simulation_run_id,
        status=run.status.value,
        input_fingerprint=run.input_fingerprint,
        failure_code=run.failure_code,
    )


async def execute_run(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    run_id: str,
) -> SimulationRunResponse:
    try:
        run = get_simulation_service(request).execute(
            simulation_run_id=run_id,
            tenant_id=workspace.tenant_id,
            project_id=workspace.workspace_id,
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationRunResponse(
        simulation_run_id=run.simulation_run_id,
        status=run.status.value,
        input_fingerprint=run.input_fingerprint,
        failure_code=run.failure_code,
    )


async def get_receipt(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    run_id: str,
) -> SimulationReceiptResponse:
    try:
        receipt = get_simulation_service(request).get_receipt(
            run_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationReceiptResponse(
        receipt_id=receipt.receipt_id,
        simulation_run_id=receipt.simulation_run_id,
        status=receipt.status.value,
        draw_count=receipt.draw_count,
        simulation_fingerprint=receipt.simulation_fingerprint,
    )


async def get_distributions(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    run_id: str,
) -> tuple[OutcomeDistributionResponse, ...]:
    try:
        rows = get_simulation_service(request).get_distributions(
            run_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return tuple(
        OutcomeDistributionResponse(
            portfolio_outcome_distribution_id=item.portfolio_outcome_distribution_id,
            candidate_portfolio_id=item.candidate_portfolio_id,
            mean=item.mean,
            median=item.median,
            distribution_artifact_ref=item.distribution_artifact_ref,
        )
        for item in rows
    )


async def get_handoff(
    request: Request,
    workspace: Annotated[Workspace, Depends(authorized_simulation_scope)],
    run_id: str,
) -> SimulationHandoffResponse:
    try:
        handoff = get_simulation_service(request).get_handoff(
            run_id, tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
        )
    except OptimizationError as exc:
        raise planning_error(exc) from exc
    return SimulationHandoffResponse(
        simulation_evidence_handoff_id=handoff.simulation_evidence_handoff_id,
        simulation_run_id=handoff.simulation_run_id,
        as_of_time=handoff.as_of_time.isoformat(),
        input_fingerprint=handoff.input_fingerprint,
        simulation_fingerprint=handoff.simulation_fingerprint,
        limitations=handoff.limitations,
    )


for _router in (canonical_simulation_router, workspace_alias_simulation_router):
    suffix = "" if _router is canonical_simulation_router else "Workspace"
    _router.add_api_route(
        "/scenario-distribution-sets",
        create_distribution_set,
        methods=["POST"],
        response_model=DistributionSetResponse,
        operation_id=f"createScenarioDistributionSet{suffix}",
    )
    _router.add_api_route(
        "/scenario-distribution-sets/{set_id}",
        get_distribution_set,
        methods=["GET"],
        response_model=DistributionSetResponse,
        operation_id=f"getScenarioDistributionSet{suffix}",
    )
    _router.add_api_route(
        "/correlation-specs",
        create_correlation,
        methods=["POST"],
        response_model=CorrelationSpecResponse,
        operation_id=f"createScenarioCorrelationSpec{suffix}",
    )
    _router.add_api_route(
        "/correlation-specs/{spec_id}",
        get_correlation,
        methods=["GET"],
        response_model=CorrelationSpecResponse,
        operation_id=f"getScenarioCorrelationSpec{suffix}",
    )
    _router.add_api_route(
        "/policies",
        create_policy,
        methods=["POST"],
        response_model=SimulationPolicyResponse,
        operation_id=f"createMonteCarloSimulationPolicy{suffix}",
    )
    _router.add_api_route(
        "/policies/{policy_id}",
        get_policy,
        methods=["GET"],
        response_model=SimulationPolicyResponse,
        operation_id=f"getMonteCarloSimulationPolicy{suffix}",
    )
    _router.add_api_route(
        "/run-specs",
        create_run_spec,
        methods=["POST"],
        response_model=SimulationRunSpecResponse,
        operation_id=f"createSimulationRunSpec{suffix}",
    )
    _router.add_api_route(
        "/run-specs/{spec_id}",
        get_run_spec,
        methods=["GET"],
        response_model=SimulationRunSpecResponse,
        operation_id=f"getSimulationRunSpec{suffix}",
    )
    _router.add_api_route(
        "/runs",
        create_run,
        methods=["POST"],
        response_model=SimulationRunResponse,
        operation_id=f"createSimulationRun{suffix}",
    )
    _router.add_api_route(
        "/runs/{run_id}",
        get_run,
        methods=["GET"],
        response_model=SimulationRunResponse,
        operation_id=f"getSimulationRun{suffix}",
    )
    _router.add_api_route(
        "/runs/{run_id}/execute",
        execute_run,
        methods=["POST"],
        response_model=SimulationRunResponse,
        status_code=202,
        operation_id=f"executeSimulationRun{suffix}",
    )
    _router.add_api_route(
        "/runs/{run_id}/receipt",
        get_receipt,
        methods=["GET"],
        response_model=SimulationReceiptResponse,
        operation_id=f"getMonteCarloSimulationReceipt{suffix}",
    )
    _router.add_api_route(
        "/runs/{run_id}/outcome-distributions",
        get_distributions,
        methods=["GET"],
        response_model=tuple[OutcomeDistributionResponse, ...],
        operation_id=f"listPortfolioOutcomeDistributions{suffix}",
    )
    _router.add_api_route(
        "/runs/{run_id}/evidence-handoff",
        get_handoff,
        methods=["GET"],
        response_model=SimulationHandoffResponse,
        operation_id=f"getSimulationEvidenceHandoff{suffix}",
    )

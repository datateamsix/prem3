"""Project-scoped Investment Portfolio API. Amounts are transient and private."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.control_plane.models import Workspace
from app.core.tenancy import require_tenant
from app.investment_planning.contracts import (
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioSnapshotRef,
    PortfolioView,
)
from app.investment_planning.enums import AmountKind, PortfolioCoverageState
from app.investment_planning.errors import PlanningError
from app.investment_planning.portfolio import (
    remaining_amount,
    rollup_by_dimension,
    summarize_allocations,
    variance_amount,
    variance_percent,
)
from app.investment_planning.service import InvestmentPlanService
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    InvestmentPortfolioResponse,
    MoneyAmountResponse,
    PortfolioAllocationResponse,
    PortfolioDimensionTotalResponse,
    PortfolioEvidenceCoverageItemResponse,
    PortfolioEvidenceCoverageResponse,
    PortfolioFreshnessResponse,
    PortfolioObservationResponse,
    PortfolioVarianceResponse,
    QuarterlyPortfolioResponse,
)
from app.service.routers.investment_planning import (
    authorized_planning_scope,
    get_investment_planning,
    private_no_store,
)

canonical_portfolio_router = APIRouter(
    prefix="/v1/projects/{project_id}/investment-portfolio",
    tags=["investment-portfolio"],
    dependencies=[Depends(private_no_store)],
)
workspace_alias_portfolio_router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/investment-portfolio",
    tags=["investment-portfolio"],
    include_in_schema=False,
    dependencies=[Depends(private_no_store)],
)


def _amount_response(amount: MoneyAmount) -> MoneyAmountResponse:
    return MoneyAmountResponse(
        kind=amount.kind.value,
        currency=amount.currency,
        value=None if amount.value is None else format(amount.value, "f"),
        missing=amount.missing,
    )


def _allocation_response(row: PortfolioAllocationView) -> PortfolioAllocationResponse:
    return PortfolioAllocationResponse(
        fiscal_year=row.fiscal_year,
        quarter=row.quarter,
        market_id=row.market_id,
        channel_id=row.channel_id,
        channel_registry_version=row.channel_registry_version,
        amounts=tuple(_amount_response(amount) for amount in row.amounts),
    )


def _portfolio_response(
    *,
    project_id: str,
    coverage_state: str,
    snapshot: PortfolioSnapshotRef | None,
    view: PortfolioView | None,
) -> InvestmentPortfolioResponse:
    snapshot_id = None if snapshot is None else snapshot.snapshot_id
    actuals_source_id = None if snapshot is None else snapshot.actuals_source_id
    if view is None:
        return InvestmentPortfolioResponse(
            coverage_state=coverage_state,
            snapshot_id=snapshot_id,
            project_id=project_id,
            workspace_id=project_id,
            actuals_source_id=actuals_source_id,
        )
    amount_kind = view.summary.totals[0].kind if view.summary.totals else AmountKind.APPROVED
    remaining = remaining_amount(view.allocations, currency=view.currency)
    if coverage_state == PortfolioCoverageState.ACTUALS_ONLY.value:
        remaining = remaining.model_copy(update={"missing": True, "value": None})
    variance = variance_amount(view.allocations, currency=view.currency)
    approved_total = next(
        (
            item
            for item in view.summary.totals
            if item.kind is AmountKind.APPROVED and not item.missing
        ),
        None,
    )
    actual_total = next(
        (
            item
            for item in view.summary.totals
            if item.kind is AmountKind.ACTUAL and not item.missing
        ),
        None,
    )
    percent = variance_percent(
        None if approved_total is None else approved_total.value,
        None if actual_total is None else actual_total.value,
    )
    if coverage_state != PortfolioCoverageState.PLAN_AND_ACTUALS.value:
        variance = variance.model_copy(update={"missing": True, "value": None})
        percent = None
    channel_rows = rollup_by_dimension(
        view.allocations, currency=view.currency, kind=amount_kind, by="channel"
    )
    market_rows = rollup_by_dimension(
        view.allocations, currency=view.currency, kind=amount_kind, by="market"
    )
    return InvestmentPortfolioResponse(
        coverage_state=coverage_state,
        snapshot_id=view.snapshot_id,
        project_id=view.project_id,
        workspace_id=view.project_id,
        fiscal_year=view.fiscal_year,
        currency=view.currency,
        baseline_kind=view.baseline_kind.value,
        actuals_source_id=actuals_source_id,
        summary=tuple(_amount_response(amount) for amount in view.summary.totals),
        remaining=_amount_response(remaining),
        variance=PortfolioVarianceResponse(
            currency=view.currency,
            value=(
                None
                if variance.missing or variance.value is None
                else format(variance.value, "f")
            ),
            missing=variance.missing,
            percent=None if percent is None else format(percent, "f"),
        ),
        allocations=tuple(_allocation_response(row) for row in view.allocations),
        channel_allocation=tuple(
            PortfolioDimensionTotalResponse(
                market_id=row.market_id,
                channel_id=row.channel_id,
                amount=_amount_response(row.amount),
            )
            for row in channel_rows
        ),
        market_allocation=tuple(
            PortfolioDimensionTotalResponse(
                market_id=row.market_id,
                channel_id=row.channel_id,
                amount=_amount_response(row.amount),
            )
            for row in market_rows
        ),
        quarterly=tuple(
            QuarterlyPortfolioResponse(
                quarter=bucket.quarter,
                summary=tuple(
                    _amount_response(amount)
                    for amount in summarize_allocations(
                        bucket.allocations, currency=view.currency, kind=amount_kind
                    ).totals
                ),
            )
            for bucket in view.quarterly
        ),
        coverage=PortfolioEvidenceCoverageResponse(
            scope=view.coverage.scope.value,
            status=view.coverage.status.value,
            labels=tuple(label.value for label in view.coverage.labels),
            items=tuple(
                PortfolioEvidenceCoverageItemResponse(
                    category=item.category.value,
                    scope=item.scope.value,
                    status=item.status.value,
                    evidence_ref=item.evidence_ref,
                    market_id=item.market_id,
                    channel_id=item.channel_id,
                    fiscal_year=item.fiscal_year,
                    quarter=item.quarter,
                    causal=item.causal,
                )
                for item in view.coverage.items
            ),
            accepted_mmm=view.coverage.accepted_mmm,
            mta_available=view.coverage.mta_available,
            exposure_integrity_available=view.coverage.exposure_integrity_available,
            stale=view.coverage.stale,
        ),
        observations=tuple(
            PortfolioObservationResponse(
                observation_id=item.observation_id,
                observation_type=item.observation_type.value,
                severity=item.severity.value,
                market_id=item.subject_market_id,
                channel_id=item.subject_channel_id,
                fiscal_year=item.fiscal_year,
                quarter=item.quarter,
                message_key=item.message_key,
                snapshot_fingerprint=item.snapshot_fingerprint,
            )
            for item in view.observations
        ),
        freshness=PortfolioFreshnessResponse(
            plan_source_as_of=view.freshness.plan_source_as_of,
            actuals_as_of=view.freshness.actuals_as_of,
            measurement_as_of=view.freshness.measurement_as_of,
        ),
    )


async def get_portfolio(
    workspace: Annotated[Workspace, Depends(authorized_planning_scope)],
    service: Annotated[InvestmentPlanService, Depends(get_investment_planning)],
    fiscal_year: Annotated[int | None, Query()] = None,
) -> InvestmentPortfolioResponse:
    try:
        state, snapshot, view = service.assemble_portfolio(
            project_id=workspace.workspace_id,
            fiscal_year=fiscal_year,
            actor_id=require_tenant().user_id or "unknown",
        )
    except PlanningError as exc:
        raise planning_error(exc) from exc
    return _portfolio_response(
        project_id=workspace.workspace_id,
        coverage_state=state.value,
        snapshot=snapshot,
        view=view,
    )


canonical_portfolio_router.add_api_route(
    "",
    get_portfolio,
    methods=["GET"],
    operation_id="getInvestmentPortfolio",
    response_model=InvestmentPortfolioResponse,
)
workspace_alias_portfolio_router.add_api_route(
    "",
    get_portfolio,
    methods=["GET"],
    operation_id="getInvestmentPortfolioWorkspaceAlias",
    response_model=InvestmentPortfolioResponse,
    include_in_schema=False,
)

"""Project-scoped Investment Portfolio API. Amounts are transient and private."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.control_plane.models import Workspace
from app.core.tenancy import require_tenant
from app.investment_planning.contracts import MoneyAmount, PortfolioAllocationView, PortfolioView
from app.investment_planning.enums import AmountKind
from app.investment_planning.errors import PlanningError
from app.investment_planning.portfolio import (
    remaining_amount,
    rollup_by_dimension,
    summarize_allocations,
)
from app.investment_planning.service import InvestmentPlanService
from app.service.errors import planning_error
from app.service.investment_planning_models import (
    InvestmentPortfolioResponse,
    MoneyAmountResponse,
    PortfolioAllocationResponse,
    PortfolioDimensionTotalResponse,
    PortfolioFreshnessResponse,
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
    snapshot_id: str | None,
    view: PortfolioView | None,
) -> InvestmentPortfolioResponse:
    if view is None:
        return InvestmentPortfolioResponse(
            coverage_state=coverage_state,
            snapshot_id=snapshot_id,
            project_id=project_id,
            workspace_id=project_id,
        )
    amount_kind = view.summary.totals[0].kind if view.summary.totals else AmountKind.APPROVED
    remaining = remaining_amount(view.allocations, currency=view.currency)
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
        summary=tuple(_amount_response(amount) for amount in view.summary.totals),
        remaining=_amount_response(remaining),
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
        snapshot_id=None if snapshot is None else snapshot.snapshot_id,
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

"""Resolve the fixed budget from an approved Drive plan transient PortfolioView."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.contracts import (
    OptimizationInputContract,
    OptimizerBudgetLine,
    OptimizerBudgetVector,
    PortfolioModelMapping,
)
from app.investment_optimization.enums import (
    ModelVariableOptimizationEligibility,
    UnmappedVariableTreatment,
)
from app.investment_optimization.errors import (
    ActualsNotFixedBudgetError,
    ApprovedPlanRequiredError,
    ClientBudgetArrayRejectedError,
    UnapprovedPlanError,
)
from app.investment_planning.actuals import round_money
from app.investment_planning.contracts import PortfolioView
from app.investment_planning.enums import AmountKind, PortfolioBaselineKind
from app.investment_planning.errors import PlanningAuthorityError


def reject_client_budget_authority(
    *,
    tenant_id: str | None,
    budget_array: object | None,
    model_path: str | None,
    drive_path: str | None,
    variable_map: object | None,
) -> None:
    if tenant_id is not None:
        raise PlanningAuthorityError("Client cannot supply tenant_id.")
    if model_path is not None:
        raise PlanningAuthorityError("Client cannot supply model artifact location.")
    if drive_path is not None:
        raise PlanningAuthorityError("Client cannot supply Drive path.")
    if budget_array is not None:
        raise ClientBudgetArrayRejectedError("Client cannot supply a budget array.")
    if variable_map is not None:
        raise PlanningAuthorityError("Client cannot supply a variable map.")


def resolve_optimizer_budget(
    *,
    view: PortfolioView | None,
    mapping: PortfolioModelMapping,
    input_contract: OptimizationInputContract,
    plan_status: str | None = None,
) -> OptimizerBudgetVector:
    if view is None:
        raise ApprovedPlanRequiredError(
            "An approved Drive plan is required for fixed-budget optimization."
        )
    if view.baseline_kind in {
        PortfolioBaselineKind.ACTUAL_YTD,
        PortfolioBaselineKind.GOVERNED_ACTUALS,
    }:
        raise ActualsNotFixedBudgetError("Actuals cannot become the fixed-budget authority.")
    if view.baseline_kind is not PortfolioBaselineKind.APPROVED_PLAN:
        raise UnapprovedPlanError("Fixed-budget optimization requires an APPROVED_PLAN baseline.")
    if plan_status is not None and plan_status != "APPROVED":
        raise UnapprovedPlanError("Fixed-budget optimization requires an approved Investment Plan.")

    approved: dict[tuple[str, str], Decimal] = {}
    for allocation in view.allocations:
        if allocation.fiscal_year != view.fiscal_year:
            continue
        cell_total = Decimal("0")
        for amount in allocation.amounts:
            if amount.kind is AmountKind.APPROVED and amount.value is not None:
                if not amount.missing:
                    cell_total += amount.value
            if amount.kind is AmountKind.ACTUAL:
                continue
        key = (allocation.market_id, allocation.channel_id)
        approved[key] = round_money(approved.get(key, Decimal("0")) + cell_total)

    lines: list[OptimizerBudgetLine] = []
    seen: set[str] = set()
    for entry in mapping.mapping_entries:
        if entry.model_variable_id in seen:
            continue
        seen.add(entry.model_variable_id)
        baseline = approved.get((entry.market_id, entry.channel_id), Decimal("0.00"))
        eligibility = ModelVariableOptimizationEligibility.OPTIMIZABLE
        if entry.model_variable_id in input_contract.fixed_variable_ids:
            eligibility = ModelVariableOptimizationEligibility.FIXED
        elif entry.model_variable_id in input_contract.excluded_variable_ids:
            eligibility = ModelVariableOptimizationEligibility.CONTEXT_ONLY
        lines.append(
            OptimizerBudgetLine(
                model_variable_id=entry.model_variable_id,
                market_id=entry.market_id,
                channel_id=entry.channel_id,
                baseline=round_money(baseline),
                eligibility=eligibility,
            )
        )

    for unmapped in mapping.unmapped_model_variables:
        if unmapped.model_variable_id in seen:
            continue
        seen.add(unmapped.model_variable_id)
        eligibility = ModelVariableOptimizationEligibility.CONTEXT_ONLY
        if unmapped.treatment is UnmappedVariableTreatment.FIXED_BASELINE:
            eligibility = ModelVariableOptimizationEligibility.FIXED
        elif unmapped.treatment is UnmappedVariableTreatment.FIXED_AT_ZERO:
            eligibility = ModelVariableOptimizationEligibility.FIXED
        lines.append(
            OptimizerBudgetLine(
                model_variable_id=unmapped.model_variable_id,
                market_id="",
                channel_id="",
                baseline=Decimal("0.00"),
                eligibility=eligibility,
            )
        )

    fixed = round_money(
        sum(
            (
                line.baseline
                for line in lines
                if line.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
            ),
            Decimal("0"),
        )
    )
    if fixed <= Decimal("0"):
        raise ApprovedPlanRequiredError(
            "Approved-plan optimizable spend must be a positive fixed budget."
        )
    return OptimizerBudgetVector(currency=view.currency, fixed_budget=fixed, lines=tuple(lines))

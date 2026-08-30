"""P6-07 future assumptions pinning and financial-value gate."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.investment_optimization.advanced_readiness import (
    advanced_receipt_is_stale,
    evaluate_advanced_readiness,
)
from app.investment_optimization.assumptions import (
    pin_assumptions,
    require_financial_value,
)
from app.investment_optimization.contracts import (
    FutureScenarioAssumptions,
    UnitValueAssumption,
)
from app.investment_optimization.enums import (
    OptimizationBudgetMode,
    OptimizationObjectiveMode,
)
from app.investment_optimization.errors import (
    FinancialValueAssumptionRequiredError,
    FlightingAssumptionInvalidError,
    FutureCostAssumptionInvalidError,
)
from app.investment_optimization.execution import optimizer_defaults_fingerprint
from app.investment_optimization.objective import validate_objective
from tests.unit.investment_optimization.p6_04_support import PROJECT, TENANT, now
from tests.unit.investment_optimization.p6_05_support import persist_ready
from tests.unit.investment_optimization.p6_07_support import (
    cost_assumption,
    flighting_assumption,
    governed_revenue,
    pinned_assumptions,
)


def test_future_cost_assumption_pinned() -> None:
    pinned = pinned_assumptions(cost_per_media_unit=(cost_assumption(),))
    assert pinned.fingerprint
    assert pinned.cost_per_media_unit_refs == ("cost_search",)
    assert pinned.cost_per_media_unit[0].value == Decimal("12.50")
    assert pinned.cost_per_media_unit[0].source == "business_iq"
    with pytest.raises(FutureCostAssumptionInvalidError):
        pin_assumptions(
            FutureScenarioAssumptions(
                assumption_set_id="oasm_badcostaaaaaaaaaaa",
                cost_per_media_unit=(cost_assumption(value="0.00"),),
            )
        )


def test_flighting_assumption_pinned() -> None:
    pinned = pinned_assumptions(flighting=(flighting_assumption(),))
    assert pinned.flighting_refs == ("flight_search",)
    assert pinned.flighting[0].weight == Decimal("1.00")
    with pytest.raises(FlightingAssumptionInvalidError):
        pin_assumptions(
            FutureScenarioAssumptions(
                assumption_set_id="oasm_badflightaaaaaaaaa",
                flighting=(flighting_assumption(weight="-0.10"),),
            )
        )


def test_revenue_per_kpi_requires_governed_source() -> None:
    ungoverned = UnitValueAssumption(
        ref_id="rev_bare",
        source="",
        scope="national",
        currency="USD",
        time_horizon="2027",
        freshness="",
        value=Decimal("4.00"),
    )
    assumptions = FutureScenarioAssumptions(
        assumption_set_id="oasm_ungovaaaaaaaaaaaaaa",
        revenue_per_kpi=ungoverned,
    )
    with pytest.raises(FinancialValueAssumptionRequiredError):
        require_financial_value(assumptions)


def test_margin_missing_does_not_fabricate_romi() -> None:
    assumptions = pinned_assumptions()
    with pytest.raises(FinancialValueAssumptionRequiredError):
        validate_objective(
            mode=OptimizationObjectiveMode.MAX_INCREMENTAL_CONTRIBUTION_VALUE,
            assumptions=assumptions,
        )
    with pytest.raises(FinancialValueAssumptionRequiredError):
        validate_objective(
            mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
            assumptions=assumptions,
            target_roi=2.0,
        )
    governed = pinned_assumptions(revenue_per_kpi=governed_revenue())
    require_financial_value(governed)
    validate_objective(
        mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        assumptions=governed,
        target_roi=2.0,
    )


def test_assumption_change_stales_readiness() -> None:
    _mapping, _coverage, _input, receipt, *_rest = persist_ready()
    first = pinned_assumptions(cost_per_media_unit=(cost_assumption(),))
    advanced = evaluate_advanced_readiness(
        tenant_id=TENANT,
        project_id=PROJECT,
        base=receipt,
        objective_mode=OptimizationObjectiveMode.MAX_EXPECTED_OUTCOME_FIXED_BUDGET,
        budget_mode=OptimizationBudgetMode.FIXED,
        assumptions=first,
        constraint_set=None,
        optimizer_defaults_fingerprint=optimizer_defaults_fingerprint(),
        created_at=now(),
    )
    changed = pinned_assumptions(
        assumption_set_id=first.assumption_set_id,
        cost_per_media_unit=(cost_assumption(value="18.00"),),
    )
    assert advanced_receipt_is_stale(
        advanced,
        base=receipt,
        assumption_fingerprint=changed.fingerprint,
        constraint_fingerprint=None,
        objective_fingerprint=advanced.objective_fingerprint,
        optimizer_defaults_fingerprint=advanced.optimizer_defaults_fingerprint,
    )

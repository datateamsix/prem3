"""Governed optimization objective modes. Never fabricate ROI/ROMI."""

from __future__ import annotations

from app.investment_optimization.assumptions import has_governed_financial_value
from app.investment_optimization.contracts import FutureScenarioAssumptions
from app.investment_optimization.enums import (
    OptimizationBudgetMode,
    OptimizationObjectiveMode,
    OptimizationRunKind,
)
from app.investment_optimization.errors import (
    FinancialValueAssumptionRequiredError,
    ObjectiveNotSupportedError,
)
from app.investment_planning.fingerprint import metadata_fingerprint

FINANCIAL_VALUE_MODES: frozenset[OptimizationObjectiveMode] = frozenset(
    {
        OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        OptimizationObjectiveMode.TARGET_MROI_FLEXIBLE_BUDGET,
        OptimizationObjectiveMode.MAX_INCREMENTAL_CONTRIBUTION_VALUE,
    }
)


def objective_fingerprint(
    *,
    mode: OptimizationObjectiveMode,
    target_roi: float | None = None,
    target_mroi: float | None = None,
    use_kpi: bool | None = None,
) -> str:
    return metadata_fingerprint(
        {
            "mode": mode.value,
            "target_roi": None if target_roi is None else str(target_roi),
            "target_mroi": None if target_mroi is None else str(target_mroi),
            "use_kpi": use_kpi,
        }
    )


def budget_mode_for(mode: OptimizationObjectiveMode) -> OptimizationBudgetMode:
    if mode is OptimizationObjectiveMode.MAX_EXPECTED_OUTCOME_FIXED_BUDGET:
        return OptimizationBudgetMode.FIXED
    return OptimizationBudgetMode.FLEXIBLE


def run_kind_for(mode: OptimizationObjectiveMode) -> OptimizationRunKind:
    if budget_mode_for(mode) is OptimizationBudgetMode.FIXED:
        return OptimizationRunKind.FIXED_BUDGET
    return OptimizationRunKind.FLEXIBLE_BUDGET


def validate_objective(
    *,
    mode: OptimizationObjectiveMode,
    assumptions: FutureScenarioAssumptions | None,
    target_roi: float | None = None,
    target_mroi: float | None = None,
) -> None:
    if mode is OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET and target_roi is None:
        raise ObjectiveNotSupportedError("TARGET_ROI_FLEXIBLE_BUDGET requires target_roi.")
    if mode is OptimizationObjectiveMode.TARGET_MROI_FLEXIBLE_BUDGET and target_mroi is None:
        raise ObjectiveNotSupportedError("TARGET_MROI_FLEXIBLE_BUDGET requires target_mroi.")
    if mode is OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET and target_mroi is not None:
        raise ObjectiveNotSupportedError(
            "Native Meridian accepts target_roi or target_mroi, not both."
        )
    if mode is OptimizationObjectiveMode.TARGET_MROI_FLEXIBLE_BUDGET and target_roi is not None:
        raise ObjectiveNotSupportedError(
            "Native Meridian accepts target_roi or target_mroi, not both."
        )
    if mode in FINANCIAL_VALUE_MODES and not has_governed_financial_value(assumptions):
        if mode is OptimizationObjectiveMode.MAX_INCREMENTAL_CONTRIBUTION_VALUE:
            raise FinancialValueAssumptionRequiredError(
                "MAX_INCREMENTAL_CONTRIBUTION_VALUE requires governed unit value or margin."
            )
        raise FinancialValueAssumptionRequiredError(
            "Target ROI/mROI requires governed revenue_per_kpi or contribution margin."
        )


def use_kpi_for(
    *,
    mode: OptimizationObjectiveMode,
    assumptions: FutureScenarioAssumptions | None,
) -> bool:
    if mode is OptimizationObjectiveMode.MAX_INCREMENTAL_CONTRIBUTION_VALUE:
        return False
    if mode in FINANCIAL_VALUE_MODES and has_governed_financial_value(assumptions):
        return False
    return True

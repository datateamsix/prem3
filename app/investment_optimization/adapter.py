"""Native Meridian adapter is frozen, not implemented, in P6-00."""

from __future__ import annotations

from app.investment_optimization.contracts import (
    OptimizationExecutionPayload,
    OptimizationExecutionPlan,
)
from app.investment_optimization.enums import OptimizationSolverKind
from app.investment_planning.errors import PlanningError


class MeridianOptimizerNotImplementedError(PlanningError):
    code = "MERIDIAN_OPTIMIZER_NOT_IMPLEMENTED"


class UnimplementedMeridianBudgetOptimizerAdapter:
    """P6-05 proves native Meridian BudgetOptimizer. P6-09 is CVaR."""

    supported_solvers = (
        OptimizationSolverKind.MERIDIAN_NATIVE_FIXED_BUDGET,
        OptimizationSolverKind.MERIDIAN_NATIVE_FLEXIBLE_BUDGET,
    )
    deferred_solvers = (OptimizationSolverKind.PREM3_RISK_AWARE_FRONTIER,)

    def optimize(
        self,
        plan: OptimizationExecutionPlan,
        payload: OptimizationExecutionPayload,
    ) -> OptimizationExecutionPayload:
        del plan, payload
        raise MeridianOptimizerNotImplementedError(
            "Meridian BudgetOptimizer is not invoked in P6-00."
        )

"""P6-00 optimization seams: native Meridian first, no execution."""

from __future__ import annotations

import pytest

from app.investment_optimization.adapter import (
    MeridianOptimizerNotImplementedError,
    UnimplementedMeridianBudgetOptimizerAdapter,
)
from app.investment_optimization.contracts import (
    OptimizationExecutionPayload,
    OptimizationExecutionPlan,
)
from app.investment_optimization.enums import (
    OptimizationReadinessStatus,
    OptimizationSolverKind,
)


def test_native_meridian_is_first_and_cvar_is_deferred() -> None:
    adapter = UnimplementedMeridianBudgetOptimizerAdapter()
    assert OptimizationSolverKind.MERIDIAN_NATIVE_FIXED_BUDGET in adapter.supported_solvers
    assert OptimizationSolverKind.PREM3_RISK_AWARE_FRONTIER in adapter.deferred_solvers
    plan = OptimizationExecutionPlan(
        execution_plan_id="oexec_aaaaaaaaaaaaaaaaaa",
        proposal_id="oprop_aaaaaaaaaaaaaaaaaaa",
        solver_kind=OptimizationSolverKind.MERIDIAN_NATIVE_FIXED_BUDGET,
        readiness=OptimizationReadinessStatus.REQUIRES_ACCEPTED_MMM,
        accepted_mmm_result_ref="mver_aaaaaaaaaaaaaaaaaaaa",
        payload_fingerprint="fp_payload",
        constraint_set_ref="ocst_aaaaaaaaaaaaaaaaaaaa",
        assumption_set_ref="oasm_aaaaaaaaaaaaaaaaaaaa",
    )
    payload = OptimizationExecutionPayload(execution_plan_id=plan.execution_plan_id)
    with pytest.raises(MeridianOptimizerNotImplementedError):
        adapter.optimize(plan, payload)

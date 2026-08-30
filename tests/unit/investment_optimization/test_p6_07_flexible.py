"""P6-07 native flexible budget path. P6-05 fixed path stays unchanged."""

from __future__ import annotations

import inspect
from decimal import Decimal

from app.investment_optimization.adapter import NativeMeridianFixedBudgetAdapter
from app.investment_optimization.enums import (
    ADVANCED_ARTIFACT_SCHEMA_VERSION,
    ARTIFACT_SCHEMA_VERSION,
    PINNED_MERIDIAN_RUNTIME,
    OptimizationBudgetMode,
    OptimizationObjectiveMode,
    OptimizationRunKind,
    OptimizationRunStatus,
)
from app.investment_optimization.validate_result import validate_constraint_result
from tests.unit.investment_optimization.p6_04_support import PROJECT
from tests.unit.investment_optimization.p6_05_support import (
    ScriptedFixedBudgetOptimizer,
    bound,
    run_service,
)
from tests.unit.investment_optimization.p6_07_support import (
    ScriptedFlexibleBudgetOptimizer,
    advanced_service,
    constraint_set,
    governed_revenue,
    line_bound,
    persist_assumption,
    persist_constraint,
    pinned_assumptions,
)


def _create(service, receipt_id: str, **kwargs):
    return bound(
        lambda: service.create_run(
            project_id=PROJECT,
            actor_id="user_music_center",
            readiness_receipt_id=receipt_id,
            **kwargs,
        )
    )


def test_native_flexible_path() -> None:
    optimizer = ScriptedFlexibleBudgetOptimizer(spends={"search_spend": 90.0})
    service, receipt, store, *_ = run_service(optimizer=optimizer)
    adv = advanced_service(store=store, object_store=service._object_store)
    assumptions = persist_assumption(adv, pinned_assumptions(revenue_per_kpi=governed_revenue()))
    run = _create(
        service,
        receipt.receipt_id,
        budget_mode=OptimizationBudgetMode.FLEXIBLE,
        objective_mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        assumption_set_id=assumptions.assumption_set_id,
        target_roi=2.0,
    )
    assert run.status is OptimizationRunStatus.COMPLETE
    assert run.run_kind is OptimizationRunKind.FLEXIBLE_BUDGET
    assert optimizer.specs
    spec = optimizer.specs[0]
    assert spec.fixed_budget is False
    assert spec.budget is None
    assert spec.target_roi == 2.0
    assert spec.target_mroi is None
    payload = bound(
        lambda: service.get_result(
            optimization_run_id=run.optimization_run_id, project_id=PROJECT
        )
    )
    assert payload.schema_version == ADVANCED_ARTIFACT_SCHEMA_VERSION
    assert payload.recommended_total == Decimal("90.00")
    assert payload.recommended_total != payload.fixed_budget


def test_target_roi_and_mroi() -> None:
    optimizer = ScriptedFlexibleBudgetOptimizer(spends={"search_spend": 95.0})
    service, receipt, store, *_ = run_service(optimizer=optimizer)
    adv = advanced_service(store=store, object_store=service._object_store)
    assumptions = persist_assumption(adv, pinned_assumptions(revenue_per_kpi=governed_revenue()))
    roi_run = _create(
        service,
        receipt.receipt_id,
        objective_mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        assumption_set_id=assumptions.assumption_set_id,
        target_roi=1.5,
    )
    assert roi_run.status is OptimizationRunStatus.COMPLETE
    assert optimizer.specs[-1].target_roi == 1.5
    mroi_run = _create(
        service,
        receipt.receipt_id,
        objective_mode=OptimizationObjectiveMode.TARGET_MROI_FLEXIBLE_BUDGET,
        assumption_set_id=assumptions.assumption_set_id,
        target_mroi=1.1,
    )
    assert mroi_run.status is OptimizationRunStatus.COMPLETE
    assert optimizer.specs[-1].target_mroi == 1.1
    assert optimizer.specs[-1].target_roi is None


def test_fixed_budget_path_unchanged() -> None:
    source = inspect.getsource(NativeMeridianFixedBudgetAdapter.optimize_fixed_budget)
    assert "fixed_budget=True" in source
    assert "use_posterior=True" in source
    optimizer = ScriptedFixedBudgetOptimizer()
    service, receipt, *_ = run_service(optimizer=optimizer)
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.COMPLETE
    assert run.run_kind is OptimizationRunKind.FIXED_BUDGET
    assert optimizer.calls
    assert not hasattr(optimizer, "specs") or not getattr(optimizer, "specs", ())
    payload = bound(
        lambda: service.get_result(
            optimization_run_id=run.optimization_run_id, project_id=PROJECT
        )
    )
    assert payload.schema_version == ARTIFACT_SCHEMA_VERSION
    assert payload.recommended_total == payload.fixed_budget


def test_runtime_pinned() -> None:
    optimizer = ScriptedFlexibleBudgetOptimizer()
    service, receipt, store, *_ = run_service(optimizer=optimizer)
    adv = advanced_service(store=store, object_store=service._object_store)
    assumptions = persist_assumption(adv, pinned_assumptions(revenue_per_kpi=governed_revenue()))
    run = _create(
        service,
        receipt.receipt_id,
        objective_mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        assumption_set_id=assumptions.assumption_set_id,
        target_roi=2.0,
    )
    assert run.runtime_version == PINNED_MERIDIAN_RUNTIME == "1.8.0"
    spec = optimizer.specs[0]
    assert spec.gtol == 0.0001
    assert spec.use_posterior is True


def test_constraint_result_validated() -> None:
    optimizer = ScriptedFlexibleBudgetOptimizer(spends={"search_spend": 80.0})
    service, receipt, store, *_ = run_service(optimizer=optimizer)
    adv = advanced_service(store=store, object_store=service._object_store)
    assumptions = persist_assumption(adv, pinned_assumptions(revenue_per_kpi=governed_revenue()))
    constraints = persist_constraint(
        adv,
        constraint_set(
            line_bounds=(line_bound(lower="50.00", upper="120.00"),),
        ),
    )
    run = _create(
        service,
        receipt.receipt_id,
        objective_mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        assumption_set_id=assumptions.assumption_set_id,
        constraint_set_id=constraints.constraint_set_id,
        target_roi=2.0,
    )
    assert run.status is OptimizationRunStatus.COMPLETE
    payload = bound(
        lambda: service.get_result(
            optimization_run_id=run.optimization_run_id, project_id=PROJECT
        )
    )
    assert payload.recommended_total == Decimal("80.00")
    loaded = adv.load_constraints(constraints)
    bindings = validate_constraint_result(constraint_set=loaded, rows=payload.rows)
    assert isinstance(bindings, tuple)

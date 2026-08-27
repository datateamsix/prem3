"""P6-06 scenario artifact tests."""

from __future__ import annotations

import pytest

from app.investment_optimization.enums import (
    OptimizationAmountKind,
    OptimizationRunStatus,
    ScenarioType,
)
from app.investment_optimization.errors import (
    ScenarioRequiresCompletedOptimizationError,
)
from app.investment_optimization.store import assert_optimization_metadata_only
from app.investment_planning.errors import PersistenceBarrierError
from tests.unit.investment_optimization.p6_04_support import PROJECT
from tests.unit.investment_optimization.p6_05_support import bound
from tests.unit.investment_optimization.p6_06_support import (
    complete_run,
    create_scenario,
    governance_stack,
)


def test_scenario_requires_completed_optimization() -> None:
    gov, run_svc, receipt, *_ = governance_stack(execute_inline=False)
    run = bound(
        lambda: run_svc.create_run(
            project_id=PROJECT,
            actor_id="user_music_center",
            readiness_receipt_id=receipt.receipt_id,
        )
    )
    assert run.status is not OptimizationRunStatus.COMPLETE
    with pytest.raises(ScenarioRequiresCompletedOptimizationError):
        create_scenario(gov, run.optimization_run_id)


def test_scenario_binds_exact_optimization_result() -> None:
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    assert scenario.optimization_run_id == run.optimization_run_id
    assert scenario.optimization_result_ref == run.result_id
    assert scenario.recommendation_fingerprint == run.result_fingerprint


def test_scenario_immutable() -> None:
    gov, run_svc, receipt, store, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    mutated = scenario.model_copy(update={"artifact_fingerprint": "tampered"})
    with pytest.raises(PersistenceBarrierError):
        store.put(mutated)


def test_scenario_uses_model_recommended_label() -> None:
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    assert scenario.amount_kind is OptimizationAmountKind.MODEL_RECOMMENDED
    assert scenario.scenario_type is ScenarioType.OPTIMIZER_RECOMMENDATION


def test_scenario_not_approved_plan() -> None:
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    dumped = scenario.model_dump()
    assert "APPROVED_PLAN" not in str(dumped)
    assert dumped["amount_kind"] == "MODEL_RECOMMENDED"
    assert_optimization_metadata_only(scenario)

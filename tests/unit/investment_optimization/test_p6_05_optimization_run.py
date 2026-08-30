"""P6-05 native fixed-budget optimization: readiness, invariant, result, authority."""

from __future__ import annotations

import inspect
import math
from decimal import Decimal

import pytest

from app.core.tenancy import bind_tenant
from app.investment_optimization.adapter import (
    NATIVE_OPTIMIZER_IMPORT,
    NativeMeridianFixedBudgetAdapter,
    UnimplementedMeridianBudgetOptimizerAdapter,
)
from app.investment_optimization.contracts import (
    NativeOptimizerChannelResult,
    NativeOptimizerRawResult,
)
from app.investment_optimization.enums import (
    PINNED_MERIDIAN_RUNTIME,
    OptimizationAmountKind,
    OptimizationFailureClass,
    OptimizationReadinessStatus,
    OptimizationRunStatus,
)
from app.investment_optimization.errors import (
    ActualsNotFixedBudgetError,
    ClientBudgetArrayRejectedError,
    CrossProjectRunAccessError,
    CrossTenantRunAccessError,
    ModelArtifactUnavailableError,
    NativeOptimizerFailedError,
    OptimizationNotReadyError,
    OptimizationReadinessStaleError,
    OptimizationReviewRequiredError,
    ResultReadbackFailedError,
    UnapprovedPlanError,
)
from app.investment_planning.enums import PortfolioBaselineKind
from app.investment_planning.errors import PlanningAuthorityError
from app.modeling.mmm.states import MMMModelingStage
from app.service.object_store import FakeObjectStore
from tests.unit.investment_optimization.p6_04_support import (
    PROJECT,
    TENANT,
    allocation,
    complete_contract,
    portfolio_view,
    snapshot,
    spend_variable,
)
from tests.unit.investment_optimization.p6_05_support import (
    ScriptedFixedBudgetOptimizer,
    bound,
    run_service,
    tenant_ctx,
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


def _result(service, run_id: str):
    return bound(lambda: service.get_result(optimization_run_id=run_id, project_id=PROJECT))


def test_optimization_requires_ready_receipt() -> None:
    service, receipt, *_ = run_service()
    assert receipt.status is OptimizationReadinessStatus.OPTIMIZATION_READY
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.COMPLETE


def test_not_ready_receipt_rejected() -> None:
    service, receipt, store, *_ = run_service()
    stale = receipt.model_copy(update={"status": OptimizationReadinessStatus.NOT_READY})
    store.put(stale)
    with pytest.raises(OptimizationNotReadyError):
        _create(service, stale.receipt_id)


def test_review_required_receipt_rejected() -> None:
    service, receipt, store, *_ = run_service()
    review = receipt.model_copy(update={"status": OptimizationReadinessStatus.REVIEW_REQUIRED})
    store.put(review)
    with pytest.raises(OptimizationReviewRequiredError):
        _create(service, review.receipt_id)


def test_stale_receipt_rejected() -> None:
    service, receipt, *_rest = run_service()
    service._planning.snapshot = snapshot(fingerprint="fp_snap_changed")
    with pytest.raises(OptimizationReadinessStaleError):
        _create(service, receipt.receipt_id)


def test_receipt_fingerprint_revalidated_at_dispatch() -> None:
    service, receipt, store, mapping, *_ = run_service()
    store.put(mapping.model_copy(update={"fingerprint": "fp_mapping_changed"}))
    with pytest.raises(OptimizationReadinessStaleError):
        _create(service, receipt.receipt_id)


def test_approved_drive_plan_is_budget_authority() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    result = _result(service, run.optimization_run_id)
    assert result.fixed_budget == Decimal("100.00")
    assert result.amount_kind is OptimizationAmountKind.MODEL_RECOMMENDED


def test_client_budget_array_rejected() -> None:
    service, receipt, *_ = run_service()
    with pytest.raises(ClientBudgetArrayRejectedError):
        _create(
            service,
            receipt.receipt_id,
            budget_array=[{"channel": "search_paid", "amount": "10"}],
        )


def test_actuals_not_used_as_fixed_budget() -> None:
    service, receipt, *_ = run_service()
    service._planning.view = portfolio_view(baseline=PortfolioBaselineKind.ACTUAL_YTD)
    with pytest.raises(ActualsNotFixedBudgetError):
        _create(service, receipt.receipt_id)


def test_unapproved_plan_rejected() -> None:
    service, receipt, *_ = run_service()
    service._planning.plan_status = "DRAFT"
    with pytest.raises(UnapprovedPlanError):
        _create(service, receipt.receipt_id)


def test_changed_plan_version_stales_execution() -> None:
    service, receipt, *_ = run_service()
    service._planning.snapshot = snapshot(fingerprint="fp_plan_v2")
    with pytest.raises(OptimizationReadinessStaleError):
        _create(service, receipt.receipt_id)


def test_model_version_matches_readiness_receipt() -> None:
    service, receipt, *_rest = run_service()
    run = _create(service, receipt.receipt_id)
    assert run.model_version_id == receipt.model_version_id


def test_model_change_stales_execution() -> None:
    service, receipt, _store, _mapping, _input, _contract, version, models = run_service()
    models._versions[:] = [
        version.model_copy(update={"model_plan_fingerprint": "fp_plan_new"})
    ]
    with pytest.raises(OptimizationReadinessStaleError):
        _create(service, receipt.receipt_id)


def test_model_artifact_unavailable_fails() -> None:
    optimizer = ScriptedFixedBudgetOptimizer(error=ModelArtifactUnavailableError("missing binpb"))
    service, receipt, *_ = run_service(optimizer=optimizer)
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.FAILED
    assert run.failure_class is OptimizationFailureClass.MODEL_ARTIFACT_UNAVAILABLE


def test_model_acceptance_not_mutated_by_optimizer() -> None:
    service, receipt, _store, _m, _i, _c, version, models = run_service()
    _create(service, receipt.receipt_id)
    loaded = models.get_version(
        tenant_id=TENANT, project_id=PROJECT, model_version_id=version.model_version_id
    )
    assert loaded is not None
    assert loaded.accepted is True
    assert loaded.state is MMMModelingStage.MODEL_ACCEPTED


def test_native_meridian_optimizer_path_used() -> None:
    source = inspect.getsource(NativeMeridianFixedBudgetAdapter.optimize_fixed_budget)
    assert "BudgetOptimizer" in source
    assert "fixed_budget=True" in source
    assert "use_posterior=True" in source
    assert NATIVE_OPTIMIZER_IMPORT == ("meridian.analysis.optimizer", "BudgetOptimizer")


def test_no_custom_optimizer_primary_path() -> None:
    adapter = NativeMeridianFixedBudgetAdapter()
    assert adapter.supported_solvers[0].value == "MERIDIAN_NATIVE_FIXED_BUDGET"
    unimplemented = UnimplementedMeridianBudgetOptimizerAdapter()
    assert unimplemented.deferred_solvers[0].value == "PREM3_RISK_AWARE_FRONTIER"


def test_runtime_version_pinned() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    assert run.runtime_version == PINNED_MERIDIAN_RUNTIME == "1.8.0"


def test_optimizer_input_matches_mapping() -> None:
    optimizer = ScriptedFixedBudgetOptimizer()
    service, receipt, _s, mapping, *_ = run_service(optimizer=optimizer)
    _create(service, receipt.receipt_id)
    expected = tuple(entry.model_variable_id for entry in mapping.mapping_entries)
    assert optimizer.calls[0]["variable_ids"] == expected


def test_optimizer_failure_classified() -> None:
    optimizer = ScriptedFixedBudgetOptimizer(error=NativeOptimizerFailedError("native boom"))
    service, receipt, *_ = run_service(optimizer=optimizer)
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.FAILED
    assert run.failure_class is OptimizationFailureClass.NATIVE_OPTIMIZER_FAILED


def test_recommended_total_equals_fixed_budget() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    result = _result(service, run.optimization_run_id)
    assert result.recommended_total == result.fixed_budget == Decimal("100.00")


def test_rounding_reconciles_to_fixed_budget() -> None:
    view = portfolio_view(
        rows=(
            allocation("mkt_us", "search_paid", "60.00"),
            allocation("mkt_us", "social_paid", "40.00"),
        )
    )
    contract = complete_contract(
        variables=(
            spend_variable("search_spend", "search_paid"),
            spend_variable("social_spend", "social_paid"),
        )
    )
    optimizer = ScriptedFixedBudgetOptimizer(
        {"search_spend": 60.004, "social_spend": 39.997}
    )
    service, receipt, *_ = run_service(optimizer=optimizer, view=view, contract=contract)
    run = _create(service, receipt.receipt_id)
    result = _result(service, run.optimization_run_id)
    assert result.recommended_total == result.fixed_budget


def test_budget_invariant_failure_blocks_complete() -> None:
    optimizer = ScriptedFixedBudgetOptimizer({"search_spend": 250.0})
    service, receipt, *_ = run_service(optimizer=optimizer)
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.FAILED
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_BUDGET_INVARIANT_FAILED


def test_fixed_variables_unchanged() -> None:
    view = portfolio_view(
        rows=(
            allocation("mkt_us", "search_paid", "80.00"),
            allocation("mkt_us", "social_paid", "20.00"),
        )
    )
    contract = complete_contract(
        variables=(
            spend_variable("search_spend", "search_paid"),
            spend_variable("social_spend", "social_paid"),
        )
    )
    service, receipt, store, _m, input_contract, *_ = run_service(view=view, contract=contract)
    store.put(
        input_contract.model_copy(
            update={
                "fixed_variable_ids": ("social_spend",),
                "optimizable_variable_ids": ("search_spend",),
            }
        )
    )
    run = _create(service, receipt.receipt_id)
    result = _result(service, run.optimization_run_id)
    social = next(row for row in result.rows if row.model_variable_id == "social_spend")
    assert social.recommended == social.baseline == Decimal("20.00")


def test_excluded_variables_not_reallocated() -> None:
    view = portfolio_view(
        rows=(
            allocation("mkt_us", "search_paid", "100.00"),
            allocation("mkt_us", "social_paid", "50.00"),
        )
    )
    contract = complete_contract(
        variables=(
            spend_variable("search_spend", "search_paid"),
            spend_variable("social_spend", "social_paid"),
        )
    )
    service, receipt, store, _m, input_contract, *_ = run_service(view=view, contract=contract)
    store.put(
        input_contract.model_copy(
            update={
                "excluded_variable_ids": ("social_spend",),
                "optimizable_variable_ids": ("search_spend",),
            }
        )
    )

    class ReallocateExcluded(ScriptedFixedBudgetOptimizer):
        def optimize_fixed_budget(self, **kwargs):
            return NativeOptimizerRawResult(
                channels=(
                    NativeOptimizerChannelResult(
                        model_variable_id="search_spend", recommended_spend=100.0
                    ),
                    NativeOptimizerChannelResult(
                        model_variable_id="social_spend", recommended_spend=50.0
                    ),
                )
            )

    service._optimizer = ReallocateExcluded()
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.FAILED
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_RESULT_INVALID


def test_unknown_model_variable_rejected() -> None:
    class UnknownVar(ScriptedFixedBudgetOptimizer):
        def optimize_fixed_budget(self, **kwargs):
            return NativeOptimizerRawResult(
                channels=(
                    NativeOptimizerChannelResult(
                        model_variable_id="search_spend", recommended_spend=100.0
                    ),
                    NativeOptimizerChannelResult(
                        model_variable_id="ghost", recommended_spend=0.0
                    ),
                )
            )

    service, receipt, *_ = run_service(optimizer=UnknownVar())
    run = _create(service, receipt.receipt_id)
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_RESULT_INVALID


def test_missing_expected_variable_rejected() -> None:
    class MissingVar(ScriptedFixedBudgetOptimizer):
        def optimize_fixed_budget(self, **kwargs):
            return NativeOptimizerRawResult(channels=())

    service, receipt, *_ = run_service(optimizer=MissingVar())
    run = _create(service, receipt.receipt_id)
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_RESULT_INVALID


def test_nan_result_rejected() -> None:
    service, receipt, *_ = run_service(
        optimizer=ScriptedFixedBudgetOptimizer({"search_spend": math.nan})
    )
    run = _create(service, receipt.receipt_id)
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_RESULT_INVALID


def test_infinite_result_rejected() -> None:
    service, receipt, *_ = run_service(
        optimizer=ScriptedFixedBudgetOptimizer({"search_spend": math.inf})
    )
    run = _create(service, receipt.receipt_id)
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_RESULT_INVALID


def test_negative_amount_rejected_v1() -> None:
    service, receipt, *_ = run_service(
        optimizer=ScriptedFixedBudgetOptimizer({"search_spend": -1.0})
    )
    run = _create(service, receipt.receipt_id)
    assert run.failure_class is OptimizationFailureClass.OPTIMIZER_RESULT_INVALID


def test_zero_amount_distinct_from_missing() -> None:
    view = portfolio_view(
        rows=(
            allocation("mkt_us", "search_paid", "70.00"),
            allocation("mkt_us", "social_paid", "30.00"),
        )
    )
    contract = complete_contract(
        variables=(
            spend_variable("search_spend", "search_paid"),
            spend_variable("social_spend", "social_paid"),
        )
    )
    service, receipt, *_ = run_service(
        optimizer=ScriptedFixedBudgetOptimizer({"search_spend": 100.0, "social_spend": 0.0}),
        view=view,
        contract=contract,
    )
    run = _create(service, receipt.receipt_id)
    result = _result(service, run.optimization_run_id)
    social = next(row for row in result.rows if row.model_variable_id == "social_spend")
    assert social.recommended == Decimal("0.00")
    assert run.status is OptimizationRunStatus.COMPLETE


def test_result_requires_artifact_readback() -> None:
    service, receipt, *_ = run_service(execute_inline=False)
    run = _create(service, receipt.receipt_id)
    assert run.status is OptimizationRunStatus.DISPATCHED
    with pytest.raises(ResultReadbackFailedError):
        _result(service, run.optimization_run_id)


def test_readback_schema_verified() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    raw = service._object_store.read_bytes(
        bucket="prem3-test-artifacts",
        object_name=run.artifact_object_name or "",
    )
    assert raw is not None
    assert b'"schema_version":"p6-05/v1"' in raw or b"p6-05/v1" in raw


def test_readback_fingerprint_verified() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    service._object_store.objects[
        ("prem3-test-artifacts", run.artifact_object_name)
    ]["data"] = b'{"schema_version":"p6-05/v1","fingerprint":"tampered"}'
    with pytest.raises(ResultReadbackFailedError):
        _result(service, run.optimization_run_id)


def test_failed_readback_never_complete() -> None:
    class BlindStore(FakeObjectStore):
        def read_bytes(self, *, bucket: str, object_name: str) -> bytes | None:
            del bucket, object_name
            return None

    service, receipt, *_ = run_service(object_store=BlindStore())
    run = _create(service, receipt.receipt_id)
    assert run.status is not OptimizationRunStatus.COMPLETE
    assert run.failure_class is OptimizationFailureClass.RESULT_READBACK_FAILED


def test_completed_result_artifact_immutable() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    with pytest.raises(FileExistsError):
        service._object_store.write_bytes(
            bucket="prem3-test-artifacts",
            object_name=run.artifact_object_name or "",
            data=b"overwrite",
        )


def test_rerun_creates_new_run() -> None:
    service, receipt, *_ = run_service()
    first = _create(service, receipt.receipt_id)
    second = _create(service, receipt.receipt_id)
    assert first.optimization_run_id != second.optimization_run_id
    assert first.artifact_object_name != second.artifact_object_name


def test_optimizer_does_not_mutate_drive_plan() -> None:
    service, receipt, *_ = run_service()
    _create(service, receipt.receipt_id)
    assert service._planning.drive_writes == []


def test_optimizer_does_not_create_plan_revision() -> None:
    service, receipt, *_ = run_service()
    _create(service, receipt.receipt_id)
    assert service._planning.plan_revisions == []


def test_client_cannot_supply_tenant() -> None:
    service, receipt, *_ = run_service()
    with pytest.raises(PlanningAuthorityError, match="tenant_id"):
        _create(service, receipt.receipt_id, tenant_id=TENANT)


def test_cross_project_run_access_fails() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    with pytest.raises(CrossProjectRunAccessError):
        bound(
            lambda: service.get_run(
                optimization_run_id=run.optimization_run_id,
                project_id="wsp_otherotherotheroth",
            )
        )


def test_cross_tenant_run_access_fails() -> None:
    service, receipt, *_ = run_service()
    run = _create(service, receipt.receipt_id)
    other = tenant_ctx().model_copy(update={"tenant_id": "ten_otherotherotherother"})
    with bind_tenant(other):
        with pytest.raises(CrossTenantRunAccessError):
            service.get_run(optimization_run_id=run.optimization_run_id, project_id=PROJECT)


def test_client_cannot_supply_model_path() -> None:
    service, receipt, *_ = run_service()
    with pytest.raises(PlanningAuthorityError, match="model"):
        _create(service, receipt.receipt_id, model_path="gs://secret/model.binpb")


def test_client_cannot_supply_drive_path() -> None:
    service, receipt, *_ = run_service()
    with pytest.raises(PlanningAuthorityError, match="Drive"):
        _create(service, receipt.receipt_id, drive_path="drive://folder")

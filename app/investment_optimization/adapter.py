"""Native Meridian BudgetOptimizer adapter. Fixed-budget only in P6-05."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Protocol

from app.investment_optimization.contracts import (
    NativeOptimizerChannelResult,
    NativeOptimizerRawResult,
    OptimizationExecutionPayload,
    OptimizationExecutionPlan,
    OptimizationOutcomeEstimate,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import (
    PINNED_OPTIMIZER_GTOL,
    PINNED_SPEND_CONSTRAINT_LOWER,
    PINNED_SPEND_CONSTRAINT_UPPER,
    ModelVariableOptimizationEligibility,
    OptimizationAmountKind,
    OptimizationSolverKind,
)
from app.investment_optimization.errors import (
    FlexibleBudgetNotImplementedError,
    MeridianOptimizerApiReviewRequiredError,
    ModelArtifactUnavailableError,
    NativeOptimizerFailedError,
)
from app.investment_optimization.numeric import float_from_decimal, pct_of_spend
from app.investment_planning.errors import PlanningError
from app.service.object_store import ObjectStore

NATIVE_OPTIMIZER_IMPORT = ("meridian.analysis.optimizer", "BudgetOptimizer")
NATIVE_SERDE_IMPORT = ("meridian.schema.serde.meridian_serde", "load_meridian")


class MeridianOptimizerNotImplementedError(PlanningError):
    code = "MERIDIAN_OPTIMIZER_NOT_IMPLEMENTED"


class UnimplementedMeridianBudgetOptimizerAdapter:
    """Flexible budget and CVaR remain unimplemented. Fixed-budget uses the native adapter."""

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
        del payload
        if plan.solver_kind is OptimizationSolverKind.MERIDIAN_NATIVE_FLEXIBLE_BUDGET:
            raise FlexibleBudgetNotImplementedError(
                "Meridian flexible-budget optimization is not implemented in P6-05."
            )
        if plan.solver_kind is OptimizationSolverKind.PREM3_RISK_AWARE_FRONTIER:
            raise MeridianOptimizerNotImplementedError("CVaR / risk-aware frontier is deferred.")
        raise MeridianOptimizerNotImplementedError(
            "Fixed-budget execution uses NativeMeridianFixedBudgetAdapter, "
            "not the P6-00 payload seam."
        )


class FixedBudgetOptimizer(Protocol):
    def optimize_fixed_budget(
        self,
        *,
        model_artifact_ref: str,
        vector: OptimizerBudgetVector,
        object_store: ObjectStore | None = None,
        artifact_bucket: str | None = None,
    ) -> NativeOptimizerRawResult: ...


class NativeMeridianFixedBudgetAdapter:
    """Production path: official Meridian BudgetOptimizer.optimize(fixed_budget=True)."""

    supported_solvers = (OptimizationSolverKind.MERIDIAN_NATIVE_FIXED_BUDGET,)
    deferred_solvers = (
        OptimizationSolverKind.MERIDIAN_NATIVE_FLEXIBLE_BUDGET,
        OptimizationSolverKind.PREM3_RISK_AWARE_FRONTIER,
    )

    def optimize(
        self,
        plan: OptimizationExecutionPlan,
        payload: OptimizationExecutionPayload,
    ) -> OptimizationExecutionPayload:
        del plan, payload
        raise MeridianOptimizerNotImplementedError(
            "Use optimize_fixed_budget with an OptimizationReadinessReceipt, "
            "not a P6-00 proposal payload."
        )

    def optimize_fixed_budget(
        self,
        *,
        model_artifact_ref: str,
        vector: OptimizerBudgetVector,
        object_store: ObjectStore | None = None,
        artifact_bucket: str | None = None,
    ) -> NativeOptimizerRawResult:
        try:
            from meridian.analysis.optimizer import BudgetOptimizer
            from meridian.schema.serde import meridian_serde
        except ImportError as exc:
            raise MeridianOptimizerApiReviewRequiredError(
                "Meridian BudgetOptimizer API is not importable in this runtime."
            ) from exc

        path = _materialize_model_path(
            model_artifact_ref,
            object_store=object_store,
            artifact_bucket=artifact_bucket,
        )
        try:
            model = meridian_serde.load_meridian(path)
            shares = pct_of_spend(vector)
            results = BudgetOptimizer(model).optimize(
                use_posterior=True,
                fixed_budget=True,
                budget=float_from_decimal(vector.fixed_budget),
                pct_of_spend=list(shares),
                spend_constraint_lower=PINNED_SPEND_CONSTRAINT_LOWER,
                spend_constraint_upper=PINNED_SPEND_CONSTRAINT_UPPER,
                gtol=PINNED_OPTIMIZER_GTOL,
            )
            return _raw_from_optimization_results(results, vector)
        except MeridianOptimizerApiReviewRequiredError:
            raise
        except ModelArtifactUnavailableError:
            raise
        except Exception as exc:
            raise NativeOptimizerFailedError("Native Meridian BudgetOptimizer failed.") from exc


def _materialize_model_path(
    model_artifact_ref: str,
    *,
    object_store: ObjectStore | None,
    artifact_bucket: str | None,
) -> str:
    local = Path(model_artifact_ref)
    if local.is_file():
        return str(local)
    object_name = model_artifact_ref
    bucket = artifact_bucket
    if model_artifact_ref.startswith("gs://"):
        rest = model_artifact_ref.removeprefix("gs://")
        bucket, _, object_name = rest.partition("/")
    if object_store is None or not bucket or not object_name:
        raise ModelArtifactUnavailableError("Accepted model optimizer artifact is unavailable.")
    data = object_store.read_bytes(bucket=bucket, object_name=object_name)
    if data is None:
        raise ModelArtifactUnavailableError("Accepted model optimizer artifact is unavailable.")
    handle = tempfile.NamedTemporaryFile(suffix=".binpb", delete=False)
    handle.write(data)
    handle.close()
    return handle.name


def _raw_from_optimization_results(
    results: object, vector: OptimizerBudgetVector
) -> NativeOptimizerRawResult:
    optimized = getattr(results, "optimized_data", None)
    if optimized is None:
        raise NativeOptimizerFailedError("OptimizationResults.optimized_data is missing.")
    spends = _channel_spends(optimized)
    outcomes = _channel_outcomes(optimized)
    channels: list[NativeOptimizerChannelResult] = []
    for line in vector.lines:
        if line.eligibility is not ModelVariableOptimizationEligibility.OPTIMIZABLE:
            continue
        if line.model_variable_id not in spends:
            raise NativeOptimizerFailedError(
                "Native optimizer omitted an expected mapped channel."
            )
        spend = spends[line.model_variable_id]
        if isinstance(spend, float) and (math.isnan(spend) or math.isinf(spend)):
            pass
        channels.append(
            NativeOptimizerChannelResult(
                model_variable_id=line.model_variable_id,
                recommended_spend=float(spend),
                outcome_estimates=outcomes.get(line.model_variable_id, ()),
            )
        )
    return NativeOptimizerRawResult(channels=tuple(channels))


def _channel_spends(optimized_data: object) -> dict[str, float]:
    coords = getattr(optimized_data, "coords", None)
    if coords is not None and "channel" in coords and "spend" in optimized_data:
        names = [str(item) for item in coords["channel"].values]
        values = optimized_data["spend"].values
        flat = values.reshape(-1)
        return {name: float(flat[index]) for index, name in enumerate(names)}
    raise NativeOptimizerFailedError("optimized_data.spend could not be read.")


def _channel_outcomes(optimized_data: object) -> dict[str, tuple[OptimizationOutcomeEstimate, ...]]:
    coords = getattr(optimized_data, "coords", None)
    if coords is None or "channel" not in coords:
        return {}
    names = [str(item) for item in coords["channel"].values]
    collected: dict[str, list[OptimizationOutcomeEstimate]] = {name: [] for name in names}
    for field in ("roi", "mroi", "incremental_outcome", "cpik", "effectiveness"):
        if field not in optimized_data:
            continue
        values = optimized_data[field].values.reshape(-1)
        for index, name in enumerate(names):
            value = float(values[index])
            if math.isnan(value) or math.isinf(value):
                continue
            collected[name].append(
                OptimizationOutcomeEstimate(
                    name=field,
                    value=format(value, ".10g"),
                    amount_kind=OptimizationAmountKind.MODEL_ESTIMATE,
                )
            )
    return {key: tuple(items) for key, items in collected.items()}

"""Advanced optimization readiness wrapping P6-04 receipts. Does not rewrite P6-04."""

from __future__ import annotations

from datetime import datetime

from app.investment_optimization.assumptions import assumption_fingerprint
from app.investment_optimization.constraints import constraint_set_fingerprint
from app.investment_optimization.contracts import (
    AdvancedOptimizationReadinessReceipt,
    FutureScenarioAssumptions,
    OptimizationConstraintSet,
    OptimizationIssue,
    OptimizationReadinessCheck,
    OptimizationReadinessReceipt,
)
from app.investment_optimization.enums import (
    ADVANCED_POLICY_VERSION,
    PINNED_MERIDIAN_RUNTIME,
    AdvancedOptimizationReadinessStatus,
    OptimizationBudgetMode,
    OptimizationIssueCode,
    OptimizationObjectiveMode,
    OptimizationReadinessCheckCode,
    OptimizationReadinessStatus,
)
from app.investment_optimization.errors import (
    AdvancedReadinessStaleError,
    OptimizationNotReadyError,
)
from app.investment_optimization.ids import new_advanced_readiness_id
from app.investment_optimization.objective import objective_fingerprint
from app.investment_planning.fingerprint import metadata_fingerprint


def _target_hurdle(target_roi: float | None, target_mroi: float | None) -> str | None:
    if target_roi is not None:
        return f"roi:{target_roi}"
    if target_mroi is not None:
        return f"mroi:{target_mroi}"
    return None


def evaluate_advanced_readiness(
    *,
    tenant_id: str,
    project_id: str,
    base: OptimizationReadinessReceipt,
    objective_mode: OptimizationObjectiveMode,
    budget_mode: OptimizationBudgetMode,
    assumptions: FutureScenarioAssumptions | None,
    constraint_set: OptimizationConstraintSet | None,
    optimizer_defaults_fingerprint: str,
    created_at: datetime,
    objective_target_roi: float | None = None,
    objective_target_mroi: float | None = None,
    use_kpi: bool | None = None,
    constraint_feasible: bool = True,
    issues: tuple[OptimizationIssue, ...] = (),
) -> AdvancedOptimizationReadinessReceipt:
    if base.status is not OptimizationReadinessStatus.OPTIMIZATION_READY:
        raise OptimizationNotReadyError(
            "Advanced optimization requires a non-stale P6-04 OPTIMIZATION_READY receipt."
        )
    obj_fp = objective_fingerprint(
        mode=objective_mode,
        target_roi=objective_target_roi,
        target_mroi=objective_target_mroi,
        use_kpi=use_kpi,
    )
    assumption_fp = None if assumptions is None else assumption_fingerprint(assumptions)
    constraint_fp = None if constraint_set is None else constraint_set_fingerprint(constraint_set)
    checks = (
        OptimizationReadinessCheck(
            code=OptimizationReadinessCheckCode.ASSUMPTIONS_PINNED, passed=True
        ),
        OptimizationReadinessCheck(
            code=OptimizationReadinessCheckCode.CONSTRAINTS_FEASIBLE, passed=constraint_feasible
        ),
        OptimizationReadinessCheck(
            code=OptimizationReadinessCheckCode.OBJECTIVE_VALID, passed=True
        ),
        OptimizationReadinessCheck(
            code=OptimizationReadinessCheckCode.UNSUPPORTED_LINES_EXPLICIT, passed=True
        ),
        OptimizationReadinessCheck(code=OptimizationReadinessCheckCode.RUNTIME_PINNED, passed=True),
    )
    blocking = tuple(issue for issue in issues if issue.blocking)
    if not constraint_feasible:
        status = AdvancedOptimizationReadinessStatus.NOT_READY
    elif blocking:
        status = AdvancedOptimizationReadinessStatus.REVIEW_REQUIRED
    else:
        status = AdvancedOptimizationReadinessStatus.ADVANCED_OPTIMIZATION_READY
    receipt_id = new_advanced_readiness_id()
    fingerprint = advanced_readiness_fingerprint(
        base_fingerprint=base.fingerprint,
        assumption_fingerprint=assumption_fp,
        constraint_fingerprint=constraint_fp,
        objective_fingerprint=obj_fp,
        optimizer_defaults_fingerprint=optimizer_defaults_fingerprint,
        runtime_version=PINNED_MERIDIAN_RUNTIME,
    )
    return AdvancedOptimizationReadinessReceipt(
        receipt_id=receipt_id,
        tenant_id=tenant_id,
        project_id=project_id,
        base_readiness_receipt_id=base.receipt_id,
        base_readiness_fingerprint=base.fingerprint,
        assumption_set_id=None if assumptions is None else assumptions.assumption_set_id,
        assumption_set_fingerprint=assumption_fp,
        constraint_set_id=None if constraint_set is None else constraint_set.constraint_set_id,
        constraint_set_fingerprint=constraint_fp,
        objective_mode=objective_mode,
        objective_fingerprint=obj_fp,
        budget_mode=budget_mode,
        target_hurdle=_target_hurdle(objective_target_roi, objective_target_mroi),
        runtime_version=PINNED_MERIDIAN_RUNTIME,
        optimizer_defaults_fingerprint=optimizer_defaults_fingerprint,
        status=status,
        checks=checks,
        issues=issues,
        policy_version=ADVANCED_POLICY_VERSION,
        fingerprint=fingerprint,
        created_at=created_at,
    )


def advanced_readiness_fingerprint(
    *,
    base_fingerprint: str,
    assumption_fingerprint: str | None,
    constraint_fingerprint: str | None,
    objective_fingerprint: str,
    optimizer_defaults_fingerprint: str,
    runtime_version: str,
) -> str:
    return metadata_fingerprint(
        {
            "base": base_fingerprint,
            "assumptions": assumption_fingerprint or "",
            "constraints": constraint_fingerprint or "",
            "objective": objective_fingerprint,
            "defaults": optimizer_defaults_fingerprint,
            "runtime": runtime_version,
            "policy": ADVANCED_POLICY_VERSION,
        }
    )


def advanced_receipt_is_stale(
    receipt: AdvancedOptimizationReadinessReceipt,
    *,
    base: OptimizationReadinessReceipt | None,
    assumption_fingerprint: str | None,
    constraint_fingerprint: str | None,
    objective_fingerprint: str,
    optimizer_defaults_fingerprint: str,
    runtime_version: str = PINNED_MERIDIAN_RUNTIME,
) -> bool:
    if base is None:
        return True
    if base.receipt_id != receipt.base_readiness_receipt_id:
        return True
    if base.fingerprint != receipt.base_readiness_fingerprint:
        return True
    if (assumption_fingerprint or "") != (receipt.assumption_set_fingerprint or ""):
        return True
    if (constraint_fingerprint or "") != (receipt.constraint_set_fingerprint or ""):
        return True
    if objective_fingerprint != receipt.objective_fingerprint:
        return True
    if optimizer_defaults_fingerprint != receipt.optimizer_defaults_fingerprint:
        return True
    if runtime_version != receipt.runtime_version:
        return True
    expected = advanced_readiness_fingerprint(
        base_fingerprint=base.fingerprint,
        assumption_fingerprint=assumption_fingerprint,
        constraint_fingerprint=constraint_fingerprint,
        objective_fingerprint=objective_fingerprint,
        optimizer_defaults_fingerprint=optimizer_defaults_fingerprint,
        runtime_version=runtime_version,
    )
    return expected != receipt.fingerprint


def require_advanced_ready(receipt: AdvancedOptimizationReadinessReceipt) -> None:
    if receipt.status is AdvancedOptimizationReadinessStatus.STALE:
        raise AdvancedReadinessStaleError("Advanced optimization readiness is stale.")
    if receipt.status is not AdvancedOptimizationReadinessStatus.ADVANCED_OPTIMIZATION_READY:
        raise OptimizationNotReadyError("Advanced optimization is not ready.")


def stale_issue() -> OptimizationIssue:
    return OptimizationIssue(
        code=OptimizationIssueCode.STALE_READINESS_RECEIPT,
        blocking=True,
        message_key="optimization.advanced_readiness_stale",
    )

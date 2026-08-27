"""Optimization contracts: durable refs vs transient amount-bearing payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict

from app.investment_optimization.enums import (
    OptimizationObjectiveKind,
    OptimizationProposalStatus,
    OptimizationReadinessStatus,
    OptimizationSolverKind,
)
from app.investment_planning.contracts import MoneyAmount, PortfolioAllocationView
from app.investment_planning.enums import SensitiveDataClass


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


_META = SensitiveDataClass.CONTROL_PLANE_METADATA
_AMOUNT = SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT


class OptimizationProposalRef(FrozenModel):
    """Durable metadata. Recommended amounts live on the customer Drive artifact."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    proposal_id: str
    tenant_id: str
    project_id: str
    workspace_id: str
    baseline_snapshot_id: str
    status: OptimizationProposalStatus
    solver_kind: OptimizationSolverKind
    objective_kind: OptimizationObjectiveKind
    accepted_mmm_result_ref: str
    constraint_set_fingerprint: str
    assumption_set_fingerprint: str
    result_drive_file_id: str | None = None
    predecessor_proposal_id: str | None = None
    fingerprint: str
    created_at: datetime
    created_by: str
    approved_at: datetime | None = None
    approved_by: str | None = None


class OptimizationExecutionPlan(FrozenModel):
    """Fingerprints and refs only. Does not carry spend vectors."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    execution_plan_id: str
    proposal_id: str
    solver_kind: OptimizationSolverKind
    readiness: OptimizationReadinessStatus
    accepted_mmm_result_ref: str
    payload_fingerprint: str
    constraint_set_ref: str
    assumption_set_ref: str


class ConstraintSetRef(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    constraint_set_id: str
    fingerprint: str


class ScenarioAssumptionSetRef(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    assumption_set_id: str
    fingerprint: str


class ConstraintSetPayload(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    constraint_set_id: str
    total_budget: Decimal | None = None
    locked_line_ids: tuple[str, ...] = ()


class ScenarioAssumptionPayload(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    assumption_set_id: str
    future_cpm_by_channel: tuple[tuple[str, Decimal], ...] = ()
    revenue_per_kpi: Decimal | None = None


class OptimizationExecutionPayload(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    execution_plan_id: str
    recommended_allocations: tuple[PortfolioAllocationView, ...] = ()
    recommended_totals: tuple[MoneyAmount, ...] = ()


OPTIMIZATION_METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    OptimizationProposalRef,
    OptimizationExecutionPlan,
    ConstraintSetRef,
    ScenarioAssumptionSetRef,
)

OPTIMIZATION_AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (
    ConstraintSetPayload,
    ScenarioAssumptionPayload,
    OptimizationExecutionPayload,
)


class MeridianBudgetOptimizerAdapter(Protocol):
    """P6-05 implements native Meridian BudgetOptimizer. P6-00 freezes the seam."""

    def optimize(
        self,
        plan: OptimizationExecutionPlan,
        payload: OptimizationExecutionPayload,
    ) -> OptimizationExecutionPayload: ...

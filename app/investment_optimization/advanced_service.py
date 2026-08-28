"""Create governed assumption/constraint sets and advanced readiness. Amounts stay on GCS."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.investment_optimization.advanced_artifacts import (
    read_assumption_artifact,
    read_constraint_artifact,
    write_assumption_artifact,
    write_constraint_artifact,
)
from app.investment_optimization.advanced_readiness import (
    advanced_receipt_is_stale,
    evaluate_advanced_readiness,
)
from app.investment_optimization.assumptions import pin_assumptions
from app.investment_optimization.constraint_validate import validate_constraint_set
from app.investment_optimization.constraints import pin_constraint_set
from app.investment_optimization.contracts import (
    AdvancedOptimizationReadinessReceipt,
    ConstraintSetRef,
    ConstraintValidationReceipt,
    FutureScenarioAssumptions,
    OptimizationConstraintSet,
    OptimizerBudgetLine,
    ScenarioAssumptionSetRef,
)
from app.investment_optimization.enums import (
    ConstraintValidationStatus,
    OptimizationObjectiveMode,
)
from app.investment_optimization.errors import (
    AdvancedReadinessStaleError,
    AssumptionSetNotFoundError,
    ConstraintSetInfeasibleError,
    ConstraintSetNotFoundError,
    OptimizationNotReadyError,
)
from app.investment_optimization.execution import optimizer_defaults_fingerprint
from app.investment_optimization.feasibility import prove_feasible
from app.investment_optimization.ids import new_assumption_set_id, new_constraint_set_id
from app.investment_optimization.objective import budget_mode_for, use_kpi_for, validate_objective
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.authority import require_human_approver, require_server_owned_scope
from app.investment_planning.errors import PlanningAuthorityError
from app.service.entitlements import require_feature
from app.service.object_store import ObjectStore


class AdvancedOptimizationService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        store: OptimizationMetadataStore,
        object_store: ObjectStore,
        artifact_bucket: str,
    ) -> None:
        self._repo = repo
        self._store = store
        self._object_store = object_store
        self._artifact_bucket = artifact_bucket

    def create_assumption_set(
        self,
        *,
        project_id: str,
        actor_id: str,
        assumptions: FutureScenarioAssumptions,
        tenant_id: str | None = None,
    ) -> ScenarioAssumptionSetRef:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        require_human_approver(actor_id)
        if tenant_id is not None:
            raise PlanningAuthorityError("Client cannot supply tenant_id.")
        set_id = assumptions.assumption_set_id or new_assumption_set_id()
        pinned = pin_assumptions(
            assumptions.model_copy(
                update={"assumption_set_id": set_id, "project_id": project_id}
            ),
            created_at=datetime.now(UTC),
        )
        object_name, generation = write_assumption_artifact(
            store=self._object_store, bucket=self._artifact_bucket, assumptions=pinned
        )
        ref = ScenarioAssumptionSetRef(
            assumption_set_id=pinned.assumption_set_id,
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            artifact_bucket=self._artifact_bucket,
            artifact_object_name=object_name,
            artifact_generation=generation,
            created_at=pinned.created_at,
            fingerprint=pinned.fingerprint,
        )
        stored = self._store.put(ref)
        assert isinstance(stored, ScenarioAssumptionSetRef)
        return stored

    def get_assumption_ref(
        self, *, assumption_set_id: str, project_id: str
    ) -> ScenarioAssumptionSetRef:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        ref = self._store.get_assumption_ref(assumption_set_id)
        if ref is None or ref.project_id not in {None, project_id}:
            raise AssumptionSetNotFoundError("Assumption set was not found.")
        if ref.tenant_id not in {None, tenant.tenant_id}:
            raise AssumptionSetNotFoundError("Assumption set was not found.")
        return ref

    def load_assumptions(self, ref: ScenarioAssumptionSetRef) -> FutureScenarioAssumptions:
        if not ref.artifact_bucket or not ref.artifact_object_name:
            raise AssumptionSetNotFoundError("Assumption set artifact is unavailable.")
        loaded = read_assumption_artifact(
            store=self._object_store,
            bucket=ref.artifact_bucket,
            object_name=ref.artifact_object_name,
        )
        if loaded is None:
            raise AssumptionSetNotFoundError("Assumption set artifact is unavailable.")
        return loaded

    def create_constraint_set(
        self,
        *,
        project_id: str,
        actor_id: str,
        constraint_set: OptimizationConstraintSet,
        tenant_id: str | None = None,
    ) -> ConstraintSetRef:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        require_human_approver(actor_id)
        if tenant_id is not None:
            raise PlanningAuthorityError("Client cannot supply tenant_id.")
        set_id = constraint_set.constraint_set_id or new_constraint_set_id()
        pinned = pin_constraint_set(
            constraint_set.model_copy(
                update={"constraint_set_id": set_id, "project_id": project_id}
            )
        )
        object_name, generation = write_constraint_artifact(
            store=self._object_store, bucket=self._artifact_bucket, constraint_set=pinned
        )
        ref = ConstraintSetRef(
            constraint_set_id=pinned.constraint_set_id,
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            artifact_bucket=self._artifact_bucket,
            artifact_object_name=object_name,
            artifact_generation=generation,
            created_at=datetime.now(UTC),
            fingerprint=pinned.fingerprint,
        )
        stored = self._store.put(ref)
        assert isinstance(stored, ConstraintSetRef)
        return stored

    def get_constraint_ref(self, *, constraint_set_id: str, project_id: str) -> ConstraintSetRef:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        ref = self._store.get_constraint_ref(constraint_set_id)
        if ref is None or ref.project_id not in {None, project_id}:
            raise ConstraintSetNotFoundError("Constraint set was not found.")
        if ref.tenant_id not in {None, tenant.tenant_id}:
            raise ConstraintSetNotFoundError("Constraint set was not found.")
        return ref

    def load_constraints(self, ref: ConstraintSetRef) -> OptimizationConstraintSet:
        if not ref.artifact_bucket or not ref.artifact_object_name:
            raise ConstraintSetNotFoundError("Constraint set artifact is unavailable.")
        loaded = read_constraint_artifact(
            store=self._object_store,
            bucket=ref.artifact_bucket,
            object_name=ref.artifact_object_name,
        )
        if loaded is None:
            raise ConstraintSetNotFoundError("Constraint set artifact is unavailable.")
        return loaded

    def validate_constraints(
        self,
        *,
        project_id: str,
        actor_id: str,
        constraint_set_id: str,
        lines: tuple[OptimizerBudgetLine, ...] = (),
        currency: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> ConstraintValidationReceipt:
        del actor_id
        ref = self.get_constraint_ref(constraint_set_id=constraint_set_id, project_id=project_id)
        payload = self.load_constraints(ref)
        receipt = validate_constraint_set(
            payload,
            lines=lines,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
            created_at=datetime.now(UTC),
        )
        if receipt.status is ConstraintValidationStatus.INFEASIBLE:
            raise ConstraintSetInfeasibleError(
                "Constraint set does not admit a feasible allocation.",
                conflicting_constraint_ids=receipt.conflicting_constraint_ids,
            )
        return receipt

    def evaluate(
        self,
        *,
        project_id: str,
        actor_id: str,
        base_readiness_receipt_id: str,
        objective_mode: OptimizationObjectiveMode,
        assumption_set_id: str | None = None,
        constraint_set_id: str | None = None,
        target_roi: float | None = None,
        target_mroi: float | None = None,
        use_kpi: bool | None = None,
        lines: tuple[OptimizerBudgetLine, ...] = (),
    ) -> AdvancedOptimizationReadinessReceipt:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        require_human_approver(actor_id)
        base = self._store.get_receipt(base_readiness_receipt_id)
        if base is None:
            raise OptimizationNotReadyError("Optimization readiness receipt was not found.")
        assumptions = None
        if assumption_set_id:
            assumptions = self.load_assumptions(
                self.get_assumption_ref(assumption_set_id=assumption_set_id, project_id=project_id)
            )
        constraints = None
        feasible = True
        if constraint_set_id:
            constraints = self.load_constraints(
                self.get_constraint_ref(constraint_set_id=constraint_set_id, project_id=project_id)
            )
            try:
                prove_feasible(constraints, lines=lines)
            except ConstraintSetInfeasibleError:
                feasible = False
        validate_objective(
            mode=objective_mode,
            assumptions=assumptions,
            target_roi=target_roi,
            target_mroi=target_mroi,
        )
        resolved_kpi = use_kpi if use_kpi is not None else use_kpi_for(
            mode=objective_mode, assumptions=assumptions
        )
        receipt = evaluate_advanced_readiness(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            base=base,
            objective_mode=objective_mode,
            budget_mode=budget_mode_for(objective_mode),
            assumptions=assumptions,
            constraint_set=constraints,
            optimizer_defaults_fingerprint=optimizer_defaults_fingerprint(),
            created_at=datetime.now(UTC),
            objective_target_roi=target_roi,
            objective_target_mroi=target_mroi,
            use_kpi=resolved_kpi,
            constraint_feasible=feasible,
        )
        stored = self._store.put(receipt)
        assert isinstance(stored, AdvancedOptimizationReadinessReceipt)
        return stored

    def get_advanced_receipt(
        self, *, receipt_id: str, project_id: str
    ) -> AdvancedOptimizationReadinessReceipt:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        receipt = self._store.get_advanced_receipt(receipt_id)
        if (
            receipt is None
            or receipt.project_id != project_id
            or receipt.tenant_id != tenant.tenant_id
        ):
            raise OptimizationNotReadyError(
                "Advanced optimization readiness receipt was not found."
            )
        return receipt

    def list_assumption_refs(self, *, project_id: str) -> tuple[ScenarioAssumptionSetRef, ...]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_assumption_refs(tenant_id=tenant.tenant_id, project_id=project_id)

    def list_constraint_refs(self, *, project_id: str) -> tuple[ConstraintSetRef, ...]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_constraint_refs(tenant_id=tenant.tenant_id, project_id=project_id)

    def list_advanced_receipts(
        self, *, project_id: str
    ) -> tuple[AdvancedOptimizationReadinessReceipt, ...]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_advanced_receipts(tenant_id=tenant.tenant_id, project_id=project_id)

    def require_current(
        self,
        receipt: AdvancedOptimizationReadinessReceipt,
        *,
        base_fingerprint: str,
        assumption_fingerprint: str | None,
        constraint_fingerprint: str | None,
        objective_fingerprint: str,
        optimizer_defaults_fingerprint: str,
    ) -> None:
        base = self._store.get_receipt(receipt.base_readiness_receipt_id)
        if advanced_receipt_is_stale(
            receipt,
            base=base,
            assumption_fingerprint=assumption_fingerprint,
            constraint_fingerprint=constraint_fingerprint,
            objective_fingerprint=objective_fingerprint,
            optimizer_defaults_fingerprint=optimizer_defaults_fingerprint,
        ) or (base is not None and base.fingerprint != base_fingerprint):
            raise AdvancedReadinessStaleError("Advanced optimization readiness is stale.")

"""Create and execute OptimizationRun records. Does not write Drive plans."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.investment_optimization.accepted_model import (
    AcceptedModelDirectory,
    select_accepted_model,
)
from app.investment_optimization.adapter import FixedBudgetOptimizer
from app.investment_optimization.advanced_artifacts import (
    read_assumption_artifact,
    read_constraint_artifact,
)
from app.investment_optimization.advanced_readiness import (
    advanced_receipt_is_stale,
    require_advanced_ready,
)
from app.investment_optimization.artifact import (
    read_back_result,
    result_fingerprint,
    write_result_artifact,
)
from app.investment_optimization.assumptions import assumption_fingerprint
from app.investment_optimization.budget_resolve import (
    reject_client_budget_authority,
    resolve_optimizer_budget,
)
from app.investment_optimization.compile_native import compile_native_spec
from app.investment_optimization.constraints import constraint_set_fingerprint
from app.investment_optimization.consumption import ModelConsumptionSource
from app.investment_optimization.contracts import (
    FutureScenarioAssumptions,
    OptimizationConstraintSet,
    OptimizationResultPayload,
    OptimizationResultRef,
    OptimizationRun,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import (
    ADVANCED_ARTIFACT_SCHEMA_VERSION,
    ARTIFACT_SCHEMA_VERSION,
    PINNED_MERIDIAN_RUNTIME,
    ModelVariableOptimizationEligibility,
    OptimizationAmountKind,
    OptimizationBudgetMode,
    OptimizationExecutionPhase,
    OptimizationFailureClass,
    OptimizationObjectiveMode,
    OptimizationRetrySemantics,
    OptimizationRunKind,
    OptimizationRunStatus,
)
from app.investment_optimization.errors import (
    ActualsNotFixedBudgetError,
    AdvancedReadinessStaleError,
    AssumptionSetNotFoundError,
    ClientBudgetArrayRejectedError,
    ConstraintReferenceInvalidError,
    ConstraintSetInfeasibleError,
    ConstraintSetNotFoundError,
    ConstraintUnitMismatchError,
    CrossProjectRunAccessError,
    CrossTenantRunAccessError,
    FinancialValueAssumptionRequiredError,
    FlexibleBudgetApiUnsupportedError,
    FlexibleBudgetNotImplementedError,
    FlightingAssumptionInvalidError,
    FunnelMappingRequiredError,
    FutureCostAssumptionInvalidError,
    MeridianOptimizerApiReviewRequiredError,
    ModelArtifactUnavailableError,
    NativeOptimizerFailedError,
    ObjectiveNotSupportedError,
    OptimizationError,
    OptimizationNotReadyError,
    OptimizationReadinessStaleError,
    OptimizationReviewRequiredError,
    OptimizationRunNotFoundError,
    OptimizerBudgetInvariantFailedError,
    OptimizerResultInvalidError,
    ProxyApprovalRequiredError,
    ResultConstraintViolationError,
    ResultReadbackFailedError,
    UnapprovedPlanError,
)
from app.investment_optimization.execution import (
    advanced_optimizer_defaults_fingerprint,
    execution_key,
    optimizer_defaults_fingerprint,
    revalidate_for_dispatch,
)
from app.investment_optimization.feasibility import prove_feasible
from app.investment_optimization.ids import new_optimization_result_id, new_optimization_run_id
from app.investment_optimization.numeric import (
    recommended_total,
    reconcile_flexible_spends,
    reconcile_recommended_spends,
)
from app.investment_optimization.objective import (
    budget_mode_for,
    objective_fingerprint,
    run_kind_for,
    use_kpi_for,
    validate_objective,
)
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_optimization.unsupported_channels import apply_unsupported_policies
from app.investment_optimization.validate_result import (
    validate_constraint_result,
    validate_raw_result,
    validate_reconciled_rows,
)
from app.investment_planning.authority import require_human_approver, require_server_owned_scope
from app.investment_planning.enums import InvestmentPlanStatus
from app.investment_planning.service import InvestmentPlanService
from app.service.entitlements import require_feature
from app.service.object_store import ObjectStore

LOGGER = logging.getLogger("prem3.investment_optimization")

_FAILURE_MAP: dict[type[Exception], tuple[OptimizationFailureClass, OptimizationRetrySemantics]] = {
    OptimizationNotReadyError: (
        OptimizationFailureClass.OPTIMIZATION_NOT_READY,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    OptimizationReviewRequiredError: (
        OptimizationFailureClass.OPTIMIZATION_REVIEW_REQUIRED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    OptimizationReadinessStaleError: (
        OptimizationFailureClass.OPTIMIZATION_READINESS_STALE,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    UnapprovedPlanError: (
        OptimizationFailureClass.UNAPPROVED_PLAN,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ActualsNotFixedBudgetError: (
        OptimizationFailureClass.ACTUALS_NOT_FIXED_BUDGET,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ClientBudgetArrayRejectedError: (
        OptimizationFailureClass.CLIENT_BUDGET_ARRAY_REJECTED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ModelArtifactUnavailableError: (
        OptimizationFailureClass.MODEL_ARTIFACT_UNAVAILABLE,
        OptimizationRetrySemantics.IDEMPOTENT_RETRY,
    ),
    NativeOptimizerFailedError: (
        OptimizationFailureClass.NATIVE_OPTIMIZER_FAILED,
        OptimizationRetrySemantics.NEW_RUN_REQUIRED,
    ),
    MeridianOptimizerApiReviewRequiredError: (
        OptimizationFailureClass.MERIDIAN_OPTIMIZER_API_REVIEW_REQUIRED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    OptimizerResultInvalidError: (
        OptimizationFailureClass.OPTIMIZER_RESULT_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    OptimizerBudgetInvariantFailedError: (
        OptimizationFailureClass.OPTIMIZER_BUDGET_INVARIANT_FAILED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ResultReadbackFailedError: (
        OptimizationFailureClass.RESULT_READBACK_FAILED,
        OptimizationRetrySemantics.NEW_RUN_REQUIRED,
    ),
    FlexibleBudgetNotImplementedError: (
        OptimizationFailureClass.FLEXIBLE_BUDGET_NOT_IMPLEMENTED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    FlexibleBudgetApiUnsupportedError: (
        OptimizationFailureClass.FLEXIBLE_BUDGET_API_UNSUPPORTED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ObjectiveNotSupportedError: (
        OptimizationFailureClass.OBJECTIVE_NOT_SUPPORTED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    FinancialValueAssumptionRequiredError: (
        OptimizationFailureClass.FINANCIAL_VALUE_ASSUMPTION_REQUIRED,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    FutureCostAssumptionInvalidError: (
        OptimizationFailureClass.FUTURE_COST_ASSUMPTION_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    FlightingAssumptionInvalidError: (
        OptimizationFailureClass.FLIGHTING_ASSUMPTION_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ConstraintSetInfeasibleError: (
        OptimizationFailureClass.CONSTRAINT_SET_INFEASIBLE,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ConstraintReferenceInvalidError: (
        OptimizationFailureClass.CONSTRAINT_REFERENCE_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ConstraintUnitMismatchError: (
        OptimizationFailureClass.CONSTRAINT_UNIT_MISMATCH,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    AdvancedReadinessStaleError: (
        OptimizationFailureClass.ADVANCED_READINESS_STALE,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ResultConstraintViolationError: (
        OptimizationFailureClass.RESULT_CONSTRAINT_VIOLATION,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    FunnelMappingRequiredError: (
        OptimizationFailureClass.CONSTRAINT_REFERENCE_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ProxyApprovalRequiredError: (
        OptimizationFailureClass.CONSTRAINT_REFERENCE_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    AssumptionSetNotFoundError: (
        OptimizationFailureClass.CONSTRAINT_REFERENCE_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
    ConstraintSetNotFoundError: (
        OptimizationFailureClass.CONSTRAINT_REFERENCE_INVALID,
        OptimizationRetrySemantics.NOT_RETRYABLE,
    ),
}


def _log(event: str, **ids: str) -> None:
    LOGGER.info("%s %s", event, " ".join(f"{key}={value}" for key, value in sorted(ids.items())))


def _classify(exc: Exception) -> tuple[OptimizationFailureClass, OptimizationRetrySemantics]:
    for exc_type, mapped in _FAILURE_MAP.items():
        if isinstance(exc, exc_type):
            return mapped
    return (
        OptimizationFailureClass.NATIVE_OPTIMIZER_FAILED,
        OptimizationRetrySemantics.NEW_RUN_REQUIRED,
    )


def _run_is_advanced(run: OptimizationRun) -> bool:
    if run.run_kind is OptimizationRunKind.FLEXIBLE_BUDGET:
        return True
    if run.constraint_set_id or run.assumption_set_id or run.advanced_readiness_receipt_id:
        return True
    if run.budget_mode is OptimizationBudgetMode.FLEXIBLE:
        return True
    if run.objective_mode not in {
        None,
        OptimizationObjectiveMode.MAX_EXPECTED_OUTCOME_FIXED_BUDGET,
    }:
        return True
    return False


def _parse_hurdle(hurdle: str | None) -> tuple[float | None, float | None]:
    if not hurdle:
        return None, None
    kind, _, value = hurdle.partition(":")
    if not value:
        return None, None
    parsed = float(value)
    if kind == "roi":
        return parsed, None
    if kind == "mroi":
        return None, parsed
    return None, None


def _format_hurdle(target_roi: float | None, target_mroi: float | None) -> str | None:
    if target_roi is not None:
        return f"roi:{target_roi}"
    if target_mroi is not None:
        return f"mroi:{target_mroi}"
    return None


class OptimizationRunService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        store: OptimizationMetadataStore,
        planning: InvestmentPlanService | None,
        models: AcceptedModelDirectory | None,
        consumption: ModelConsumptionSource | None,
        object_store: ObjectStore,
        artifact_bucket: str,
        optimizer: FixedBudgetOptimizer,
        execute_inline: bool = False,
    ) -> None:
        self._repo = repo
        self._store = store
        self._planning = planning
        self._models = models
        self._consumption = consumption
        self._object_store = object_store
        self._artifact_bucket = artifact_bucket
        self._optimizer = optimizer
        self._execute_inline = execute_inline

    def create_run(
        self,
        *,
        project_id: str,
        actor_id: str,
        readiness_receipt_id: str,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        budget_array: object | None = None,
        model_path: str | None = None,
        drive_path: str | None = None,
        variable_map: object | None = None,
        budget_mode: OptimizationBudgetMode | None = None,
        objective_mode: OptimizationObjectiveMode | None = None,
        constraint_set_id: str | None = None,
        assumption_set_id: str | None = None,
        advanced_readiness_receipt_id: str | None = None,
        target_roi: float | None = None,
        target_mroi: float | None = None,
    ) -> OptimizationRun:
        reject_client_budget_authority(
            tenant_id=tenant_id,
            budget_array=budget_array,
            model_path=model_path,
            drive_path=drive_path,
            variable_map=variable_map,
        )
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        require_human_approver(actor_id)
        if idempotency_key:
            existing = self._store.get_run_by_idempotency(
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                _log(
                    "optimization_run_idempotent",
                    optimization_run_id=existing.optimization_run_id,
                )
                return existing

        bundle = self._authorized_bundle(
            project_id=project_id,
            actor_id=actor_id,
            readiness_receipt_id=readiness_receipt_id,
        )
        advanced = self._resolve_advanced_inputs(
            project_id=project_id,
            bundle=bundle,
            budget_mode=budget_mode,
            objective_mode=objective_mode,
            constraint_set_id=constraint_set_id,
            assumption_set_id=assumption_set_id,
            advanced_readiness_receipt_id=advanced_readiness_receipt_id,
            target_roi=target_roi,
            target_mroi=target_mroi,
        )
        now = datetime.now(UTC)
        defaults = optimizer_defaults_fingerprint()
        if advanced is not None:
            defaults = advanced["defaults_fingerprint"]
        key = execution_key(
            receipt=bundle["receipt"],
            mapping=bundle["mapping"],
            input_contract=bundle["input_contract"],
            model_fingerprint=bundle["version"].model_plan_fingerprint or "",
            plan_version_fingerprint=bundle["snapshot"].fingerprint if bundle["snapshot"] else None,
            defaults=defaults,
        )
        run_kind = OptimizationRunKind.FIXED_BUDGET
        extra: dict[str, object] = {}
        if advanced is not None:
            run_kind = advanced["run_kind"]
            extra = {
                "constraint_set_id": advanced["constraint_set_id"],
                "constraint_set_fingerprint": advanced["constraint_set_fingerprint"],
                "assumption_set_id": advanced["assumption_set_id"],
                "assumption_set_fingerprint": advanced["assumption_set_fingerprint"],
                "objective_mode": advanced["objective_mode"],
                "objective_fingerprint": advanced["objective_fingerprint"],
                "budget_mode": advanced["budget_mode"],
                "target_hurdle": advanced["target_hurdle"],
                "advanced_readiness_receipt_id": advanced["advanced_readiness_receipt_id"],
                "advanced_readiness_fingerprint": advanced["advanced_readiness_fingerprint"],
            }
        run = OptimizationRun(
            optimization_run_id=new_optimization_run_id(),
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            run_kind=run_kind,
            status=OptimizationRunStatus.DISPATCHED,
            phase=OptimizationExecutionPhase.RESOLVE_BUDGET,
            readiness_receipt_id=readiness_receipt_id,
            optimization_input_id=bundle["input_contract"].optimization_input_id,
            plan_version_fingerprint=(
                None if bundle["snapshot"] is None else bundle["snapshot"].fingerprint
            ),
            mapping_id=bundle["mapping"].mapping_id,
            model_version_id=bundle["version"].model_version_id,
            portfolio_snapshot_id=(
                None if bundle["snapshot"] is None else bundle["snapshot"].snapshot_id
            ),
            readiness_fingerprint=bundle["receipt"].fingerprint,
            input_contract_fingerprint=bundle["input_contract"].fingerprint,
            mapping_fingerprint=bundle["mapping"].fingerprint,
            model_fingerprint=bundle["version"].model_plan_fingerprint,
            runtime_version=PINNED_MERIDIAN_RUNTIME,
            optimizer_defaults_fingerprint=defaults,
            execution_key=key,
            idempotency_key=idempotency_key,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            **extra,
        )
        stored = self._store.put(run)
        assert isinstance(stored, OptimizationRun)
        _log(
            "optimization_run_dispatched",
            optimization_run_id=stored.optimization_run_id,
            readiness_receipt_id=readiness_receipt_id,
        )
        if self._execute_inline:
            return self.execute_run(
                optimization_run_id=stored.optimization_run_id, actor_id=actor_id
            )
        return stored

    def execute_run(
        self, *, optimization_run_id: str, actor_id: str | None = None
    ) -> OptimizationRun:
        del actor_id
        run = self._store.get_run(optimization_run_id)
        if run is None:
            raise OptimizationRunNotFoundError("Optimization run was not found.")
        if run.status is OptimizationRunStatus.COMPLETE:
            return run
        try:
            return self._execute(run)
        except Exception as exc:
            failed = self._fail(run, exc)
            if isinstance(exc, OptimizationError):
                return failed
            raise

    def get_run(self, *, optimization_run_id: str, project_id: str) -> OptimizationRun:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        run = self._store.get_run(optimization_run_id)
        if run is None:
            raise OptimizationRunNotFoundError("Optimization run was not found.")
        if run.tenant_id != tenant.tenant_id:
            raise CrossTenantRunAccessError(
                "Cross-tenant optimization run access is not allowed."
            )
        if run.project_id != project_id:
            raise CrossProjectRunAccessError(
                "Cross-project optimization run access is not allowed."
            )
        return run

    def list_runs(self, *, project_id: str) -> tuple[OptimizationRun, ...]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_runs(tenant_id=tenant.tenant_id, project_id=project_id)

    def get_result(self, *, optimization_run_id: str, project_id: str) -> OptimizationResultPayload:
        run = self.get_run(optimization_run_id=optimization_run_id, project_id=project_id)
        if run.status is not OptimizationRunStatus.COMPLETE or not run.artifact_object_name:
            raise ResultReadbackFailedError("Optimization result requires a verified artifact.")
        ref = self._store.get_result_ref_for_run(optimization_run_id)
        if ref is None:
            raise ResultReadbackFailedError("Optimization result metadata was not found.")
        expected_keys = self._expected_keys(run)
        return read_back_result(
            store=self._object_store,
            bucket=ref.artifact_bucket,
            object_name=ref.artifact_object_name,
            expected_fingerprint=ref.result_fingerprint,
            expected_keys=expected_keys,
        )

    def _expected_keys(self, run: OptimizationRun) -> set[str]:
        if run.mapping_id is None or run.optimization_input_id is None:
            raise ResultReadbackFailedError("Optimization run is missing mapping identity.")
        mapping = self._store.get_mapping(run.mapping_id)
        input_contract = self._store.get_input_contract(run.optimization_input_id)
        if mapping is None or input_contract is None:
            raise ResultReadbackFailedError("Optimization mapping is unavailable for read-back.")
        excluded = set(input_contract.excluded_variable_ids)
        return {
            entry.model_variable_id
            for entry in mapping.mapping_entries
            if entry.model_variable_id not in excluded
        }

    def _authorized_bundle(
        self,
        *,
        project_id: str,
        actor_id: str,
        readiness_receipt_id: str,
        enforce_tenant: bool = True,
    ) -> dict[str, object]:
        tenant = require_tenant()
        receipt = self._store.get_receipt(readiness_receipt_id)
        if receipt is None:
            raise OptimizationNotReadyError("Optimization readiness receipt was not found.")
        if enforce_tenant and receipt.tenant_id != tenant.tenant_id:
            raise CrossTenantRunAccessError(
                "Cross-tenant optimization run access is not allowed."
            )
        if receipt.project_id != project_id:
            raise CrossProjectRunAccessError(
                "Cross-project optimization run access is not allowed."
            )
        snapshot = None
        view = None
        plan_status = getattr(self._planning, "plan_status", InvestmentPlanStatus.APPROVED.value)
        if self._planning is not None and hasattr(self._planning, "assemble_portfolio"):
            _state, snapshot, view = self._planning.assemble_portfolio(
                project_id=project_id,
                fiscal_year=None,
                actor_id=actor_id,
            )
            if (
                snapshot is not None
                and snapshot.investment_plan_id
                and hasattr(self._planning, "_store")
            ):
                plan = self._planning._store.get_plan(snapshot.investment_plan_id)
                if plan is not None:
                    plan_status = plan.status.value
        mapping = (
            None if receipt.mapping_id is None else self._store.get_mapping(receipt.mapping_id)
        )
        input_contract = (
            None
            if receipt.optimization_input_id is None
            else self._store.get_input_contract(receipt.optimization_input_id)
        )
        version = None
        contract = None
        if self._models is not None:
            versions = self._models.list_versions(tenant_id=tenant.tenant_id, project_id=project_id)
            selection = select_accepted_model(
                versions,
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                requested_model_version_id=receipt.model_version_id,
            )
            version = selection.version
        if (
            version is not None
            and self._consumption is not None
        ):
            contract = self._consumption.get_contract(
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                model_version_id=version.model_version_id,
            )
        if contract is None and version is not None:
            contract = self._store.get_consumption_for_model(
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                model_version_id=version.model_version_id,
            )
        rebound = revalidate_for_dispatch(
            receipt=receipt,
            snapshot=snapshot,
            mapping=mapping,
            input_contract=input_contract,
            contract=contract,
            version=version,
        )
        assert mapping is not None
        assert input_contract is not None
        assert version is not None
        vector = resolve_optimizer_budget(
            view=view,
            mapping=mapping,
            input_contract=input_contract,
            plan_status=plan_status,
        )
        return {
            "receipt": receipt,
            "snapshot": snapshot,
            "view": view,
            "mapping": mapping,
            "input_contract": input_contract,
            "contract": rebound,
            "version": version,
            "vector": vector,
        }

    def _execute(self, run: OptimizationRun) -> OptimizationRun:
        now = datetime.now(UTC)
        running = run.model_copy(
            update={
                "status": OptimizationRunStatus.RUNNING,
                "phase": OptimizationExecutionPhase.LOAD_MODEL,
                "updated_at": now,
            }
        )
        self._store.put(running)
        bundle = self._authorized_bundle(
            project_id=run.project_id,
            actor_id=run.created_by,
            readiness_receipt_id=run.readiness_receipt_id,
        )
        vector = bundle["vector"]
        assert isinstance(vector, OptimizerBudgetVector)
        contract = bundle["contract"]
        input_contract = bundle["input_contract"]
        artifact_ref = contract.optimizer_artifact_ref
        if not artifact_ref:
            raise ModelArtifactUnavailableError("Accepted model optimizer artifact is unavailable.")
        if _run_is_advanced(run):
            return self._execute_advanced(
                run,
                running=running,
                bundle=bundle,
                vector=vector,
                artifact_ref=artifact_ref,
            )
        raw = self._optimizer.optimize_fixed_budget(
            model_artifact_ref=artifact_ref,
            vector=vector,
            object_store=self._object_store,
            artifact_bucket=self._artifact_bucket,
        )
        validating = running.model_copy(
            update={
                "status": OptimizationRunStatus.VALIDATING,
                "phase": OptimizationExecutionPhase.VALIDATE,
                "updated_at": datetime.now(UTC),
            }
        )
        self._store.put(validating)
        validate_raw_result(vector=vector, input_contract=input_contract, raw=raw)
        rows = reconcile_recommended_spends(vector=vector, raw=raw)
        validate_reconciled_rows(
            vector=vector,
            input_contract=input_contract,
            rows=rows,
            fixed_budget=vector.fixed_budget,
        )
        result_id = new_optimization_result_id()
        payload = OptimizationResultPayload(
            optimization_run_id=run.optimization_run_id,
            result_id=result_id,
            amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
            currency=vector.currency,
            fixed_budget=vector.fixed_budget,
            recommended_total=recommended_total(rows),
            rows=rows,
            fingerprint="",
            schema_version=ARTIFACT_SCHEMA_VERSION,
        )
        fingerprint = result_fingerprint(payload)
        payload = payload.model_copy(update={"fingerprint": fingerprint})
        persisting = validating.model_copy(
            update={
                "phase": OptimizationExecutionPhase.PERSIST,
                "updated_at": datetime.now(UTC),
            }
        )
        self._store.put(persisting)
        object_name, generation = write_result_artifact(
            store=self._object_store,
            bucket=self._artifact_bucket,
            payload=payload,
        )
        reading = persisting.model_copy(
            update={
                "status": OptimizationRunStatus.READBACK,
                "phase": OptimizationExecutionPhase.READBACK,
                "artifact_object_name": object_name,
                "artifact_generation": generation,
                "result_id": result_id,
                "result_fingerprint": fingerprint,
                "updated_at": datetime.now(UTC),
            }
        )
        self._store.put(reading)
        expected_keys = {
            row.model_variable_id
            for row in rows
            if row.eligibility
            in {
                ModelVariableOptimizationEligibility.OPTIMIZABLE,
                ModelVariableOptimizationEligibility.FIXED,
            }
        }
        verified = read_back_result(
            store=self._object_store,
            bucket=self._artifact_bucket,
            object_name=object_name,
            expected_fingerprint=fingerprint,
            expected_keys=expected_keys,
            expected_total=vector.fixed_budget,
        )
        del verified
        completed_at = datetime.now(UTC)
        ref = OptimizationResultRef(
            result_id=result_id,
            optimization_run_id=run.optimization_run_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            artifact_bucket=self._artifact_bucket,
            artifact_object_name=object_name,
            artifact_generation=generation,
            result_fingerprint=fingerprint,
            schema_version=ARTIFACT_SCHEMA_VERSION,
            runtime_version=PINNED_MERIDIAN_RUNTIME,
            is_current=True,
            created_at=completed_at,
        )
        self._store.put(ref)
        complete = reading.model_copy(
            update={
                "status": OptimizationRunStatus.COMPLETE,
                "phase": OptimizationExecutionPhase.READBACK,
                "updated_at": completed_at,
                "completed_at": completed_at,
            }
        )
        stored = self._store.put(complete)
        assert isinstance(stored, OptimizationRun)
        _log("optimization_run_complete", optimization_run_id=stored.optimization_run_id)
        return stored

    def _resolve_advanced_inputs(
        self,
        *,
        project_id: str,
        bundle: dict[str, object],
        budget_mode: OptimizationBudgetMode | None,
        objective_mode: OptimizationObjectiveMode | None,
        constraint_set_id: str | None,
        assumption_set_id: str | None,
        advanced_readiness_receipt_id: str | None,
        target_roi: float | None,
        target_mroi: float | None,
    ) -> dict[str, object] | None:
        requested = any(
            (
                budget_mode is OptimizationBudgetMode.FLEXIBLE,
                objective_mode
                not in {None, OptimizationObjectiveMode.MAX_EXPECTED_OUTCOME_FIXED_BUDGET},
                constraint_set_id,
                assumption_set_id,
                advanced_readiness_receipt_id,
                target_roi is not None,
                target_mroi is not None,
            )
        )
        if not requested:
            return None
        vector = bundle["vector"]
        assert isinstance(vector, OptimizerBudgetVector)
        advanced_receipt = None
        if advanced_readiness_receipt_id:
            advanced_receipt = self._store.get_advanced_receipt(advanced_readiness_receipt_id)
            if advanced_receipt is None:
                raise OptimizationNotReadyError(
                    "Advanced optimization readiness receipt was not found."
                )
            require_advanced_ready(advanced_receipt)
            constraint_set_id = constraint_set_id or advanced_receipt.constraint_set_id
            assumption_set_id = assumption_set_id or advanced_receipt.assumption_set_id
            objective_mode = objective_mode or advanced_receipt.objective_mode
            budget_mode = budget_mode or advanced_receipt.budget_mode
            if target_roi is None and target_mroi is None:
                target_roi, target_mroi = _parse_hurdle(advanced_receipt.target_hurdle)
        mode = objective_mode or OptimizationObjectiveMode.MAX_EXPECTED_OUTCOME_FIXED_BUDGET
        resolved_budget_mode = budget_mode or budget_mode_for(mode)
        assumptions = self._load_assumptions(assumption_set_id, project_id=project_id)
        constraints = self._load_constraints(constraint_set_id, project_id=project_id)
        validate_objective(
            mode=mode, assumptions=assumptions, target_roi=target_roi, target_mroi=target_mroi
        )
        lines = vector.lines
        if constraints is not None:
            lines = apply_unsupported_policies(lines=lines, constraint_set=constraints)
            prove_feasible(constraints, lines=lines)
        use_kpi = use_kpi_for(mode=mode, assumptions=assumptions)
        spec = compile_native_spec(
            vector=vector.model_copy(update={"lines": lines}),
            mode=mode,
            budget_mode=resolved_budget_mode,
            constraint_set=constraints,
            assumptions=assumptions,
            target_roi=target_roi,
            target_mroi=target_mroi,
            use_kpi=use_kpi,
        )
        obj_fp = objective_fingerprint(
            mode=mode, target_roi=target_roi, target_mroi=target_mroi, use_kpi=use_kpi
        )
        assumption_fp = None if assumptions is None else assumption_fingerprint(assumptions)
        constraint_fp = None if constraints is None else constraint_set_fingerprint(constraints)
        defaults = advanced_optimizer_defaults_fingerprint(
            spec_fingerprint=spec.fingerprint,
            budget_mode=resolved_budget_mode.value,
            objective_fingerprint=obj_fp,
            assumption_fingerprint=assumption_fp or "",
            constraint_fingerprint=constraint_fp or "",
        )
        if advanced_receipt is not None:
            if advanced_receipt_is_stale(
                advanced_receipt,
                base=bundle["receipt"],
                assumption_fingerprint=assumption_fp,
                constraint_fingerprint=constraint_fp,
                objective_fingerprint=obj_fp,
                optimizer_defaults_fingerprint=optimizer_defaults_fingerprint(),
            ):
                raise AdvancedReadinessStaleError("Advanced optimization readiness is stale.")
        return {
            "run_kind": run_kind_for(mode),
            "objective_mode": mode,
            "objective_fingerprint": obj_fp,
            "budget_mode": resolved_budget_mode,
            "target_hurdle": _format_hurdle(target_roi, target_mroi),
            "constraint_set_id": None if constraints is None else constraints.constraint_set_id,
            "constraint_set_fingerprint": constraint_fp,
            "assumption_set_id": None if assumptions is None else assumptions.assumption_set_id,
            "assumption_set_fingerprint": assumption_fp,
            "advanced_readiness_receipt_id": (
                None if advanced_receipt is None else advanced_receipt.receipt_id
            ),
            "advanced_readiness_fingerprint": (
                None if advanced_receipt is None else advanced_receipt.fingerprint
            ),
            "defaults_fingerprint": defaults,
        }

    def _load_assumptions(
        self, assumption_set_id: str | None, *, project_id: str
    ) -> FutureScenarioAssumptions | None:
        if not assumption_set_id:
            return None
        ref = self._store.get_assumption_ref(assumption_set_id)
        if ref is None or ref.project_id not in {None, project_id}:
            raise AssumptionSetNotFoundError("Assumption set was not found.")
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

    def _load_constraints(
        self, constraint_set_id: str | None, *, project_id: str
    ) -> OptimizationConstraintSet | None:
        if not constraint_set_id:
            return None
        ref = self._store.get_constraint_ref(constraint_set_id)
        if ref is None or ref.project_id not in {None, project_id}:
            raise ConstraintSetNotFoundError("Constraint set was not found.")
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

    def _execute_advanced(
        self,
        run: OptimizationRun,
        *,
        running: OptimizationRun,
        bundle: dict[str, object],
        vector: OptimizerBudgetVector,
        artifact_ref: str,
    ) -> OptimizationRun:
        input_contract = bundle["input_contract"]
        assumptions = self._load_assumptions(run.assumption_set_id, project_id=run.project_id)
        constraints = self._load_constraints(run.constraint_set_id, project_id=run.project_id)
        mode = run.objective_mode or OptimizationObjectiveMode.MAX_EXPECTED_OUTCOME_FIXED_BUDGET
        budget_mode = run.budget_mode or budget_mode_for(mode)
        target_roi, target_mroi = _parse_hurdle(run.target_hurdle)
        lines = vector.lines
        if constraints is not None:
            lines = apply_unsupported_policies(lines=lines, constraint_set=constraints)
            prove_feasible(constraints, lines=lines)
        working = vector.model_copy(update={"lines": lines})
        use_kpi = use_kpi_for(mode=mode, assumptions=assumptions)
        validate_objective(
            mode=mode, assumptions=assumptions, target_roi=target_roi, target_mroi=target_mroi
        )
        spec = compile_native_spec(
            vector=working,
            mode=mode,
            budget_mode=budget_mode,
            constraint_set=constraints,
            assumptions=assumptions,
            target_roi=target_roi,
            target_mroi=target_mroi,
            use_kpi=use_kpi,
        )
        optimize_flexible = getattr(self._optimizer, "optimize_flexible_budget", None)
        if optimize_flexible is None:
            if budget_mode is OptimizationBudgetMode.FIXED:
                raw = self._optimizer.optimize_fixed_budget(
                    model_artifact_ref=artifact_ref,
                    vector=working,
                    object_store=self._object_store,
                    artifact_bucket=self._artifact_bucket,
                )
            else:
                raise FlexibleBudgetNotImplementedError(
                    "Flexible-budget optimization requires optimize_flexible_budget."
                )
        else:
            raw = optimize_flexible(
                model_artifact_ref=artifact_ref,
                vector=working,
                spec=spec,
                object_store=self._object_store,
                artifact_bucket=self._artifact_bucket,
            )
        validating = running.model_copy(
            update={
                "status": OptimizationRunStatus.VALIDATING,
                "phase": OptimizationExecutionPhase.VALIDATE,
                "updated_at": datetime.now(UTC),
            }
        )
        self._store.put(validating)
        validate_raw_result(vector=working, input_contract=input_contract, raw=raw)
        flexible = budget_mode is OptimizationBudgetMode.FLEXIBLE
        if flexible:
            rows = reconcile_flexible_spends(vector=working, raw=raw)
        else:
            rows = reconcile_recommended_spends(vector=working, raw=raw)
        min_total = None
        max_total = None
        if constraints is not None and constraints.total_budget_bounds is not None:
            min_total = constraints.total_budget_bounds.lower
            max_total = constraints.total_budget_bounds.upper
        validate_reconciled_rows(
            vector=working,
            input_contract=input_contract,
            rows=rows,
            fixed_budget=working.fixed_budget,
            min_total=min_total,
            max_total=max_total,
            require_fixed_total=not flexible,
        )
        bindings = ()
        if constraints is not None:
            bindings = validate_constraint_result(constraint_set=constraints, rows=rows)
        result_id = new_optimization_result_id()
        rec_total = recommended_total(rows)
        payload = OptimizationResultPayload(
            optimization_run_id=run.optimization_run_id,
            result_id=result_id,
            run_kind=run.run_kind,
            amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
            currency=working.currency,
            fixed_budget=working.fixed_budget,
            recommended_total=rec_total,
            total_baseline_spend=working.fixed_budget,
            objective_mode=mode,
            budget_mode=budget_mode,
            target_hurdle=run.target_hurdle,
            assumption_set_id=run.assumption_set_id,
            assumption_set_fingerprint=run.assumption_set_fingerprint,
            constraint_set_id=run.constraint_set_id,
            constraint_set_fingerprint=run.constraint_set_fingerprint,
            binding_constraints=bindings,
            rows=rows,
            fingerprint="",
            schema_version=ADVANCED_ARTIFACT_SCHEMA_VERSION,
        )
        fingerprint = result_fingerprint(payload)
        payload = payload.model_copy(update={"fingerprint": fingerprint})
        persisting = validating.model_copy(
            update={
                "phase": OptimizationExecutionPhase.PERSIST,
                "updated_at": datetime.now(UTC),
            }
        )
        self._store.put(persisting)
        object_name, generation = write_result_artifact(
            store=self._object_store,
            bucket=self._artifact_bucket,
            payload=payload,
        )
        reading = persisting.model_copy(
            update={
                "status": OptimizationRunStatus.READBACK,
                "phase": OptimizationExecutionPhase.READBACK,
                "artifact_object_name": object_name,
                "artifact_generation": generation,
                "result_id": result_id,
                "result_fingerprint": fingerprint,
                "updated_at": datetime.now(UTC),
            }
        )
        self._store.put(reading)
        expected_keys = {
            row.model_variable_id
            for row in rows
            if row.eligibility
            in {
                ModelVariableOptimizationEligibility.OPTIMIZABLE,
                ModelVariableOptimizationEligibility.FIXED,
            }
        }
        verified = read_back_result(
            store=self._object_store,
            bucket=self._artifact_bucket,
            object_name=object_name,
            expected_fingerprint=fingerprint,
            expected_keys=expected_keys,
            expected_total=None if flexible else working.fixed_budget,
        )
        del verified
        completed_at = datetime.now(UTC)
        ref = OptimizationResultRef(
            result_id=result_id,
            optimization_run_id=run.optimization_run_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            artifact_bucket=self._artifact_bucket,
            artifact_object_name=object_name,
            artifact_generation=generation,
            result_fingerprint=fingerprint,
            schema_version=ADVANCED_ARTIFACT_SCHEMA_VERSION,
            runtime_version=PINNED_MERIDIAN_RUNTIME,
            is_current=True,
            created_at=completed_at,
        )
        self._store.put(ref)
        complete = reading.model_copy(
            update={
                "status": OptimizationRunStatus.COMPLETE,
                "phase": OptimizationExecutionPhase.READBACK,
                "updated_at": completed_at,
                "completed_at": completed_at,
            }
        )
        stored = self._store.put(complete)
        assert isinstance(stored, OptimizationRun)
        _log("optimization_run_complete", optimization_run_id=stored.optimization_run_id)
        return stored

    def _fail(self, run: OptimizationRun, exc: Exception) -> OptimizationRun:
        failure_class, retry = _classify(exc)
        status = (
            OptimizationRunStatus.STALE_REFUSED
            if failure_class is OptimizationFailureClass.OPTIMIZATION_READINESS_STALE
            else OptimizationRunStatus.FAILED
        )
        failed = run.model_copy(
            update={
                "status": status,
                "failure_class": failure_class,
                "failure_stage": run.phase,
                "retry_semantics": retry,
                "updated_at": datetime.now(UTC),
            }
        )
        stored = self._store.put(failed)
        assert isinstance(stored, OptimizationRun)
        _log(
            "optimization_run_failed",
            optimization_run_id=stored.optimization_run_id,
            failure_class=failure_class.value,
        )
        return stored

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
from app.investment_optimization.artifact import (
    read_back_result,
    result_fingerprint,
    write_result_artifact,
)
from app.investment_optimization.budget_resolve import (
    reject_client_budget_authority,
    resolve_optimizer_budget,
)
from app.investment_optimization.consumption import ModelConsumptionSource
from app.investment_optimization.contracts import (
    OptimizationResultPayload,
    OptimizationResultRef,
    OptimizationRun,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import (
    ARTIFACT_SCHEMA_VERSION,
    PINNED_MERIDIAN_RUNTIME,
    ModelVariableOptimizationEligibility,
    OptimizationAmountKind,
    OptimizationExecutionPhase,
    OptimizationFailureClass,
    OptimizationRetrySemantics,
    OptimizationRunKind,
    OptimizationRunStatus,
)
from app.investment_optimization.errors import (
    ActualsNotFixedBudgetError,
    ClientBudgetArrayRejectedError,
    CrossProjectRunAccessError,
    CrossTenantRunAccessError,
    FlexibleBudgetNotImplementedError,
    MeridianOptimizerApiReviewRequiredError,
    ModelArtifactUnavailableError,
    NativeOptimizerFailedError,
    OptimizationError,
    OptimizationNotReadyError,
    OptimizationReadinessStaleError,
    OptimizationReviewRequiredError,
    OptimizationRunNotFoundError,
    OptimizerBudgetInvariantFailedError,
    OptimizerResultInvalidError,
    ResultReadbackFailedError,
    UnapprovedPlanError,
)
from app.investment_optimization.execution import (
    execution_key,
    optimizer_defaults_fingerprint,
    revalidate_for_dispatch,
)
from app.investment_optimization.ids import new_optimization_result_id, new_optimization_run_id
from app.investment_optimization.numeric import recommended_total, reconcile_recommended_spends
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_optimization.validate_result import (
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
        now = datetime.now(UTC)
        key = execution_key(
            receipt=bundle["receipt"],
            mapping=bundle["mapping"],
            input_contract=bundle["input_contract"],
            model_fingerprint=bundle["version"].model_plan_fingerprint or "",
            plan_version_fingerprint=bundle["snapshot"].fingerprint if bundle["snapshot"] else None,
        )
        run = OptimizationRun(
            optimization_run_id=new_optimization_run_id(),
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            run_kind=OptimizationRunKind.FIXED_BUDGET,
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
            optimizer_defaults_fingerprint=optimizer_defaults_fingerprint(),
            execution_key=key,
            idempotency_key=idempotency_key,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
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

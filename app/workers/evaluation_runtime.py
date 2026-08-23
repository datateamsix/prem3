"""Evaluation worker runtime. Requires a server-owned dispatch, never CLI authority."""

from __future__ import annotations

import os
from collections.abc import Callable

from app.control_plane.dispatch_claims import (
    DispatchClaimOutcome,
    mark_failed,
    mark_succeeded,
    utc_now,
)
from app.control_plane.models import Feature, UploadStatus
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import AuthorityMismatchError, SafetyViolationError
from app.core.tenancy import AuthState, TenantContext, WorkspaceContext, bind_tenant, bind_workspace
from app.service.evaluation_executor import EvaluationExecutor
from app.service.evaluation_jobs import execution_id_from_resource
from app.service.security_log import security_log

RETRYABLE_ERROR_CODES = frozenset(
    {
        "FIRESTORE_UNAVAILABLE",
        "GCS_UNAVAILABLE",
        "PROVIDER_UNAVAILABLE",
        "EDA_LAUNCH_TRANSIENT",
    }
)


class EvaluationWorkerError(Exception):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def claim_owner_from_env(env: dict[str, str] | None = None) -> tuple[str, str]:
    source = env if env is not None else os.environ
    execution = execution_id_from_resource(
        source.get("CLOUD_RUN_EXECUTION") or "local-evaluation"
    )
    attempt = (source.get("CLOUD_RUN_TASK_ATTEMPT") or "0").strip()
    return execution, f"{execution}:{attempt}"


def execute_claimed_dispatch(
    *,
    repo: ControlPlaneRepository,
    executor: EvaluationExecutor,
    dispatch_id: str,
    owner: str,
    execution_name: str,
    run_async: Callable,
) -> int:
    """Claim, authorize, invoke EvaluationExecutor. Return process exit code."""
    now = utc_now()
    outcome, dispatch = repo.claim_evaluation_dispatch(
        dispatch_id=dispatch_id,
        owner=owner,
        execution_name=execution_name,
        now=now,
    )
    if dispatch is None or outcome == "not_found":
        security_log("evaluation.worker_missing_dispatch", dispatch_id=dispatch_id)
        return 0
    if outcome == DispatchClaimOutcome.DENIED.value:
        security_log(
            "evaluation.worker_duplicate_denied",
            dispatch_id=dispatch_id,
            execution=execution_name,
        )
        return 0
    if outcome == DispatchClaimOutcome.ALREADY_TERMINAL.value:
        security_log("evaluation.worker_already_terminal", dispatch_id=dispatch_id)
        return 0
    try:
        _authorize_and_execute(
            repo=repo,
            executor=executor,
            dispatch_id=dispatch_id,
            run_async=run_async,
        )
    except EvaluationWorkerError as exc:
        failed = mark_failed(
            dispatch, now=utc_now(), retryable=exc.retryable, error_code=exc.code
        )
        repo.put_evaluation_dispatch(failed)
        security_log(
            "evaluation.worker_failed",
            dispatch_id=dispatch_id,
            run_id=dispatch.run_id,
            error_code=exc.code,
        )
        return 1 if exc.retryable else 0
    except Exception:
        failed = mark_failed(
            dispatch,
            now=utc_now(),
            retryable=True,
            error_code="PROVIDER_UNAVAILABLE",
        )
        repo.put_evaluation_dispatch(failed)
        security_log("evaluation.worker_retryable", dispatch_id=dispatch_id)
        return 1
    succeeded = mark_succeeded(dispatch, now=utc_now())
    repo.put_evaluation_dispatch(succeeded)
    security_log(
        "evaluation.worker_succeeded",
        dispatch_id=dispatch_id,
        run_id=dispatch.run_id,
        execution=execution_name,
    )
    return 0


def _authorize_and_execute(
    *,
    repo: ControlPlaneRepository,
    executor: EvaluationExecutor,
    dispatch_id: str,
    run_async: Callable,
) -> None:
    dispatch = repo.get_evaluation_dispatch(dispatch_id)
    if dispatch is None:
        raise EvaluationWorkerError("EVALUATION_MISSING", retryable=False)
    evaluation = repo.get_evaluation_ref(tenant_id=dispatch.tenant_id, run_id=dispatch.run_id)
    if evaluation is None:
        raise EvaluationWorkerError("EVALUATION_MISSING", retryable=False)
    if (
        dispatch.tenant_id != evaluation.tenant_id
        or dispatch.workspace_id != evaluation.workspace_id
        or dispatch.dataset_id != evaluation.dataset_id
        or dispatch.run_id != evaluation.run_id
    ):
        raise EvaluationWorkerError("DISPATCH_EVALUATION_MISMATCH", retryable=False)
    snapshot = repo.get_entitlement_snapshot(
        tenant_id=evaluation.tenant_id,
        snapshot_id=evaluation.entitlement_snapshot_id,
    )
    if snapshot is None or snapshot.tenant_id != evaluation.tenant_id:
        raise EvaluationWorkerError("ENTITLEMENT_SNAPSHOT_MISSING", retryable=False)
    if Feature.DATASET_ASSESSMENT not in snapshot.features:
        raise EvaluationWorkerError("ENTITLEMENT_SNAPSHOT_DENIED", retryable=False)
    upload = repo.get_upload(
        tenant_id=evaluation.tenant_id,
        workspace_id=evaluation.workspace_id,
        dataset_id=evaluation.dataset_id,
        upload_id=evaluation.upload_id,
    )
    if upload is None or upload.status is not UploadStatus.VERIFIED:
        raise EvaluationWorkerError("EVALUATION_UPLOAD_MISSING", retryable=False)
    if upload.package_uri != evaluation.package_uri:
        raise EvaluationWorkerError("PACKAGE_FINGERPRINT_MISMATCH", retryable=False)
    if (
        evaluation.package_fingerprint is not None
        and upload.package_fingerprint != evaluation.package_fingerprint
    ):
        raise EvaluationWorkerError("PACKAGE_FINGERPRINT_MISMATCH", retryable=False)
    tenant = TenantContext(
        tenant_id=dispatch.tenant_id,
        user_id=None,
        auth_state=AuthState.SERVICE,
        entitlement_snapshot_id=evaluation.entitlement_snapshot_id,
    )
    workspace = WorkspaceContext(
        workspace_id=dispatch.workspace_id,
        dataset_id=dispatch.dataset_id,
    )
    try:
        with bind_tenant(tenant), bind_workspace(workspace):
            run_async(executor.execute_evaluation(evaluation.run_id))
    except (AuthorityMismatchError, SafetyViolationError, LookupError):
        raise EvaluationWorkerError("EVALUATION_AUTHORITY_INVALID", retryable=False) from None

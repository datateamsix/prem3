"""Cloud Run Job entrypoint for approved Meridian posterior sampling.

This process is the only production runtime that should fit google-meridian.
It restores server-owned Tenant/Project/Cycle/Track/ModelVersion/FitPlan from
durable dispatch state. It never executes generated Python and never accepts
tenant, storage path, image, or service-account authority from an agent payload.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any

from app.modeling.common.errors import FitRuntimeError
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitRunStatus,
    MeridianRuntimeMode,
)
from app.modeling.mmm.meridian.runner import (
    OfficialMeridianRuntime,
    execute_approved_fit,
)
from app.modeling.mmm.repository import ModelingRepository
from app.modeling.mmm.service import MMMModelingService

FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "python",
        "script",
        "generated_python",
        "container_image",
        "service_account",
        "cloud_run_job_name",
        "destination_override",
        "storage_path",
        "gpu",
        "cpu",
        "memory",
        "region",
        "image_digest",
    }
)


def _reject_untrusted(request: dict[str, Any]) -> None:
    unexpected = FORBIDDEN_REQUEST_KEYS.intersection(request)
    if unexpected:
        raise FitRuntimeError(
            f"Worker rejected untrusted authority keys: {sorted(unexpected)}"
        )


def execute_server_owned_request(request: dict[str, Any]) -> dict[str, Any]:
    """Legacy JSON path used only to prove untrusted keys are rejected."""
    _reject_untrusted(request)
    raise FitRuntimeError(
        "Worker reconstructs authority from durable dispatch_id; request JSON is not authority."
    )


def execute_fit_dispatch(
    *,
    dispatch_id: str,
    repo: ModelingRepository,
    runtime: OfficialMeridianRuntime | None = None,
    service: MMMModelingService | None = None,
) -> dict[str, Any]:
    dispatch = repo.get_dispatch(dispatch_id)
    if dispatch is None:
        raise FitRuntimeError("Fit dispatch was not found.")
    plan = repo.get_plan(dispatch.model_version_id)
    fit_plan = repo.get_fit_plan(dispatch.model_version_id)
    if plan is None or fit_plan is None:
        raise FitRuntimeError("Worker could not restore the approved FitPlan.")
    if fit_plan.fingerprint != dispatch.fit_plan_fingerprint:
        raise FitRuntimeError("Worker rejected a mismatched FitPlan fingerprint.")
    run = repo.get_fit_run(
        tenant_id=dispatch.tenant_id,
        project_id=dispatch.project_id,
        fit_run_id=dispatch.fit_run_id,
    )
    if run is not None and run.status is FitRunStatus.SUCCEEDED:
        return {
            "status": "SUCCEEDED",
            "dispatch_id": dispatch_id,
            "fit_run_id": run.fit_run_id,
            "skipped": "already COMPLETE",
        }
    if run is not None and run.status is FitRunStatus.RUNNING and run.attempt > 0:
        if dispatch.cloud_run_execution_name:
            return {
                "status": "RUNNING",
                "dispatch_id": dispatch_id,
                "fit_run_id": run.fit_run_id,
                "skipped": "active identical execution",
            }
    mode = dispatch.runtime_mode
    if mode is MeridianRuntimeMode.FAKE_TEST:
        raise FitRuntimeError("Worker refuses FAKE_TEST.")
    if dispatch.compute_profile is ComputeProfile.CPU_TEST:
        mode = MeridianRuntimeMode.OFFICIAL_CPU_SMOKE
    owned = runtime or OfficialMeridianRuntime(mode=mode)
    result = execute_approved_fit(
        owned,
        plan,
        fit_plan,
        expected_input_fingerprint=plan.model_ready_manifest_fingerprint,
    )
    if service is not None:
        version = service.get_version(
            tenant_id=dispatch.tenant_id,
            project_id=dispatch.project_id,
            model_version_id=dispatch.model_version_id,
        )
        service._execute_fit(version, plan, fit_plan, run)
    return {
        "status": "SUCCEEDED",
        "tenant_id": dispatch.tenant_id,
        "project_id": dispatch.project_id,
        "cycle_id": dispatch.cycle_id,
        "track_id": dispatch.track_id,
        "model_version_id": dispatch.model_version_id,
        "fit_run_id": dispatch.fit_run_id,
        "dispatch_id": dispatch_id,
        "binary_sha256": result.binary_sha256,
        "python_version": result.python_version,
        "meridian_version": result.meridian_version,
        "tensorflow_version": result.tensorflow_version,
        "worker_image_digest": result.worker_image_digest,
        "runtime_mode": result.runtime_mode.value,
        "review_source": result.review_source.value,
        "calls_made": list(result.calls_made),
        "health_checks": [item.model_dump(mode="json") for item in result.health_checks],
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print(
            "usage: PREM3_MMM_FIT_DISPATCH_ID=<dispatch_id> "
            "python -m app.tools.meridian_model_worker\n"
            "Cloud Run Job entrypoint for approved Meridian posterior sampling.\n"
            "Forbidden: generated Python, agent-supplied tenant, storage path, "
            "container image, or service account."
        )
        return 0
    dispatch_id = (os.environ.get("PREM3_MMM_FIT_DISPATCH_ID") or "").strip()
    if not dispatch_id:
        print("PREM3_MMM_FIT_DISPATCH_ID is required", file=sys.stderr)
        return 2
    try:
        raise FitRuntimeError(
            "Worker process requires the production Firestore modeling repository."
        )
    except Exception as exc:
        failure = {"status": "FAILED", "error": str(exc), "traceback": traceback.format_exc()}
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

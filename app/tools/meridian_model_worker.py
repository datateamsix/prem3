"""Cloud Run Job entrypoint for approved Meridian posterior sampling.

This process is the only production runtime that should fit google-meridian.
It restores server-owned Tenant/Project/Cycle/Track/ModelVersion/FitPlan from
a durable request written by prem3-api. It never executes generated Python and
never accepts tenant, storage path, image, or service-account authority from
an agent or user payload.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from app.modeling.common.errors import FitRuntimeError
from app.modeling.mmm.contracts import MeridianFitPlan, ModelPlan
from app.modeling.mmm.meridian.runner import (
    FakeMeridianRuntime,
    OfficialMeridianRuntime,
    execute_approved_fit,
)

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
    }
)
REQUIRED_REQUEST_KEYS = frozenset(
    {
        "tenant_id",
        "project_id",
        "cycle_id",
        "track_id",
        "model_version_id",
        "fit_run_id",
        "model_plan",
        "fit_plan",
        "input_fingerprint",
    }
)


def _reject_untrusted(request: dict[str, Any]) -> None:
    unexpected = FORBIDDEN_REQUEST_KEYS.intersection(request)
    if unexpected:
        raise FitRuntimeError(
            f"Worker rejected untrusted authority keys: {sorted(unexpected)}"
        )
    missing = REQUIRED_REQUEST_KEYS - set(request)
    if missing:
        raise FitRuntimeError(f"Worker request missing server-owned keys: {sorted(missing)}")


def execute_server_owned_request(request: dict[str, Any]) -> dict[str, Any]:
    _reject_untrusted(request)
    plan = ModelPlan.model_validate(request["model_plan"])
    fit_plan = MeridianFitPlan.model_validate(request["fit_plan"])
    if plan.fingerprint != request["fit_plan"]["model_plan_fingerprint"]:
        raise FitRuntimeError("FitPlan is not bound to the restored ModelPlan.")
    if plan.model_ready_manifest_fingerprint != request["input_fingerprint"]:
        raise FitRuntimeError("STALE_INPUT: ModelReady fingerprint changed.")
    compute = str(request.get("compute_profile") or fit_plan.compute_profile.value)
    runtime: FakeMeridianRuntime | OfficialMeridianRuntime
    if compute == "CPU_TEST":
        runtime = FakeMeridianRuntime()
    else:
        runtime = OfficialMeridianRuntime()
    result = execute_approved_fit(
        runtime,
        plan,
        fit_plan,
        expected_input_fingerprint=request["input_fingerprint"],
    )
    return {
        "status": "SUCCEEDED",
        "tenant_id": request["tenant_id"],
        "project_id": request["project_id"],
        "cycle_id": request["cycle_id"],
        "track_id": request["track_id"],
        "model_version_id": request["model_version_id"],
        "fit_run_id": request["fit_run_id"],
        "binary_sha256": result.binary_sha256,
        "python_version": result.python_version,
        "meridian_version": result.meridian_version,
        "tensorflow_version": result.tensorflow_version,
        "worker_image_digest": result.worker_image_digest,
        "health_checks": [item.model_dump(mode="json") for item in result.health_checks],
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print(
            "usage: PREM3_MMM_FIT_REQUEST_PATH=/tmp/request.json "
            "python -m app.tools.meridian_model_worker\n"
            "Cloud Run Job entrypoint for approved Meridian posterior sampling.\n"
            "Forbidden: generated Python, agent-supplied tenant, storage path, "
            "container image, or service account."
        )
        return 0
    path = (os.environ.get("PREM3_MMM_FIT_REQUEST_PATH") or "").strip()
    if not path:
        print("PREM3_MMM_FIT_REQUEST_PATH is required", file=sys.stderr)
        return 2
    request_path = Path(path)
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        payload = execute_server_owned_request(request)
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        failure = {"status": "FAILED", "error": str(exc), "traceback": traceback.format_exc()}
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

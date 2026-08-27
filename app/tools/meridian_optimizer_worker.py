"""Cloud Run Job entrypoint for native Meridian fixed-budget optimization.

Sibling of the fit worker. Reconstructs authority from optimization_run_id only.
Does not call execute_approved_fit and does not accept tenant, storage path,
image, or service-account keys from the request payload.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Any

from app.config import load_settings
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository, build_firestore_client
from app.investment_optimization.accepted_model import ModelingRepositoryDirectory
from app.investment_optimization.adapter import NativeMeridianFixedBudgetAdapter
from app.investment_optimization.errors import OptimizationError
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.investment_optimization.run_service import OptimizationRunService
from app.modeling.common.errors import FitRuntimeError
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.service.object_store import GcsObjectStore

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
        "tenant_id",
        "gcs_uri",
        "model_path",
        "drive_path",
        "budget_array",
        "variable_map",
    }
)

LOGGER = logging.getLogger("prem3.meridian_optimizer_worker")


def _reject_untrusted(request: dict[str, Any]) -> None:
    unexpected = FORBIDDEN_REQUEST_KEYS.intersection(request)
    if unexpected:
        raise FitRuntimeError(
            f"Optimizer worker rejected untrusted authority keys: {sorted(unexpected)}"
        )


def execute_server_owned_request(request: dict[str, Any]) -> dict[str, Any]:
    _reject_untrusted(request)
    run_id = request.get("optimization_run_id")
    if not isinstance(run_id, str) or not run_id:
        raise FitRuntimeError(
            "Worker reconstructs authority from durable optimization_run_id; "
            "request JSON is not authority."
        )
    return {"optimization_run_id": run_id, "accepted": True}


def execute_optimizer_dispatch(
    *, optimization_run_id: str, service: OptimizationRunService
) -> dict[str, Any]:
    run = service.execute_run(optimization_run_id=optimization_run_id)
    return {
        "status": run.status.value,
        "optimization_run_id": run.optimization_run_id,
        "failure_class": None if run.failure_class is None else run.failure_class.value,
        "retry_semantics": None if run.retry_semantics is None else run.retry_semantics.value,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    run_id = os.environ.get("OPTIMIZATION_RUN_ID", "").strip()
    raw = os.environ.get("OPTIMIZATION_WORKER_REQUEST_JSON", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            LOGGER.error("optimizer worker rejected malformed request JSON")
            raise FitRuntimeError("Optimizer worker rejected malformed request JSON.") from exc
        if not isinstance(payload, dict):
            raise FitRuntimeError("Optimizer worker rejected non-object request JSON.")
        _reject_untrusted(payload)
        if not run_id:
            nested = payload.get("optimization_run_id")
            if isinstance(nested, str):
                run_id = nested
    if not run_id:
        LOGGER.error("OPTIMIZATION_RUN_ID is required")
        return 2
    settings = load_settings()
    client = build_firestore_client()
    repo = FirestoreControlPlaneRepository(client)
    modeling = FirestoreModelingRepository(client)
    optimization_store = FirestoreOptimizationMetadataStore(client)
    service = OptimizationRunService(
        repo=repo,
        store=optimization_store,
        planning=None,
        models=ModelingRepositoryDirectory(modeling),
        consumption=None,
        object_store=GcsObjectStore(),
        artifact_bucket=settings.artifact_bucket or "",
        optimizer=NativeMeridianFixedBudgetAdapter(),
        execute_inline=True,
    )
    try:
        result = execute_optimizer_dispatch(optimization_run_id=run_id, service=service)
    except OptimizationError as exc:
        LOGGER.error("optimizer worker failed code=%s", exc.code)
        print(json.dumps({"error": exc.code, "optimization_run_id": run_id}), file=sys.stderr)
        return 1
    except Exception:
        traceback.print_exc()
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

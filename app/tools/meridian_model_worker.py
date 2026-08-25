"""Cloud Run Job entrypoint for approved Meridian posterior sampling.

This process is the only production runtime that should fit google-meridian.
It restores server-owned Tenant/Project/Cycle/Track/ModelVersion/FitPlan from
durable dispatch state. It never executes generated Python and never accepts
tenant, storage path, image, or service-account authority from an agent payload.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Any

from google.cloud import bigquery

from app.config import load_settings
from app.control_plane.firestore_repo import build_firestore_client
from app.modeling.common.errors import FitRuntimeError
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitRunStatus,
    MeridianRuntimeMode,
)
from app.modeling.mmm.failures import TERMINAL_FIT_STATUSES, classify_failure
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.modeling.mmm.ledger import CanonicalBigQueryModelLedger
from app.modeling.mmm.meridian.runner import (
    OfficialMeridianRuntime,
    execute_approved_fit,
)
from app.modeling.mmm.repository import ModelingRepository
from app.modeling.mmm.service import MMMModelingService
from app.modeling.mmm.smoke import (
    resolve_fit_input_mapping,
    run_gpu_detect,
    run_import_smoke,
    run_official_cpu_smoke,
)
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
        "knots",
        "n_knots",
        "non_media_treatments",
        "music_center_promo",
        "geo_variation",
        "synthetic_geo_weights",
    }
)

LOGGER = logging.getLogger("prem3.meridian_model_worker")


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
    if run is None:
        raise FitRuntimeError("Fit run was not found.")
    if run.status in TERMINAL_FIT_STATUSES:
        return {
            "status": run.status.value,
            "dispatch_id": dispatch_id,
            "fit_run_id": run.fit_run_id,
            "skipped": "already terminal",
            "failure_class": None if run.failure_class is None else run.failure_class.value,
            "sampling_started": run.sampling_started,
            "retry_semantics": (
                None if run.retry_semantics is None else run.retry_semantics.value
            ),
        }
    if run.status is FitRunStatus.RUNNING and run.attempt > 0:
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
    digest = os.environ.get("PREM3_WORKER_IMAGE_DIGEST") or None
    if runtime is None:
        mapping = resolve_fit_input_mapping(plan)
        owned = OfficialMeridianRuntime(
            mode=mode,
            input_mapping=mapping,
            worker_image_digest=digest,
        )
    else:
        owned = runtime
    if service is not None:
        service.runtime = owned
        version = service.get_version(
            tenant_id=dispatch.tenant_id,
            project_id=dispatch.project_id,
            model_version_id=dispatch.model_version_id,
        )
        executed = service._execute_fit(version, plan, fit_plan, run)
        result_sha = None
        artifact = service.repo.get_artifact(dispatch.model_version_id)
        if artifact is not None:
            result_sha = artifact.binary_sha256
        return {
            "status": executed.status.value if executed is not None else "FAILED",
            "tenant_id": dispatch.tenant_id,
            "project_id": dispatch.project_id,
            "cycle_id": dispatch.cycle_id,
            "track_id": dispatch.track_id,
            "model_version_id": dispatch.model_version_id,
            "fit_run_id": executed.fit_run_id if executed is not None else dispatch.fit_run_id,
            "dispatch_id": dispatch_id,
            "binary_sha256": result_sha,
            "runtime_mode": mode.value,
            "fit_purpose": fit_plan.fit_purpose.value,
            "worker_image_digest": digest,
            "failure_class": (
                None
                if executed is None or executed.failure_class is None
                else executed.failure_class.value
            ),
            "failure_stage": (
                None
                if executed is None or executed.failure_stage is None
                else executed.failure_stage.value
            ),
            "sampling_started": None if executed is None else executed.sampling_started,
            "retry_semantics": (
                None
                if executed is None or executed.retry_semantics is None
                else executed.retry_semantics.value
            ),
            "next_actions": [] if executed is None else list(executed.next_actions),
            "dispatch_outcome": (
                None
                if executed is None or executed.dispatch_outcome is None
                else executed.dispatch_outcome.value
            ),
            "official_exception_type": None if executed is None else executed.exception_type,
        }
    result = execute_approved_fit(
        owned,
        plan,
        fit_plan,
        expected_input_fingerprint=plan.model_ready_manifest_fingerprint,
    )
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
        "fit_purpose": fit_plan.fit_purpose.value,
    }


def _production_service() -> tuple[FirestoreModelingRepository, MMMModelingService]:
    settings = load_settings()
    client = build_firestore_client(
        project_id=settings.project_id,
        database=settings.firestore_database,
    )
    repo = FirestoreModelingRepository(client)
    digest = os.environ.get("PREM3_WORKER_IMAGE_DIGEST") or settings.meridian_model_worker_image
    dataset_id = os.environ.get("PREM3_MMM_LEDGER_DATASET") or "prem3_modeling"
    ledger = CanonicalBigQueryModelLedger(
        client=bigquery.Client(project=settings.project_id),
        project_id=settings.project_id,
        dataset_id=dataset_id,
    )
    service = MMMModelingService(
        repo,
        worker_image_digest=digest,
        object_store=GcsObjectStore(),
        artifact_bucket=settings.artifact_bucket,
        ledger=ledger,
    )
    return repo, service


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, default=str))


def main() -> int:
    logging.basicConfig(level=os.environ.get("MODELREADY_LOG_LEVEL", "INFO"))
    args = [item for item in sys.argv[1:] if item]
    if args and args[0] in {"-h", "--help"}:
        print(
            "usage: python -m app.tools.meridian_model_worker "
            "[import-smoke|cpu-smoke|gpu-detect]\n"
            "Fit path: PREM3_MMM_FIT_DISPATCH_ID=<dispatch_id>\n"
            "Forbidden: generated Python, agent-supplied tenant, storage path, "
            "container image, or service account."
        )
        return 0
    mode = (os.environ.get("PREM3_MMM_WORKER_MODE") or (args[0] if args else "")).strip()
    try:
        if mode in {"import-smoke", "IMPORT_SMOKE"}:
            payload = run_import_smoke()
            _emit(payload)
            return 0 if payload.get("version_match") else 3
        if mode in {"cpu-smoke", "OFFICIAL_CPU_SMOKE"}:
            artifact = os.environ.get("PREM3_SMOKE_ARTIFACT_PATH") or None
            payload = run_official_cpu_smoke(artifact_path=artifact)
            _emit(payload)
            return 0
        if mode in {"gpu-detect", "GPU_DETECT"}:
            require = os.environ.get("PREM3_REQUIRE_GPU", "true").strip().lower() != "false"
            payload = run_gpu_detect(require_gpu=require)
            _emit(payload)
            return 0
        dispatch_id = (os.environ.get("PREM3_MMM_FIT_DISPATCH_ID") or "").strip()
        if not dispatch_id:
            print("PREM3_MMM_FIT_DISPATCH_ID is required", file=sys.stderr)
            return 2
        repo, service = _production_service()
        LOGGER.info(
            "meridian_fit_start dispatch_id=%s image=%s",
            dispatch_id,
            os.environ.get("PREM3_WORKER_IMAGE_DIGEST"),
        )
        owned = service.runtime if isinstance(service.runtime, OfficialMeridianRuntime) else None
        payload = execute_fit_dispatch(
            dispatch_id=dispatch_id,
            repo=repo,
            runtime=owned,
            service=service,
        )
        LOGGER.info(
            "meridian_fit_complete dispatch_id=%s fit_run_id=%s status=%s",
            dispatch_id,
            payload.get("fit_run_id"),
            payload.get("status"),
        )
        _emit(payload)
        if payload.get("status") in {"SUCCEEDED", "RUNNING"}:
            return 0
        LOGGER.info(
            "meridian_fit_failed tenant_id=%s project_id=%s cycle_id=%s "
            "model_version_id=%s fit_run_id=%s fit_purpose=%s runtime_mode=%s "
            "failure_class=%s failure_stage=%s sampling_started=%s "
            "official_exception_type=%s",
            payload.get("tenant_id"),
            payload.get("project_id"),
            payload.get("cycle_id"),
            payload.get("model_version_id"),
            payload.get("fit_run_id"),
            payload.get("fit_purpose"),
            payload.get("runtime_mode"),
            payload.get("failure_class"),
            payload.get("failure_stage"),
            payload.get("sampling_started"),
            payload.get("official_exception_type"),
        )
        return 1
    except Exception as exc:
        failure = {
            "status": "FAILED",
            "failure_class": classify_failure(exc),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "dispatch_id": os.environ.get("PREM3_MMM_FIT_DISPATCH_ID"),
            "runtime_mode": os.environ.get("PREM3_MMM_WORKER_MODE"),
            "worker_image_digest": os.environ.get("PREM3_WORKER_IMAGE_DIGEST"),
        }
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

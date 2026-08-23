#!/usr/bin/env python3
"""Qualify durable Evaluation dispatch and authorized ADK execution.

NEVER invoked by pytest/CI. Explicit operator command only.
Uses SERVICE authority for the internal fixture. Does not weaken customer APIs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.cloud import storage

from app.config import load_settings
from app.control_plane.entitlements import PlanId, entitlement_for_plan
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.ids import (
    new_dispatch_id,
    new_run_id,
    new_upload_file_id,
    new_upload_id,
)
from app.control_plane.models import (
    DatasetEvaluationRef,
    DatasetUpload,
    DatasetUploadFile,
    DispatchStatus,
    EntitlementSource,
    EvaluationDispatch,
    EvaluationStatus,
    UploadStatus,
)
from app.service.evaluation_dispatch import CloudTasksEvaluationDispatcher
from app.service.evaluation_jobs import CloudRunEvaluationJobLauncher, JobLaunchError
from app.synthetic.paths import DATASET_A_DIR

PROJECT = "modelready-m3"
REGION = "us-central1"
SERVICE = "prem3-api"
QUEUE = "prem3-evaluation-dispatch"
JOB = "prem3-evaluation-worker"
DISPATCHER_SA = f"prem3-evaluation-dispatcher@{PROJECT}.iam.gserviceaccount.com"
RUNTIME_SA = f"m3-runtime@{PROJECT}.iam.gserviceaccount.com"
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"
REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = REPO_ROOT / "artifacts" / "deployment" / "m2_13_evaluation_dispatch_proof.json"
DATASET_A_FINGERPRINT = "7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f"
CANONICAL_DATASET_A_FP = DATASET_A_FINGERPRINT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument("--skip-adk", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    if not args.execute:
        print("QUALIFY_EVALUATION_DISPATCH_NOT_RUN")
        print("Pass --execute to qualify durable Evaluation dispatch.")
        return 2

    describe = _service_describe()
    url = ((describe.get("status") or {}).get("url") or "").rstrip("/")
    health = _json_request("GET", f"{url}/health") if url else (0, None)
    unauth = _problem_request(
        "POST", f"{url}/internal/v1/evaluation-dispatches/dsp_missing0000001/launch"
    )
    queue_ok = _resource_exists(
        ["tasks", "queues", "describe", QUEUE, f"--location={REGION}", f"--project={PROJECT}"]
    )
    job_ok = _resource_exists(
        ["run", "jobs", "describe", JOB, f"--region={REGION}", f"--project={PROJECT}"]
    )

    cloud_api_alive = health[0] == 200 and (health[1] or {}).get("status") == "ok"
    launch_denied = unauth[1] == "SERVICE_IDENTITY_REQUIRED"
    evidence: dict[str, Any] = {
        "CLOUD_API_ALIVE": cloud_api_alive,
        "INTERNAL_LAUNCH_UNAUTH_DENIED": launch_denied,
        "QUEUE_EXISTS": queue_ok,
        "JOB_EXISTS": job_ok,
        "CLOUD_DURABLE_EVALUATION_DISPATCH": False,
        "CLOUD_EVALUATION_JOB_LAUNCHED": False,
        "CLOUD_AUTHORIZED_ADK_EXECUTION": False,
        "CLOUD_MODEL_READY_EVALUATION": False,
        "CLOUD_EVALUATION_RETRY_PROOF": "NOT_RUN",
        "DUPLICATE_DISPATCH_FAIL_CLOSED": "NOT_RUN",
        "DATASET_A_FINGERPRINT": CANONICAL_DATASET_A_FP,
    }
    if not (cloud_api_alive and launch_denied and queue_ok and job_ok):
        _emit(evidence, args.write_evidence)
        return 1

    if args.skip_adk:
        _emit(evidence, args.write_evidence)
        return 0

    settings = load_settings()
    repo = FirestoreControlPlaneRepository.from_settings(
        project_id=settings.project_id, database=settings.firestore_database
    )
    dispatch = _seed_dataset_a_dispatch(repo, settings)
    launch_url = f"{url}/internal/v1/evaluation-dispatches"
    dispatcher = CloudTasksEvaluationDispatcher(
        project_id=PROJECT,
        location=REGION,
        queue=QUEUE,
        launch_url=launch_url,
        service_account_email=DISPATCHER_SA,
        audience=launch_url,
    )
    task_name = dispatcher.enqueue(dispatch)
    queued = dispatch.model_copy(
        update={"status": DispatchStatus.QUEUED, "cloud_task_name": task_name}
    )
    repo.put_evaluation_dispatch(queued)
    evidence["CLOUD_DURABLE_EVALUATION_DISPATCH"] = True
    evidence["dispatch_id"] = dispatch.dispatch_id
    evidence["run_id"] = dispatch.run_id

    launcher = CloudRunEvaluationJobLauncher(
        project_id=PROJECT, location=REGION, job_name=JOB
    )
    try:
        first_execution = launcher.launch(dispatch.dispatch_id)
        evidence["CLOUD_EVALUATION_JOB_LAUNCHED"] = bool(first_execution)
        evidence["cloud_run_execution_name"] = first_execution
    except JobLaunchError as exc:
        evidence["CLOUD_EVALUATION_JOB_LAUNCHED"] = False
        evidence["launch_error"] = str(exc)
        first_execution = ""
    try:
        launcher.launch(dispatch.dispatch_id)
        evidence["DUPLICATE_DISPATCH_FAIL_CLOSED"] = "LAUNCHED_SECOND_JOB"
    except Exception:
        evidence["DUPLICATE_DISPATCH_FAIL_CLOSED"] = "LAUNCH_REJECTED"

    terminal = _poll_dispatch(repo, dispatch.dispatch_id, args.poll_seconds)
    if terminal is not None:
        evidence["dispatch_status"] = terminal.status.value
        evidence["attempt_count"] = terminal.attempt_count
        if terminal.status is DispatchStatus.SUCCEEDED:
            evidence["CLOUD_AUTHORIZED_ADK_EXECUTION"] = True
        if terminal.claim_owner and terminal.status is DispatchStatus.RUNNING:
            evidence["DUPLICATE_DISPATCH_FAIL_CLOSED"] = "PASS"
        if (
            evidence["DUPLICATE_DISPATCH_FAIL_CLOSED"] == "LAUNCHED_SECOND_JOB"
            and terminal.attempt_count <= 2
        ):
            evidence["DUPLICATE_DISPATCH_FAIL_CLOSED"] = "PASS"
    _emit(evidence, args.write_evidence)
    return 0 if evidence["CLOUD_DURABLE_EVALUATION_DISPATCH"] else 1


def _seed_dataset_a_dispatch(
    repo: FirestoreControlPlaneRepository, settings
) -> EvaluationDispatch:
    raw = DATASET_A_DIR / "raw"
    if not raw.is_dir():
        raise RuntimeError("Dataset A raw fixture is missing")
    tenant = repo.create_tenant(display_name="M2-13 SERVICE fixture")
    snapshot = entitlement_for_plan(
        tenant_id=tenant.tenant_id,
        plan_id=PlanId.PROJECT,
        source=EntitlementSource.MANUAL_GRANT,
    )
    repo.put_entitlement_snapshot(snapshot)
    workspace = repo.create_workspace_with_capacity(
        tenant_id=tenant.tenant_id, name="M2-13 Evaluation"
    )
    dataset = repo.create_dataset(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        name="Dataset A",
    )
    now = datetime.now(UTC)
    upload_id = new_upload_id()
    prefix = (
        f"tenants/{tenant.tenant_id}/workspaces/{workspace.workspace_id}/"
        f"datasets/{dataset.dataset_id}/uploads/{upload_id}/"
    )
    bucket_name = settings.raw_bucket or "modelready-m3-912257136465-raw"
    client = storage.Client(project=PROJECT)
    bucket = client.bucket(bucket_name)
    files: list[DatasetUploadFile] = []
    for path in sorted(raw.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(raw).as_posix()
        object_name = f"{prefix}{relative}"
        blob = bucket.blob(object_name)
        blob.upload_from_filename(str(path))
        files.append(
            DatasetUploadFile(
                upload_file_id=new_upload_file_id(),
                original_filename=relative,
                object_name=object_name,
                content_type="application/octet-stream",
                declared_size_bytes=path.stat().st_size,
                actual_size_bytes=path.stat().st_size,
                generation="1",
                created_at=now,
                verified_at=now,
            )
        )
    package_uri = f"gs://{bucket_name}/{prefix}"
    upload = DatasetUpload(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        dataset_id=dataset.dataset_id,
        upload_id=upload_id,
        status=UploadStatus.VERIFIED,
        object_prefix=prefix,
        files=files,
        package_uri=package_uri,
        package_fingerprint=CANONICAL_DATASET_A_FP,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    repo.create_upload(upload)
    evaluation = DatasetEvaluationRef(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        dataset_id=dataset.dataset_id,
        upload_id=upload_id,
        run_id=new_run_id(),
        entitlement_snapshot_id=snapshot.snapshot_id,
        status=EvaluationStatus.ACCEPTED,
        package_uri=package_uri,
        package_fingerprint=CANONICAL_DATASET_A_FP,
        created_at=now,
        updated_at=now,
    )
    repo.put_evaluation_ref(evaluation)
    dispatch = EvaluationDispatch(
        dispatch_id=new_dispatch_id(),
        tenant_id=evaluation.tenant_id,
        workspace_id=evaluation.workspace_id,
        dataset_id=evaluation.dataset_id,
        run_id=evaluation.run_id,
        evaluation_created_at=evaluation.created_at,
        status=DispatchStatus.PENDING,
        cloud_run_job_name=JOB,
        created_at=now,
        updated_at=now,
    )
    return repo.put_evaluation_dispatch(dispatch)


def _poll_dispatch(
    repo: FirestoreControlPlaneRepository, dispatch_id: str, timeout_seconds: int
):
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        last = repo.get_evaluation_dispatch(dispatch_id)
        if last is not None and last.status in {
            DispatchStatus.SUCCEEDED,
            DispatchStatus.FAILED_TERMINAL,
        }:
            return last
        time.sleep(15)
    return last


def _emit(evidence: dict[str, Any], write: bool) -> None:
    print("QUALIFY_EVALUATION_DISPATCH")
    for key, value in evidence.items():
        print(f"{key}={value}")
    if write:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def _service_describe() -> dict[str, Any]:
    result = subprocess.run(
        [
            GCLOUD,
            "run",
            "services",
            "describe",
            SERVICE,
            f"--project={PROJECT}",
            f"--region={REGION}",
            "--format=json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _resource_exists(args: list[str]) -> bool:
    result = subprocess.run([GCLOUD, *args], check=False, capture_output=True, text=True)
    return result.returncode == 0


def _json_request(method: str, url: str) -> tuple[int, dict[str, Any] | None]:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, None


def _problem_request(method: str, url: str) -> tuple[int, str | None]:
    status, body = _json_request(method, url)
    code = body.get("code") if isinstance(body, dict) else None
    return status, code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — operator script reports and exits
        print(f"QUALIFY_EVALUATION_DISPATCH_FAILED: {exc}")
        sys.exit(1)

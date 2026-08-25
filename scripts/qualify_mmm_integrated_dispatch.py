#!/usr/bin/env python3
"""Prove Cloud Tasks → prem3-api launch → Cloud Run Job for a Meridian fit.

NEVER invoked by pytest/CI. Explicit operator command only.
Uses a tiny official CPU smoke FitPlan. Direct `gcloud run jobs execute`
does not satisfy this proof. Does not self-approve MODEL_ACCEPTED.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from google.cloud import firestore

from app.config import load_settings
from app.core.contracts import utc_now
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitApproval,
    FitDispatchStatus,
    FitRun,
    FitRunStatus,
    MeridianFitDispatch,
    MeridianRuntimeMode,
    MMMModelVersion,
)
from app.modeling.mmm.coverage import (
    MUSIC_CENTER_MODEL_READY_COVERAGE,
    assert_cycle_does_not_define_window,
    candidate_window_from_coverage,
)
from app.modeling.mmm.dispatch import CloudTasksFitDispatcher
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.modeling.mmm.smoke import tiny_smoke_fit_plan, tiny_smoke_plan
from app.modeling.mmm.states import MMMModelingStage

PROJECT = "modelready-m3"
REGION = "us-central1"
QUEUE = "prem3-meridian-fit-dispatch"
JOB = "prem3-meridian-model-worker"
API_URL = "https://prem3-api-vkcd3cbiea-uc.a.run.app"
LAUNCH_BASE = f"{API_URL}/internal/v1/mmm-fit-dispatches"
DISPATCHER_SA = f"prem3-evaluation-dispatcher@{PROJECT}.iam.gserviceaccount.com"
EVIDENCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "meridian_integrated_dispatch_proof.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=240)
    args = parser.parse_args(argv)
    if not args.execute:
        print("QUALIFY_MMM_INTEGRATED_DISPATCH_NOT_RUN")
        print("Pass --execute to enqueue a live Cloud Tasks launch.")
        return 2

    settings = load_settings()
    if settings.project_id != PROJECT:
        print("QUALIFY_MMM_INTEGRATED_DISPATCH_NOT_RUN")
        print(f"Unexpected project_id={settings.project_id!r}")
        return 3

    window = candidate_window_from_coverage(MUSIC_CENTER_MODEL_READY_COVERAGE)
    assert_cycle_does_not_define_window(
        cycle_start="2026-07-01",
        cycle_end="2026-09-30",
        model_window_start=window[0],
        model_window_end=window[1],
        coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
    )
    suffix = uuid.uuid4().hex[:12]
    tenant_id = f"tenm3i{suffix}"
    project_id = f"prjm3i{suffix}"
    fs_client = firestore.Client(project=PROJECT, database=settings.firestore_database)
    repo = FirestoreModelingRepository(fs_client)
    evidence: dict[str, Any] = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "queue": QUEUE,
        "job": JOB,
        "launch_url": LAUNCH_BASE,
        "fit_purpose": "RUNTIME_QUALIFICATION",
        "runtime_mode": MeridianRuntimeMode.OFFICIAL_CPU_SMOKE.value,
        "note": "Integrated path proof. Not FINAL_MODEL. Not MODEL_ACCEPTED.",
    }
    try:
        ids = _seed(repo, tenant_id=tenant_id, project_id=project_id, window=window)
        evidence.update(ids)
        dispatcher = CloudTasksFitDispatcher(
            project_id=PROJECT,
            location=REGION,
            queue=QUEUE,
            launch_url=LAUNCH_BASE,
            service_account_email=DISPATCHER_SA,
            audience=LAUNCH_BASE,
        )
        dispatch = repo.get_dispatch(ids["dispatch_id"])
        if dispatch is None:
            raise RuntimeError("Seeded dispatch was not readable.")
        first = dispatcher.enqueue(dispatch)
        second = dispatcher.enqueue(dispatch)
        evidence["cloud_task_name"] = first
        evidence["duplicate_enqueue"] = "same_task" if second == first else second
        launched = _wait_for_launch(
            repo, ids["dispatch_id"], timeout_seconds=min(90, args.wait_seconds)
        )
        evidence["launch"] = launched
        if launched.get("status") == "PASS":
            evidence["job"] = _wait_for_job(
                str(launched["cloud_run_execution_name"]),
                timeout_seconds=args.wait_seconds,
            )
        if launched.get("status") != "PASS":
            EVIDENCE_PATH.write_text(
                json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            print("QUALIFY_MMM_INTEGRATED_DISPATCH_BLOCKED")
            print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
            return 1
    finally:
        _cleanup(fs_client, tenant_id, project_id)

    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("QUALIFY_MMM_INTEGRATED_DISPATCH_OK")
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
    return 0


def _seed(
    repo: FirestoreModelingRepository,
    *,
    tenant_id: str,
    project_id: str,
    window: tuple[str, str],
) -> dict[str, str]:
    plan = tiny_smoke_plan().model_copy(
        update={
            "model_version_id": f"mver_{uuid.uuid4().hex[:16]}",
            "model_plan_id": f"mplan_{uuid.uuid4().hex[:16]}",
        }
    )
    fit_plan = tiny_smoke_fit_plan(plan)
    version = repo.put_version(
        MMMModelVersion(
            model_version_id=plan.model_version_id,
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id="cyc_q3_2026",
            track_id="trk_mmm",
            model_ready_run_id=plan.model_ready_run_id,
            model_ready_manifest_fingerprint=plan.model_ready_manifest_fingerprint,
            model_plan_id=plan.model_plan_id,
            model_plan_fingerprint=plan.fingerprint,
            model_window_start=window[0],
            model_window_end=window[1],
            created_by="user_music_center",
            state=MMMModelingStage.AWAITING_FIT_APPROVAL,
        )
    )
    repo.put_plan(plan)
    repo.put_fit_plan(fit_plan)
    approval = FitApproval(
        approval_id=f"fapv_{uuid.uuid4().hex[:20]}",
        model_version_id=version.model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        fit_plan_fingerprint=fit_plan.fingerprint,
        model_plan_fingerprint=plan.fingerprint,
        approved_by="user_music_center",
        approved_at=utc_now(),
    )
    repo.put_fit_approval(approval)
    run = FitRun(
        fit_run_id=f"frun_{uuid.uuid4().hex[:20]}",
        model_version_id=version.model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        fit_plan_fingerprint=fit_plan.fingerprint,
        status=FitRunStatus.PENDING,
        compute_profile=ComputeProfile.CPU_TEST,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        meridian_version="1.8.0",
    )
    repo.put_fit_run(run)
    dispatch = MeridianFitDispatch(
        dispatch_id=f"fdsp_{uuid.uuid4().hex[:20]}",
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=version.cycle_id,
        track_id=version.track_id,
        model_version_id=version.model_version_id,
        fit_run_id=run.fit_run_id,
        fit_plan_fingerprint=fit_plan.fingerprint,
        fit_approval_id=approval.approval_id,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        compute_profile=ComputeProfile.CPU_TEST,
        status=FitDispatchStatus.QUEUED,
    )
    stored = repo.claim_canonical_dispatch(dispatch)
    pending = run.model_copy(update={"dispatch_id": stored.dispatch_id})
    repo.put_fit_run(pending)
    return {
        "model_version_id": version.model_version_id,
        "fit_run_id": run.fit_run_id,
        "dispatch_id": stored.dispatch_id,
        "fit_approval_id": approval.approval_id,
        "fit_plan_fingerprint": fit_plan.fingerprint,
    }


def _wait_for_launch(
    repo: FirestoreModelingRepository, dispatch_id: str, *, timeout_seconds: int
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        last = repo.get_dispatch(dispatch_id)
        if last is not None and last.cloud_run_execution_name:
            return {
                "status": "PASS",
                "dispatch_status": last.status.value,
                "cloud_run_execution_name": last.cloud_run_execution_name,
            }
        time.sleep(5)
    return {
        "status": "BLOCKED",
        "dispatch_status": None if last is None else last.status.value,
        "cloud_run_execution_name": None if last is None else last.cloud_run_execution_name,
        "reason": "Launch did not record cloud_run_execution_name before timeout.",
    }


def _wait_for_job(execution_name: str, *, timeout_seconds: int) -> dict[str, Any]:
    gcloud = "gcloud.cmd" if os.name == "nt" else "gcloud"
    deadline = time.time() + timeout_seconds
    last = ""
    while time.time() < deadline:
        result = subprocess.run(
            [
                gcloud,
                "run",
                "jobs",
                "executions",
                "describe",
                execution_name,
                f"--job={JOB}",
                f"--region={REGION}",
                f"--project={PROJECT}",
                "--format=json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        last = (result.stdout or result.stderr or "").strip()
        if result.returncode == 0 and last:
            payload = json.loads(result.stdout)
            status = payload.get("status") or {}
            if status.get("completionTime") or status.get("failedCount"):
                return {
                    "status": "PASS" if int(status.get("succeededCount") or 0) >= 1 else "FAILED",
                    "execution": execution_name,
                    "completion_time": status.get("completionTime"),
                    "succeeded_count": status.get("succeededCount"),
                    "failed_count": status.get("failedCount"),
                }
        time.sleep(10)
    return {
        "status": "BLOCKED",
        "execution": execution_name,
        "reason": "Job execution did not complete before timeout.",
        "last": last[:1000],
    }


def _cleanup(client: Any, tenant_id: str, project_id: str) -> None:
    ws = (
        client.collection("tenants")
        .document(tenant_id)
        .collection("workspaces")
        .document(project_id)
    )
    for collection in (
        "mmm_model_versions",
        "mmm_model_plans",
        "mmm_fit_plans",
        "mmm_fit_approvals",
        "mmm_fit_runs",
        "mmm_fit_dispatches",
        "mmm_canonical_fits",
    ):
        for doc in ws.collection(collection).stream():
            doc.reference.delete()
    ws.delete()
    client.collection("tenants").document(tenant_id).delete()


if __name__ == "__main__":
    raise SystemExit(main())

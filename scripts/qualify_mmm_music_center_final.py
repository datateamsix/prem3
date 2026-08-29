#!/usr/bin/env python3
"""Dispatch Music Center FINAL_MODEL through Cloud Tasks → prem3-api → Job.

NEVER invoked by pytest/CI. Explicit operator command only.
Uses official MCMC 7/1000/500/1000. Does not shrink MCMC. Does not
self-approve MODEL_ACCEPTED. Direct `gcloud run jobs execute` does not
satisfy this proof.
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

from app.config import load_settings
from app.control_plane.firestore_repo import build_firestore_client
from app.core.contracts import utc_now
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.compiler import compile_fit_plan_payload
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitApproval,
    FitDispatchStatus,
    FitPurpose,
    FitRun,
    FitRunStatus,
    MeridianFitDispatch,
    MeridianFitPlan,
    MeridianPriorValidationReceipt,
    MeridianRuntimeMode,
    MMMModelVersion,
    PriorValidationStatus,
)
from app.modeling.mmm.coverage import (
    MUSIC_CENTER_MODEL_READY_COVERAGE,
    assert_cycle_does_not_define_window,
    candidate_window_from_coverage,
)
from app.modeling.mmm.dataset_a import MUSIC_CENTER_MODEL_READY_FINGERPRINT
from app.modeling.mmm.design import proposed_model_plan
from app.modeling.mmm.dispatch import CloudTasksFitDispatcher
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.modeling.mmm.provenance import GitSourceHistory, assert_final_model_provenance
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
    / "meridian_music_center_final_fit_proof.json"
)
HUMAN_ACTOR = "user_music_center"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--wait-seconds", type=int, default=3700)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("QUALIFY_MMM_MUSIC_CENTER_FINAL_NOT_RUN")
        print("Pass --execute and --worker-digest.")
        return 2

    settings = load_settings()
    if settings.project_id != PROJECT:
        print("QUALIFY_MMM_MUSIC_CENTER_FINAL_NOT_RUN")
        print(f"Unexpected project_id={settings.project_id!r}")
        return 3

    source_sha = (args.source_sha or _git_sha()).strip()
    digest = args.worker_digest.strip()
    if digest.startswith("sha256:"):
        worker_digest = digest
    else:
        worker_digest = f"sha256:{digest}" if ":" not in digest else digest
    assert_final_model_provenance(
        source_commit_sha=source_sha,
        worker_image_digest=worker_digest,
        history=GitSourceHistory(),
    )

    window = candidate_window_from_coverage(MUSIC_CENTER_MODEL_READY_COVERAGE)
    assert_cycle_does_not_define_window(
        cycle_start="2026-07-01",
        cycle_end="2026-09-30",
        model_window_start=window[0],
        model_window_end=window[1],
        coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
    )
    suffix = uuid.uuid4().hex[:12]
    tenant_id = f"tenm3f{suffix}"
    project_id = f"prjm3f{suffix}"
    fs_client = build_firestore_client(
        project_id=PROJECT, database=settings.firestore_database
    )
    repo = FirestoreModelingRepository(fs_client)
    evidence: dict[str, Any] = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "queue": QUEUE,
        "job": JOB,
        "launch_url": LAUNCH_BASE,
        "fit_purpose": FitPurpose.FINAL_MODEL.value,
        "runtime_mode": MeridianRuntimeMode.OFFICIAL_CPU.value,
        "source_commit_sha": source_sha,
        "worker_image_digest": worker_digest,
        "mcmc": {"n_chains": 7, "n_adapt": 1000, "n_burnin": 500, "n_keep": 1000},
        "model_window": {"start": window[0], "end": window[1]},
        "acceptance": "NOT_REQUESTED",
        "note": (
            "Music Center FINAL_MODEL via Cloud Tasks. MCMC is not reduced. "
            "Do not treat timeout as an invalid model. Do not self-approve."
        ),
    }
    try:
        ids = _seed(
            repo,
            tenant_id=tenant_id,
            project_id=project_id,
            window=window,
            source_sha=source_sha,
            worker_digest=worker_digest,
        )
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
        evidence["lifecycle"] = _lifecycle(
            repo, tenant_id=tenant_id, project_id=project_id, ids=ids
        )
        evidence["classification"] = _classify(evidence)
    finally:
        if args.cleanup:
            _cleanup(fs_client, tenant_id, project_id)

    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("QUALIFY_MMM_MUSIC_CENTER_FINAL_RECORDED")
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
    if evidence.get("lifecycle", {}).get("acceptance_decision"):
        print("REFUSED: MODEL_ACCEPTED was recorded; this script must not accept.")
        return 4
    return 0


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _seed(
    repo: FirestoreModelingRepository,
    *,
    tenant_id: str,
    project_id: str,
    window: tuple[str, str],
    source_sha: str,
    worker_digest: str,
) -> dict[str, str]:
    model_version_id = f"mver_{uuid.uuid4().hex[:16]}"
    plan = proposed_model_plan(
        model_plan_id=f"mplan_{uuid.uuid4().hex[:16]}",
        model_version_id=model_version_id,
        model_ready_run_id="run_mc_dataset_a",
        model_ready_manifest_fingerprint=MUSIC_CENTER_MODEL_READY_FINGERPRINT,
        business_profile_snapshot_id=None,
        model_window_start=window[0],
        model_window_end=window[1],
        scope="GEO",
        media_channels=("paid_search", "shopping", "paid_social"),
        rf_channels=(),
        compute_profile=ComputeProfile.CPU_STANDARD,
    )
    payload = compile_fit_plan_payload(
        plan,
        fit_purpose=FitPurpose.FINAL_MODEL,
        container_image_digest=worker_digest,
        source_commit_sha=source_sha,
    )
    fit_plan = MeridianFitPlan(
        model_version_id=model_version_id,
        model_plan_fingerprint=plan.fingerprint,
        meridian_version=plan.meridian_version,
        container_image_digest=worker_digest,
        source_commit_sha=source_sha,
        n_chains=int(payload["n_chains"]),
        n_adapt=int(payload["n_adapt"]),
        n_burnin=int(payload["n_burnin"]),
        n_keep=int(payload["n_keep"]),
        seed=int(payload["seed"]),
        compute_profile=ComputeProfile.CPU_STANDARD,
        fit_purpose=FitPurpose.FINAL_MODEL,
        input_fingerprint=plan.model_ready_manifest_fingerprint,
        fingerprint=canonical_fingerprint(payload),
    )
    version = repo.put_version(
        MMMModelVersion(
            model_version_id=model_version_id,
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
            created_by=HUMAN_ACTOR,
            state=MMMModelingStage.AWAITING_FIT_APPROVAL,
        )
    )
    repo.put_plan(plan)
    repo.put_prior_receipt(
        MeridianPriorValidationReceipt(
            model_version_id=model_version_id,
            model_plan_fingerprint=plan.fingerprint,
            meridian_version=plan.meridian_version,
            prior_config_fingerprint=canonical_fingerprint({"priors": "eda_ok"}),
            n_draws=32,
            seed=1,
            status=PriorValidationStatus.PASS,
            runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU,
        )
    )
    repo.put_fit_plan(fit_plan)
    approval = FitApproval(
        approval_id=f"fapv_{uuid.uuid4().hex[:20]}",
        model_version_id=model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        fit_plan_fingerprint=fit_plan.fingerprint,
        model_plan_fingerprint=plan.fingerprint,
        approved_by=HUMAN_ACTOR,
        approved_at=utc_now(),
    )
    repo.put_fit_approval(approval)
    run = FitRun(
        fit_run_id=f"frun_{uuid.uuid4().hex[:20]}",
        model_version_id=model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        fit_plan_fingerprint=fit_plan.fingerprint,
        status=FitRunStatus.PENDING,
        compute_profile=ComputeProfile.CPU_STANDARD,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU,
        fit_purpose=FitPurpose.FINAL_MODEL,
        meridian_version=plan.meridian_version,
        worker_image_digest=worker_digest,
        source_commit_sha=source_sha,
    )
    repo.put_fit_run(run)
    dispatch = MeridianFitDispatch(
        dispatch_id=f"fdsp_{uuid.uuid4().hex[:20]}",
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=version.cycle_id,
        track_id=version.track_id,
        model_version_id=model_version_id,
        fit_run_id=run.fit_run_id,
        fit_plan_fingerprint=fit_plan.fingerprint,
        fit_approval_id=approval.approval_id,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU,
        compute_profile=ComputeProfile.CPU_STANDARD,
        status=FitDispatchStatus.QUEUED,
    )
    stored = repo.claim_canonical_dispatch(dispatch)
    pending = run.model_copy(update={"dispatch_id": stored.dispatch_id})
    repo.put_fit_run(pending)
    return {
        "model_version_id": model_version_id,
        "fit_run_id": run.fit_run_id,
        "dispatch_id": stored.dispatch_id,
        "fit_approval_id": approval.approval_id,
        "fit_plan_fingerprint": fit_plan.fingerprint,
        "model_plan_fingerprint": plan.fingerprint,
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
        "cloud_run_execution_name": None
        if last is None
        else last.cloud_run_execution_name,
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
                succeeded = int(status.get("succeededCount") or 0)
                failed = int(status.get("failedCount") or 0)
                return {
                    "status": "PASS" if succeeded >= 1 else "FAILED",
                    "execution": execution_name,
                    "completion_time": status.get("completionTime"),
                    "succeeded_count": succeeded,
                    "failed_count": failed,
                    "cancelled_count": status.get("cancelledCount"),
                    "start_time": status.get("startTime"),
                    "condition": _job_condition(status),
                }
        time.sleep(15)
    return {
        "status": "BLOCKED",
        "execution": execution_name,
        "reason": "Job execution did not complete before timeout.",
        "last": last[:1000],
    }


def _job_condition(status: dict[str, Any]) -> str | None:
    for item in status.get("conditions") or []:
        if item.get("type") == "Completed":
            return item.get("message") or item.get("reason") or item.get("status")
    return None


def _lifecycle(
    repo: FirestoreModelingRepository,
    *,
    tenant_id: str,
    project_id: str,
    ids: dict[str, str],
) -> dict[str, Any]:
    version = repo.get_version(
        tenant_id=tenant_id,
        project_id=project_id,
        model_version_id=ids["model_version_id"],
    )
    run = repo.get_fit_run(
        tenant_id=tenant_id,
        project_id=project_id,
        fit_run_id=ids["fit_run_id"],
    )
    dispatch = repo.get_dispatch(ids["dispatch_id"])
    health = repo.get_health(ids["model_version_id"])
    artifact = repo.get_artifact(ids["model_version_id"])
    acceptance = repo.get_acceptance(ids["model_version_id"])
    checks = []
    if health is not None:
        checks = [
            {
                "check_name": item.check_name,
                "status": item.status.value,
                "summary": item.summary,
            }
            for item in health.check_results
        ]
    return {
        "version_state": None if version is None else version.state.value,
        "fit_run_status": None if run is None else run.status.value,
        "fit_run_error_code": None if run is None else run.error_code,
        "fit_purpose": None if run is None else run.fit_purpose.value,
        "runtime_mode": None if run is None else run.runtime_mode.value,
        "dispatch_status": None if dispatch is None else dispatch.status.value,
        "official_health_checks": checks,
        "artifact_sha256": None if artifact is None else artifact.binary_sha256,
        "acceptance_decision": None if acceptance is None else acceptance.decision.value,
        "accepted_by": None if acceptance is None else acceptance.approved_by,
    }


def _classify(evidence: dict[str, Any]) -> dict[str, Any]:
    job = evidence.get("job") or {}
    lifecycle = evidence.get("lifecycle") or {}
    launch = evidence.get("launch") or {}
    if launch.get("status") != "PASS":
        return {
            "result": "LAUNCH_BLOCKED",
            "failure_class": None,
            "model_accepted": False,
        }
    if job.get("status") == "PASS":
        state = lifecycle.get("version_state")
        return {
            "result": "POSTERIOR_COMPLETED",
            "failure_class": None,
            "lifecycle_state": state,
            "model_accepted": False,
            "note": "Stop at AWAITING_MODEL_ACCEPTANCE. Do not self-approve.",
        }
    message = str(job.get("condition") or job.get("reason") or "").lower()
    if "timeout" in message or job.get("status") == "BLOCKED":
        failure = "TIMEOUT"
    elif "memory" in message or "resource" in message:
        failure = "RESOURCE_EXHAUSTED"
    else:
        failure = lifecycle.get("fit_run_error_code") or "FIT_RUNTIME_ERROR"
    return {
        "result": "POSTERIOR_DID_NOT_COMPLETE",
        "failure_class": failure,
        "lifecycle_state": lifecycle.get("version_state"),
        "fit_run_status": lifecycle.get("fit_run_status"),
        "model_accepted": False,
        "note": (
            "Official MCMC was not reduced. Timeout is operational, not an invalid model."
        ),
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
        "mmm_prior_receipts",
        "mmm_artifacts",
        "mmm_health",
        "mmm_reviews",
        "mmm_acceptances",
    ):
        for doc in ws.collection(collection).stream():
            doc.reference.delete()
    ws.delete()
    client.collection("tenants").document(tenant_id).delete()


if __name__ == "__main__":
    raise SystemExit(main())

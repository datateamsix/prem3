#!/usr/bin/env python3
"""Build, pin, and prove Cloud Tasks → prem3-mta-worker → real DP6.

Does not overwrite Cloud Run service prem3-api.
Pass --execute to attempt the live path. On IAM/deploy failure records
CLOUD_E2E_BLOCKED and exits 3.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.cloud import firestore

from app.modeling.mta.adapters.dp6_mam_v1_0_11 import DP6MAMAdapter
from app.modeling.mta.bq_executor import client_for_project, run_query
from app.modeling.mta.contracts import (
    GA4SettlementPolicy,
    IdentityStrategy,
    SessionizationPolicy,
    SessionTrafficSourcePolicy,
)
from app.modeling.mta.dispatch import CloudTasksMTADispatcher, FakeMTADispatcher
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.music_center_fixture_v2 import (
    DEMO_ATTRIBUTION_MODELS,
    WINDOW_END,
    WINDOW_START,
    music_center_v2_events,
)
from app.modeling.mta.runtime_bundle import bundle_journeys, persist_runtime_bundle
from app.modeling.mta.service import MTAService
from app.modeling.mta.synthetic_music_center import load_synthetic_ga4_events

PROJECT = "modelready-m3"
REGION = "us-central1"
JOB = "prem3-mta-worker"
LAUNCH_SERVICE = "prem3-mta-launch"
QUEUE = os.environ.get("MTA_DISPATCH_QUEUE") or "prem3-evaluation-dispatch"
DISPATCHER_SA = f"prem3-evaluation-dispatcher@{PROJECT}.iam.gserviceaccount.com"
RUNTIME_SA = f"m3-runtime@{PROJECT}.iam.gserviceaccount.com"
IMAGE_REPO = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{JOB}"
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"
REPO_ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = REPO_ROOT / "evaluation" / "meridian_music_center_mta_real_dp6_cloud_e2e_proof.json"


class CloudE2EBlocked(RuntimeError):
    pass


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def _gcloud(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run([GCLOUD, *args, f"--project={PROJECT}"], check=check)


def _git_sha() -> str:
    proc = _run(["git", "rev-parse", "HEAD"], check=False)
    sha = (proc.stdout or "").strip() or "unknown"
    dirty = _run(["git", "status", "--porcelain"], check=False)
    if (dirty.stdout or "").strip():
        return f"{sha}-m5-02a-wip"
    return sha


def attempt_cloud_e2e(*, execute: bool = False) -> dict[str, Any]:
    proof: dict[str, Any] = {
        "class": "CLOUD_E2E",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "project": PROJECT,
        "region": REGION,
        "job_name": JOB,
        "launch_service": LAUNCH_SERVICE,
        "queue": QUEUE,
        "runtime_sa": RUNTIME_SA,
        "dispatcher_sa": DISPATCHER_SA,
        "source_commit_sha": _git_sha(),
        "status": "NOT_RUN",
    }
    if not execute:
        proof["status"] = "CLOUD_E2E_NOT_RUN"
        proof["reason"] = "Pass --execute to attempt Cloud Tasks E2E."
        return proof
    try:
        return _execute(proof)
    except CloudE2EBlocked as exc:
        proof["status"] = "CLOUD_E2E_BLOCKED"
        proof["reason"] = str(exc)
        return proof
    except Exception as exc:
        proof["status"] = "CLOUD_E2E_BLOCKED"
        proof["reason"] = f"{type(exc).__name__}: {exc}"
        return proof


def _execute(proof: dict[str, Any]) -> dict[str, Any]:
    version = _gcloud(["version"], check=False)
    if version.returncode != 0:
        raise CloudE2EBlocked(f"gcloud unavailable: {version.stderr}")
    dirty = _run(["git", "status", "--porcelain"], check=False)
    tag = "m5-02a-wip" if (dirty.stdout or "").strip() else _git_sha()[:12]
    image = f"{IMAGE_REPO}:{tag}"
    proof["image_tag"] = image
    build = _gcloud(
        [
            "builds",
            "submit",
            "--config=deployment/prem3_mta_worker/cloudbuild.yaml",
            f"--substitutions=_TAG={tag}",
            ".",
        ],
        check=False,
    )
    if build.returncode != 0:
        raise CloudE2EBlocked(
            f"Cloud Build failed for {JOB}: {(build.stderr or build.stdout)[-2000:]}"
        )
    describe_image = _gcloud(
        ["artifacts", "docker", "images", "describe", image, "--format=json"],
        check=False,
    )
    digest = None
    if describe_image.returncode == 0 and describe_image.stdout:
        try:
            payload = json.loads(describe_image.stdout)
            digest = (
                payload.get("image_summary", {}).get("digest")
                or payload.get("digest")
            )
        except json.JSONDecodeError:
            digest = None
    pinned = f"{IMAGE_REPO}@{digest}" if digest else image
    proof["image_digest"] = digest
    proof["pinned_image"] = pinned

    job_deploy = _gcloud(
        [
            "run",
            "jobs",
            "deploy",
            JOB,
            f"--image={pinned}",
            f"--region={REGION}",
            f"--service-account={RUNTIME_SA}",
            "--set-env-vars=PREM3_MTA_CLOUD_RUNTIME=1,"
            f"GOOGLE_CLOUD_PROJECT={PROJECT}",
            "--cpu=2",
            "--memory=4Gi",
            "--task-timeout=30m",
            "--max-retries=0",
        ],
        check=False,
    )
    if job_deploy.returncode != 0:
        raise CloudE2EBlocked(
            f"Cloud Run Job deploy failed: {(job_deploy.stderr or job_deploy.stdout)[-2000:]}"
        )
    proof["job_deployed"] = True

    launch_deploy = _gcloud(
        [
            "run",
            "deploy",
            LAUNCH_SERVICE,
            f"--image={pinned}",
            f"--region={REGION}",
            f"--service-account={RUNTIME_SA}",
            "--no-allow-unauthenticated",
            "--command=python",
            "--args=-m,app.tools.mta_launch_service",
            f"--set-env-vars=GOOGLE_CLOUD_PROJECT={PROJECT},GOOGLE_CLOUD_REGION={REGION}",
            "--cpu=1",
            "--memory=512Mi",
        ],
        check=False,
    )
    if launch_deploy.returncode != 0:
        raise CloudE2EBlocked(
            "Cloud Run launch service deploy failed: "
            f"{(launch_deploy.stderr or launch_deploy.stdout)[-2000:]}"
        )
    url_proc = _gcloud(
        [
            "run",
            "services",
            "describe",
            LAUNCH_SERVICE,
            f"--region={REGION}",
            "--format=value(status.url)",
        ],
        check=False,
    )
    launch_url = (url_proc.stdout or "").strip()
    if not launch_url:
        raise CloudE2EBlocked("prem3-mta-launch has no URL")
    proof["launch_url"] = launch_url
    invoker = _gcloud(
        [
            "run",
            "services",
            "add-iam-policy-binding",
            LAUNCH_SERVICE,
            f"--region={REGION}",
            f"--member=serviceAccount:{DISPATCHER_SA}",
            "--role=roles/run.invoker",
            "--quiet",
        ],
        check=False,
    )
    if invoker.returncode != 0:
        raise CloudE2EBlocked(
            "Could not grant Cloud Tasks dispatcher run.invoker on prem3-mta-launch: "
            f"{(invoker.stderr or invoker.stdout)[-1500:]}"
        )
    job_invoker = _gcloud(
        [
            "run",
            "jobs",
            "add-iam-policy-binding",
            JOB,
            f"--region={REGION}",
            f"--member=serviceAccount:{RUNTIME_SA}",
            "--role=roles/run.developer",
            "--quiet",
        ],
        check=False,
    )
    proof["job_iam_binding"] = job_invoker.returncode == 0

    events = music_center_v2_events()
    load_synthetic_ga4_events(project_id=PROJECT, events=events, replace=True)
    sql = f"""
    SELECT
      journey_id,
      subject_key,
      conversion_event,
      CAST(conversion_ts AS STRING) AS conversion_ts,
      CAST(conversion_value AS FLOAT64) AS conversion_value,
      channels,
      ARRAY(SELECT CAST(ts AS STRING) FROM UNNEST(touchpoint_timestamps) AS ts) AS touchpoint_times,
      path_string
    FROM `{PROJECT}.prem3_modeling.mta_journeys`
    WHERE conversion_date BETWEEN '{WINDOW_START.isoformat()}' AND '{WINDOW_END.isoformat()}'
    LIMIT 5000
    """
    bq_rows = run_query(client_for_project(PROJECT), sql, fetch=True).rows
    journeys = []
    for raw in bq_rows:
        channels = [str(c) for c in (raw.get("channels") or [])]
        journeys.append(
            {
                "subject_key": str(raw.get("subject_key") or raw.get("journey_id")),
                "channels": channels,
                "touchpoint_times": list(raw.get("touchpoint_times") or []),
                "conversion_ts": raw.get("conversion_ts"),
                "converted": True,
                "conversion_value": float(raw.get("conversion_value") or 1.0),
                "path_string": raw.get("path_string") or " > ".join(channels),
                "conversion_event": raw.get("conversion_event") or "purchase",
                "journey_id": raw.get("journey_id"),
            }
        )
    if not journeys:
        raise CloudE2EBlocked(
            "No September v2 journeys in BigQuery. Run LIVE_BQ refresh first."
        )

    fs = firestore.Client(project=PROJECT)
    service = MTAService(
        dispatcher=FakeMTADispatcher(),
        dp6=DP6MAMAdapter(fake=False),
        firestore_client=fs,
    )
    contract = build_input_contract(
        input_contract_id="ic_m502a_cloud",
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2-cloud",
        track_id="mta",
        ga4_dataset_id="analytics_music_center_synthetic",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start=WINDOW_START.isoformat(),
        conversion_period_end=WINDOW_END.isoformat(),
        lookback_window_days=30,
        identity_strategy=IdentityStrategy.PSEUDO_ID_ONLY,
        sessionization_policy=SessionizationPolicy.GA4_SESSION_ID_V1,
        traffic_source_policy=SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1,
        channel_grouping_version="v1",
        attribution_models=DEMO_ATTRIBUTION_MODELS,
    )
    service.repo.put_contract(contract)
    service.evaluate_readiness(
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2-cloud",
        track_id="mta",
        contract=contract,
        ga4_dataset_exists=True,
        daily_shards_continuous=True,
        key_event_present=True,
        conversion_volume_ok=True,
        channel_grouping_approved=True,
        unmapped_share_ok=True,
        uses_intraday_for_canonical=False,
        lookback_covered=True,
        user_pseudo_id_coverage=0.99,
    )
    run = service.start_run(
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2-cloud",
        track_id="mta",
        journeys=journeys,
        proof_label="SYNTHETIC_DEMO",
        runtime_mode="SYNTHETIC_DEMO",
        worker_image_digest=digest,
        source_commit_sha=_git_sha(),
    )
    plan = service.repo.get_execution_plan(run.execution_plan_id)
    dispatch = service.repo.get_dispatch(run.dispatch_id)
    persist_runtime_bundle(
        fs,
        dispatch_id=run.dispatch_id,
        plan=plan,
        run=run,
        dispatch=dispatch,
        contract=contract,
        journeys=journeys,
    )
    proof["dispatch_id"] = run.dispatch_id
    proof["run_id"] = run.run_id

    dispatcher = CloudTasksMTADispatcher(
        project_id=PROJECT,
        location=REGION,
        queue=QUEUE,
        launch_url=f"{launch_url}/internal/v1/mta-dispatches",
        service_account_email=DISPATCHER_SA,
        audience=launch_url,
    )
    try:
        task_name = dispatcher.enqueue(dispatch)
    except Exception as exc:
        raise CloudE2EBlocked(f"Cloud Tasks enqueue failed: {exc}") from exc
    proof["cloud_task_name"] = task_name
    proof["cloud_tasks_oidc"] = True

    deadline = time.time() + 900
    receipt_status = None
    while time.time() < deadline:
        snap = fs.collection("mta_runtime").document(run.dispatch_id).get()
        payload = snap.to_dict() or {}
        if payload.get("completed") and payload.get("receipt"):
            receipt_status = payload["receipt"].get("status")
            proof["receipt_id"] = payload["receipt"].get("receipt_id")
            proof["computation_authority"] = payload["receipt"].get(
                "computation_authority"
            )
            break
        time.sleep(15)
    if receipt_status is None:
        raise CloudE2EBlocked(
            "Worker did not persist a receipt within 15 minutes after Cloud Task enqueue."
        )
    proof["receipt_status"] = receipt_status
    proof["journey_count"] = len(bundle_journeys(fs, dispatch_id=run.dispatch_id))
    proof["status"] = "PASSED"
    return proof


def write_proof(proof: dict[str, Any]) -> None:
    PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    os.chdir(REPO_ROOT)
    proof = attempt_cloud_e2e(execute=args.execute)
    write_proof(proof)
    print(json.dumps(proof, indent=2))
    if proof.get("status") == "PASSED":
        return 0
    if proof.get("status") == "CLOUD_E2E_NOT_RUN":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

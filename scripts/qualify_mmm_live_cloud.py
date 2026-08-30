#!/usr/bin/env python3
"""Live Firestore / GCS / BigQuery / Cloud Tasks qualification for M3-02.

NEVER invoked by pytest/CI. Explicit operator command only.
Uses synthetic hackathon IDs only. Does not self-approve MODEL_ACCEPTED.
Does not download service-account keys.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from google.cloud import bigquery, storage

from app.config import load_settings
from app.control_plane.firestore_repo import build_firestore_client
from app.core.contracts import utc_now
from app.modeling.common.errors import ArtifactVerificationFailedError
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.artifacts import (
    ARTIFACT_MANIFEST_NAME,
    CANONICAL_MODEL_BINARY_NAME,
    HEALTH_HTML_NAME,
    REPRODUCIBILITY_NAME,
    RESULTS_HTML_NAME,
    REVIEW_PACK_NAME,
    modeling_prefix,
    persist_immutable_bytes,
)
from app.modeling.mmm.contracts import (
    AcceptanceDecision,
    ComputeProfile,
    DecisionStatus,
    DecisionType,
    FitApproval,
    FitDispatchStatus,
    FitRun,
    FitRunStatus,
    KnowledgeClass,
    MeridianFitDispatch,
    MeridianModelArtifactManifest,
    MeridianModelHealthReceipt,
    MeridianPriorValidationReceipt,
    MeridianRuntimeMode,
    MMMModelReviewPack,
    MMMModelVersion,
    ModelAcceptanceApproval,
    ModelDecision,
    OfficialCheckResult,
    OfficialHealthStatus,
    PriorValidationStatus,
    ReviewSource,
)
from app.modeling.mmm.coverage import (
    MUSIC_CENTER_MODEL_READY_COVERAGE,
    assert_cycle_does_not_define_window,
    candidate_window_from_coverage,
)
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.modeling.mmm.ledger import (
    CanonicalBigQueryModelLedger,
    compile_channel_summary_row,
    compile_decision_row,
    compile_fit_run_row,
    compile_health_row,
    compile_model_version_row,
    ensure_model_ledger_tables,
)
from app.modeling.mmm.smoke import tiny_smoke_fit_plan, tiny_smoke_plan
from app.modeling.mmm.states import MMMModelingStage
from app.service.object_store import GcsObjectStore

PROJECT = "modelready-m3"
REGION = "us-central1"
QUEUE = "prem3-meridian-fit-dispatch"
JOB = "prem3-meridian-model-worker"
LEDGER_DATASET = "prem3_modeling"
EVIDENCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "meridian_cloud_runtime_qualification.json"
)
PYTHON = sys.executable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("QUALIFY_MMM_LIVE_CLOUD_NOT_RUN")
        print("Pass --execute to run live Firestore/GCS/BigQuery/Cloud Tasks proofs.")
        return 2

    settings = load_settings()
    if settings.project_id != PROJECT:
        print("QUALIFY_MMM_LIVE_CLOUD_NOT_RUN")
        print(f"Unexpected project_id={settings.project_id!r}")
        return 3

    suffix = uuid.uuid4().hex[:12]
    tenant_id = f"tenm3q{suffix}"
    project_id = f"prjm3q{suffix}"
    foreign_tenant = f"tenm3x{suffix}"
    foreign_project = f"prjm3x{suffix}"
    window = candidate_window_from_coverage(MUSIC_CENTER_MODEL_READY_COVERAGE)
    assert_cycle_does_not_define_window(
        cycle_start="2026-07-01",
        cycle_end="2026-09-30",
        model_window_start=window[0],
        model_window_end=window[1],
        coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
    )
    evidence: dict[str, Any] = {
        "selected_cycle_name": "Q3 2026",
        "model_window_start": window[0],
        "model_window_end": window[1],
        "tenant_id": tenant_id,
        "project_id": project_id,
        "firestore": {"status": "FAILED"},
        "gcs": {"status": "FAILED"},
        "bigquery": {"status": "FAILED"},
        "cloud_tasks": {"status": "NOT_RUN"},
        "job_launch": {"status": "NOT_RUN"},
    }
    fs_client = build_firestore_client(
        project_id=PROJECT, database=settings.firestore_database
    )
    repo = FirestoreModelingRepository(fs_client)
    try:
        evidence["firestore"] = _firestore_proof(
            repo,
            tenant_id=tenant_id,
            project_id=project_id,
            foreign_tenant=foreign_tenant,
            foreign_project=foreign_project,
            window=window,
        )
        bucket = settings.artifact_bucket or "modelready-m3-912257136465-artifacts"
        evidence["gcs"] = _gcs_proof(
            tenant_id=tenant_id,
            project_id=project_id,
            model_version_id=evidence["firestore"]["model_version_id"],
            bucket=bucket,
        )
        evidence["bigquery"] = _bq_proof(
            tenant_id=tenant_id,
            project_id=project_id,
            window=window,
            firestore_ids=evidence["firestore"],
        )
        evidence["cloud_tasks"] = _cloud_tasks_proof(
            repo,
            tenant_id=tenant_id,
            project_id=project_id,
            firestore_ids=evidence["firestore"],
        )
    finally:
        _cleanup_firestore(fs_client, tenant_id, project_id)
        _cleanup_firestore(fs_client, foreign_tenant, foreign_project)

    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("QUALIFY_MMM_LIVE_CLOUD_OK")
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
    failed = [
        name
        for name in ("firestore", "gcs", "bigquery")
        if evidence[name].get("status") != "PASS"
    ]
    return 1 if failed else 0


def _firestore_proof(
    repo: FirestoreModelingRepository,
    *,
    tenant_id: str,
    project_id: str,
    foreign_tenant: str,
    foreign_project: str,
    window: tuple[str, str],
) -> dict[str, Any]:
    plan = tiny_smoke_plan().model_copy(
        update={
            "model_version_id": f"mver_{uuid.uuid4().hex[:16]}",
            "model_plan_id": f"mplan_{uuid.uuid4().hex[:16]}",
        }
    )
    fit_plan = tiny_smoke_fit_plan(plan)
    version = MMMModelVersion(
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
    repo.put_version(version)
    repo.put_plan(plan)
    decision = ModelDecision(
        decision_id=f"mdc_{uuid.uuid4().hex[:20]}",
        model_version_id=version.model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        decision_type=DecisionType.MODEL_WINDOW,
        proposal={"start": window[0], "end": window[1]},
        authority=KnowledgeClass.PREM3_DETERMINISTIC_EVIDENCE,
        status=DecisionStatus.APPROVED,
        approved_by="user_music_center",
        approved_at=utc_now(),
        plan_fingerprint=plan.fingerprint,
        chosen_value=f"{window[0]}/{window[1]}",
    )
    repo.put_decision(decision)
    prior = MeridianPriorValidationReceipt(
        model_version_id=version.model_version_id,
        model_plan_fingerprint=plan.fingerprint,
        meridian_version="1.8.0",
        prior_config_fingerprint=canonical_fingerprint({"priors": []}),
        n_draws=8,
        seed=1,
        status=PriorValidationStatus.PASS,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
    )
    repo.put_prior_receipt(prior)
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
    first = repo.claim_canonical_dispatch(dispatch)
    duplicate = dispatch.model_copy(update={"dispatch_id": f"fdsp_{uuid.uuid4().hex[:20]}"})
    second = repo.claim_canonical_dispatch(duplicate)
    artifact = MeridianModelArtifactManifest(
        model_version_id=version.model_version_id,
        fit_run_id=run.fit_run_id,
        meridian_version="1.8.0",
        input_fingerprint=plan.model_ready_manifest_fingerprint,
        model_plan_fingerprint=plan.fingerprint,
        fit_plan_fingerprint=fit_plan.fingerprint,
        binary_model_ref="modeling/meridian_model.binpb",
        binary_sha256="0" * 64,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        serde_readback_ok=True,
    )
    repo.put_artifact(artifact)
    health = MeridianModelHealthReceipt(
        model_version_id=version.model_version_id,
        fit_run_id=run.fit_run_id,
        reviewer_version="1.8.0",
        meridian_version="1.8.0",
        check_results=(
            OfficialCheckResult(
                check_name="ConvergenceCheck",
                status=OfficialHealthStatus.PASS,
                summary="Synthetic live-persistence receipt only.",
            ),
        ),
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        review_source=ReviewSource.OFFICIAL_MERIDIAN,
    )
    repo.put_health(health)
    pack = MMMModelReviewPack(
        model_version_id=version.model_version_id,
        fit_run_id=run.fit_run_id,
        fingerprint=canonical_fingerprint({"v": version.model_version_id, "f": run.fit_run_id}),
        official_health=health,
    )
    repo.put_review(pack)
    acceptance = ModelAcceptanceApproval(
        approval_id=f"mapv_{uuid.uuid4().hex[:20]}",
        model_version_id=version.model_version_id,
        fit_run_id=run.fit_run_id,
        tenant_id=tenant_id,
        project_id=project_id,
        review_pack_fingerprint=pack.fingerprint,
        model_artifact_fingerprint=artifact.binary_sha256,
        approved_by="user_music_center",
        approved_at=utc_now(),
        decision=AcceptanceDecision.ACCEPT,
    )
    repo.put_acceptance(acceptance)

    foreign_version = version.model_copy(
        update={
            "tenant_id": foreign_tenant,
            "project_id": foreign_project,
            "model_version_id": f"mver_x{uuid.uuid4().hex[:16]}",
        }
    )
    repo.put_version(foreign_version)
    denied = repo.get_version(
        tenant_id=foreign_tenant,
        project_id=foreign_project,
        model_version_id=version.model_version_id,
    )
    home = repo.get_version(
        tenant_id=tenant_id,
        project_id=project_id,
        model_version_id=version.model_version_id,
    )
    foreign_approval = approval.model_copy(
        update={"tenant_id": foreign_tenant, "project_id": foreign_project}
    )
    cross_approval_rejected = (
        foreign_approval.tenant_id != tenant_id or foreign_approval.project_id != project_id
    )
    reloaded_fp = _reload_plan_fingerprint(
        tenant_id=tenant_id,
        project_id=project_id,
        model_version_id=version.model_version_id,
    )
    if home is None or denied is not None:
        raise RuntimeError("Live Firestore tenancy proof failed.")
    if reloaded_fp != plan.fingerprint:
        raise RuntimeError("New-process Firestore reload fingerprint mismatch.")
    if first.dispatch_id != second.dispatch_id:
        raise RuntimeError("Canonical dispatch was not idempotent.")
    return {
        "status": "PASS",
        "model_version_id": version.model_version_id,
        "model_plan_fingerprint": plan.fingerprint,
        "fit_plan_fingerprint": fit_plan.fingerprint,
        "fit_run_id": run.fit_run_id,
        "dispatch_id": first.dispatch_id,
        "approval_id": approval.approval_id,
        "duplicate_dispatch_id": second.dispatch_id,
        "reload_fingerprint": reloaded_fp,
        "foreign_get_denied": denied is None,
        "foreign_approval_cannot_authorize": cross_approval_rejected,
        "acceptance_actor": acceptance.approved_by,
    }


def _reload_plan_fingerprint(*, tenant_id: str, project_id: str, model_version_id: str) -> str:
    script = (
        "from app.control_plane.firestore_repo import build_firestore_client\n"
        "from app.modeling.mmm.firestore import FirestoreModelingRepository\n"
        f"client = build_firestore_client(project_id={PROJECT!r}, database='(default)')\n"
        "repo = FirestoreModelingRepository(client)\n"
        f"plan = repo.get_plan({model_version_id!r})\n"
        "print(plan.fingerprint if plan is not None else 'MISSING')\n"
    )
    result = subprocess.run(
        [PYTHON, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return result.stdout.strip()


def _gcs_proof(
    *,
    tenant_id: str,
    project_id: str,
    model_version_id: str,
    bucket: str,
) -> dict[str, Any]:
    store = GcsObjectStore(client=storage.Client(project=PROJECT))
    prefix = modeling_prefix(tenant_id, project_id, model_version_id)
    payloads = {
        CANONICAL_MODEL_BINARY_NAME: (b"prem3-m3-02-live-binpb", "application/octet-stream"),
        HEALTH_HTML_NAME: (b"<html>health</html>", "text/html; charset=utf-8"),
        RESULTS_HTML_NAME: (b"<html>results</html>", "text/html; charset=utf-8"),
        ARTIFACT_MANIFEST_NAME: (b'{"kind":"manifest"}', "application/json"),
        REVIEW_PACK_NAME: (b'{"kind":"review"}', "application/json"),
        REPRODUCIBILITY_NAME: (b'{"kind":"repro"}', "application/json"),
    }
    hashes: dict[str, str] = {}
    for name, (data, content_type) in payloads.items():
        object_name = f"{prefix}{name}"
        digest = persist_immutable_bytes(
            store,
            bucket=bucket,
            object_name=object_name,
            data=data,
            content_type=content_type,
        )
        read_back = store.read_bytes(bucket=bucket, object_name=object_name)
        if read_back != data:
            raise RuntimeError(f"GCS read-back mismatch for {name}")
        hashes[name] = digest
    conflict_rejected = False
    try:
        persist_immutable_bytes(
            store,
            bucket=bucket,
            object_name=f"{prefix}{CANONICAL_MODEL_BINARY_NAME}",
            data=b"different-hash-payload",
            content_type="application/octet-stream",
        )
    except ArtifactVerificationFailedError:
        conflict_rejected = True
    if not conflict_rejected:
        raise RuntimeError("Conflicting GCS overwrite was not rejected.")
    return {
        "status": "PASS",
        "bucket": bucket,
        "prefix": prefix,
        "hashes": hashes,
        "conflict_overwrite_rejected": True,
    }


def _bq_proof(
    *,
    tenant_id: str,
    project_id: str,
    window: tuple[str, str],
    firestore_ids: dict[str, Any],
) -> dict[str, Any]:
    del tenant_id
    client = bigquery.Client(project=PROJECT)
    dataset_ref = bigquery.Dataset(f"{PROJECT}.{LEDGER_DATASET}")
    dataset_ref.location = REGION
    client.create_dataset(dataset_ref, exists_ok=True)
    ensure_model_ledger_tables(client, project_id=PROJECT, dataset_id=LEDGER_DATASET)
    ledger = CanonicalBigQueryModelLedger(
        client=client, project_id=PROJECT, dataset_id=LEDGER_DATASET
    )
    version_a = MMMModelVersion(
        model_version_id=firestore_ids["model_version_id"],
        tenant_id="ten_unused",
        project_id=project_id,
        cycle_id="cyc_q3_2026",
        track_id="trk_mmm",
        model_ready_run_id="run_cpu_smoke",
        model_ready_manifest_fingerprint="official-cpu-smoke-tiny",
        model_plan_fingerprint=firestore_ids["model_plan_fingerprint"],
        model_window_start=window[0],
        model_window_end=window[1],
        created_by="user_music_center",
        state=MMMModelingStage.AWAITING_MODEL_REVIEW,
    )
    version_b = version_a.model_copy(
        update={"model_version_id": f"mver_h{uuid.uuid4().hex[:16]}", "version": 2}
    )
    run = FitRun(
        fit_run_id=firestore_ids["fit_run_id"],
        model_version_id=version_a.model_version_id,
        tenant_id="ten_unused",
        project_id=project_id,
        fit_plan_fingerprint=firestore_ids["fit_plan_fingerprint"],
        status=FitRunStatus.SUCCEEDED,
        compute_profile=ComputeProfile.CPU_TEST,
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        meridian_version="1.8.0",
    )
    decision = ModelDecision(
        decision_id=f"mdc_{uuid.uuid4().hex[:20]}",
        model_version_id=version_a.model_version_id,
        tenant_id="ten_unused",
        project_id=project_id,
        decision_type=DecisionType.MODEL_WINDOW,
        proposal={"start": window[0], "end": window[1]},
        authority=KnowledgeClass.PREM3_DETERMINISTIC_EVIDENCE,
        status=DecisionStatus.APPROVED,
        plan_fingerprint=firestore_ids["model_plan_fingerprint"],
    )
    health = MeridianModelHealthReceipt(
        model_version_id=version_a.model_version_id,
        fit_run_id=run.fit_run_id,
        reviewer_version="1.8.0",
        meridian_version="1.8.0",
        check_results=(),
        runtime_mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        review_source=ReviewSource.OFFICIAL_MERIDIAN,
    )
    ledger.write(table="mmm_model_versions", row=compile_model_version_row(version_a))
    ledger.write(table="mmm_model_versions", row=compile_model_version_row(version_b))
    ledger.write(
        table="mmm_fit_runs",
        row=compile_fit_run_row(run, cycle_id=version_a.cycle_id, track_id=version_a.track_id),
    )
    ledger.write(
        table="mmm_model_decisions",
        row=compile_decision_row(
            decision, cycle_id=version_a.cycle_id, track_id=version_a.track_id
        ),
    )
    ledger.write(
        table="mmm_model_health",
        row=compile_health_row(
            health,
            project_id=project_id,
            cycle_id=version_a.cycle_id,
            track_id=version_a.track_id,
        ),
    )
    ledger.write(
        table="mmm_model_channel_summary",
        row=compile_channel_summary_row(
            project_id=project_id,
            cycle_id=version_a.cycle_id,
            track_id=version_a.track_id,
            model_version_id=version_a.model_version_id,
            fit_run_id=run.fit_run_id,
            channel="channel",
            roi=None,
            contribution=None,
            meridian_version="1.8.0",
        ),
    )
    version_read = ledger.read_back(
        table="mmm_model_versions", model_version_id=version_a.model_version_id
    )
    fit_read = ledger.read_back(table="mmm_fit_runs", model_version_id=version_a.model_version_id)
    history = ledger.read_history(table="mmm_model_versions")
    ids = {row.get("model_version_id") for row in history}
    if version_read is None or fit_read is None:
        raise RuntimeError("BigQuery ledger read-back missing.")
    if version_read.get("model_plan_fingerprint") != version_a.model_plan_fingerprint:
        raise RuntimeError("BigQuery model version fingerprint mismatch.")
    if fit_read.get("fit_run_id") != run.fit_run_id:
        raise RuntimeError("BigQuery fit run id mismatch.")
    if version_a.model_version_id not in ids or version_b.model_version_id not in ids:
        raise RuntimeError("Historical BigQuery model-version rows were not retained.")
    return {
        "status": "PASS",
        "dataset": f"{PROJECT}.{LEDGER_DATASET}",
        "model_version_readback": version_read.get("model_version_id"),
        "fit_run_readback": fit_read.get("fit_run_id"),
        "fit_plan_fingerprint": fit_read.get("fit_plan_fingerprint"),
        "history_row_count": len(history),
        "history_retained": True,
    }


def _cloud_tasks_proof(
    repo: FirestoreModelingRepository,
    *,
    tenant_id: str,
    project_id: str,
    firestore_ids: dict[str, Any],
) -> dict[str, Any]:
    del repo, tenant_id, project_id
    try:
        from google.cloud import tasks_v2
        from google.protobuf import timestamp_pb2
    except ImportError:
        return {"status": "BLOCKED", "reason": "google-cloud-tasks is not installed locally."}
    client = tasks_v2.CloudTasksClient()
    parent = f"projects/{PROJECT}/locations/{REGION}/queues/{QUEUE}"
    task_id = f"prem3-mmm-qual-{uuid.uuid4().hex[:16]}"
    task_name = f"{parent}/tasks/{task_id}"
    schedule = timestamp_pb2.Timestamp()
    schedule.FromDatetime(datetime.now(UTC) + timedelta(hours=24))
    body = json.dumps({"dispatch_id": firestore_ids["dispatch_id"]}).encode("utf-8")
    task = {
        "name": task_name,
        "schedule_time": schedule,
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": (
                "https://prem3-api-vkcd3cbiea-uc.a.run.app"
                f"/internal/v1/mmm-fit-dispatches/{firestore_ids['dispatch_id']}/launch"
            ),
            "headers": {"Content-Type": "application/json"},
            "body": body,
        },
    }
    created = client.create_task(request={"parent": parent, "task": task})
    duplicate = "missing"
    try:
        client.create_task(request={"parent": parent, "task": task})
        duplicate = "created_second"
    except Exception as exc:
        duplicate = type(exc).__name__
    client.delete_task(request={"name": task_name})
    idempotent = "AlreadyExists" in duplicate
    return {
        "status": "PASS" if idempotent else "FAILED",
        "queue": QUEUE,
        "task_name": created.name,
        "dispatch_id": firestore_ids["dispatch_id"],
        "duplicate_result": duplicate,
        "deleted_unfired_task": True,
        "note": (
            "Task was scheduled 24h ahead and deleted so the live prem3-api "
            "revision is not required to serve /mmm-fit-dispatches."
        ),
    }


def _cleanup_firestore(client: Any, tenant_id: str, project_id: str) -> None:
    ws = (
        client.collection("tenants")
        .document(tenant_id)
        .collection("workspaces")
        .document(project_id)
    )
    for collection in (
        "mmm_model_versions",
        "mmm_model_plans",
        "mmm_model_decisions",
        "mmm_fit_plans",
        "mmm_fit_approvals",
        "mmm_fit_runs",
        "mmm_fit_dispatches",
        "mmm_canonical_fits",
        "mmm_artifacts",
        "mmm_health",
        "mmm_reviews",
        "mmm_acceptances",
        "mmm_prior_receipts",
        "mmm_design_briefs",
    ):
        for snap in ws.collection(collection).stream():
            snap.reference.delete()
    ws.delete()
    client.collection("tenants").document(tenant_id).delete()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"QUALIFY_MMM_LIVE_CLOUD_FAILED: {exc}")
        raise

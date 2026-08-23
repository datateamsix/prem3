#!/usr/bin/env python3
"""Provision Cloud Tasks queue, dispatcher SA, and least-privilege IAM for M2-13.

NEVER invoked by pytest/CI. Explicit operator command only.
Does not grant Owner or Editor.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

PROJECT = "modelready-m3"
REGION = "us-central1"
QUEUE = "prem3-evaluation-dispatch"
JOB = "prem3-evaluation-worker"
RUNTIME_SA = f"m3-runtime@{PROJECT}.iam.gserviceaccount.com"
DISPATCHER_SA = f"prem3-evaluation-dispatcher@{PROJECT}.iam.gserviceaccount.com"
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("PROVISION_EVALUATION_DISPATCH_NOT_RUN")
        print("Pass --execute to create the queue, dispatcher SA, and IAM grants.")
        return 2

    grants: list[str] = []
    _gcloud(["services", "enable", "cloudtasks.googleapis.com", f"--project={PROJECT}"])
    _ensure_sa()
    grants.append(f"serviceAccount:{DISPATCHER_SA} Cloud Tasks OIDC identity only")
    _ensure_queue()
    _grant(
        [
            "tasks",
            "queues",
            "add-iam-policy-binding",
            QUEUE,
            f"--location={REGION}",
            f"--project={PROJECT}",
            f"--member=serviceAccount:{RUNTIME_SA}",
            "--role=roles/cloudtasks.enqueuer",
        ]
    )
    grants.append(
        f"serviceAccount:{RUNTIME_SA} roles/cloudtasks.enqueuer "
        f"on projects/{PROJECT}/locations/{REGION}/queues/{QUEUE}"
    )
    _grant(
        [
            "iam",
            "service-accounts",
            "add-iam-policy-binding",
            DISPATCHER_SA,
            f"--project={PROJECT}",
            f"--member=serviceAccount:{RUNTIME_SA}",
            "--role=roles/iam.serviceAccountUser",
        ]
    )
    grants.append(
        f"serviceAccount:{RUNTIME_SA} roles/iam.serviceAccountUser on {DISPATCHER_SA}"
    )
    _grant(
        [
            "run",
            "jobs",
            "add-iam-policy-binding",
            JOB,
            f"--region={REGION}",
            f"--project={PROJECT}",
            f"--member=serviceAccount:{RUNTIME_SA}",
            "--role=roles/run.jobsExecutorWithOverrides",
        ],
        allow_missing_job=True,
    )
    grants.append(
        f"serviceAccount:{RUNTIME_SA} roles/run.jobsExecutorWithOverrides "
        f"on job {JOB} (binding applied when the job exists)"
    )
    print("PROVISION_EVALUATION_DISPATCH_OK")
    print(f"queue={QUEUE}")
    print(f"location={REGION}")
    print("retry=max_attempts=8 min_backoff=10s max_backoff=300s max_concurrent=8")
    print("rate=max_dispatches_per_second=5")
    print("dispatch_deadline=60s (per task)")
    print(f"dispatcher_sa={DISPATCHER_SA}")
    for grant in grants:
        if grant:
            print(f"iam={grant}")
    return 0


def _ensure_sa() -> None:
    existing = _gcloud(
        ["iam", "service-accounts", "describe", DISPATCHER_SA, f"--project={PROJECT}"],
        check=False,
    )
    if existing.returncode == 0:
        return
    _gcloud(
        [
            "iam",
            "service-accounts",
            "create",
            "prem3-evaluation-dispatcher",
            f"--project={PROJECT}",
            "--display-name=PreM3 Evaluation Cloud Tasks OIDC identity",
        ]
    )


def _ensure_queue() -> None:
    existing = _gcloud(
        [
            "tasks",
            "queues",
            "describe",
            QUEUE,
            f"--location={REGION}",
            f"--project={PROJECT}",
        ],
        check=False,
    )
    if existing.returncode == 0:
        return
    _gcloud(
        [
            "tasks",
            "queues",
            "create",
            QUEUE,
            f"--location={REGION}",
            f"--project={PROJECT}",
            "--max-dispatches-per-second=5",
            "--max-concurrent-dispatches=8",
            "--max-attempts=8",
            "--min-backoff=10s",
            "--max-backoff=300s",
            "--max-retry-duration=1800s",
            "--max-doublings=4",
        ]
    )


def _grant(args: list[str], *, allow_missing_job: bool = False) -> None:
    result = _gcloud(args, check=False)
    if result.returncode == 0:
        return
    stderr = result.stderr or ""
    if allow_missing_job and ("NOT_FOUND" in stderr or "not found" in stderr.lower()):
        return
    sys.stderr.write(stderr)
    raise RuntimeError("IAM grant failed")


def _gcloud(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([GCLOUD, *args], check=check, capture_output=True, text=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"PROVISION_EVALUATION_DISPATCH_FAILED: {exc}")
        sys.exit(1)

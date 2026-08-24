#!/usr/bin/env python3
"""Build and deploy prem3-meridian-model-worker.

NEVER invoked by pytest/CI. Explicit operator command only.
Does not deploy over historical modelready-m3 or meridian-eda-worker.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT = "modelready-m3"
REGION = "us-central1"
JOB = "prem3-meridian-model-worker"
RUNTIME_SA = f"m3-runtime@{PROJECT}.iam.gserviceaccount.com"
IMAGE_REPO = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{JOB}"
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"
REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_SERVICE = "modelready-m3"
EDA_JOB = "meridian-eda-worker"

WORKER_ENV = {
    "GOOGLE_CLOUD_PROJECT": PROJECT,
    "GOOGLE_CLOUD_REGION": REGION,
    "PREM3_API_RUNTIME": "cloud",
    "FIRESTORE_DATABASE": "(default)",
    "M3_RUNTIME_SA": RUNTIME_SA,
    "MODELREADY_ENV": "demo",
    "MODELREADY_LOG_LEVEL": "INFO",
    "MODELREADY_RAW_BUCKET": "modelready-m3-912257136465-raw",
    "MODELREADY_ARTIFACT_BUCKET": "modelready-m3-912257136465-artifacts",
    "MODELREADY_BQ_OPS_DATASET": "modelready_ops",
    "MODELREADY_BQ_EXPERIENCE_DATASET": "modelready_experience",
    "MODELREADY_BQ_MODELS_DATASET": "modelready_models",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--cpu-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("DEPLOY_MERIDIAN_MODEL_WORKER_NOT_RUN")
        print("Pass --execute to build and deploy prem3-meridian-model-worker.")
        return 2

    os.chdir(REPO_ROOT)
    source_sha = _git_sha()
    historical_before = _historical_fingerprint()
    if not args.skip_build:
        _build(source_sha)
    image_uri = f"{IMAGE_REPO}:{source_sha}"
    digest = _image_digest(image_uri)
    resolved = f"{IMAGE_REPO}@{digest}" if digest else image_uri
    env = dict(WORKER_ENV)
    env["PREM3_WORKER_IMAGE_DIGEST"] = digest or source_sha
    try:
        _deploy(resolved, env, cpu_only=args.cpu_only)
    except RuntimeError as exc:
        print("LIVE_GPU_DEPLOY_BLOCKED")
        print(str(exc))
        raise
    historical_after = _historical_fingerprint()
    if historical_before != historical_after:
        print("DEPLOY_MERIDIAN_MODEL_WORKER_REFUSED")
        print("Historical modelready-m3 or meridian-eda-worker changed during deploy.")
        return 4
    describe = _job_describe()
    print("DEPLOY_MERIDIAN_MODEL_WORKER_OK")
    print(f"source_sha={source_sha}")
    print(f"image_uri={image_uri}")
    print(f"image_digest={digest}")
    print(f"job={JOB}")
    print(f"region={REGION}")
    print(f"service_account={RUNTIME_SA}")
    print("task_timeout=3600")
    print("max_retries=0")
    print("tasks=1")
    print("parallelism=1")
    print("cpu=4")
    print("memory=16Gi")
    if args.cpu_only:
        print("gpu=none")
        print("profile=CPU_FALLBACK")
    else:
        print("gpu=1")
        print("gpu_type=nvidia-l4")
        print("gpu_zonal_redundancy=disabled")
    spec = (
        (((describe.get("spec") or {}).get("template") or {}).get("spec") or {}).get(
            "template"
        )
        or {}
    ).get("spec") or {}
    image = ((spec.get("containers") or [{}])[0]).get("image")
    print(f"deployed_image={image}")
    return 0


def _gcloud(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([GCLOUD, *args], check=check, capture_output=True, text=True)


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _build(tag: str) -> None:
    config = (
        REPO_ROOT / "deployment" / "prem3_meridian_model_worker" / "cloudbuild.yaml"
    )
    result = _gcloud(
        [
            "builds",
            "submit",
            f"--config={config}",
            f"--project={PROJECT}",
            f"--substitutions=_TAG={tag}",
            "--quiet",
        ],
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "")
        sys.stderr.write(result.stdout or "")
        raise RuntimeError(f"Cloud Build failed: {(result.stderr or result.stdout or '')[:4000]}")


def _image_digest(image_uri: str) -> str:
    result = _gcloud(
        [
            "artifacts",
            "docker",
            "images",
            "describe",
            image_uri,
            f"--project={PROJECT}",
            "--format=value(image_summary.digest)",
        ],
        check=False,
    )
    return (result.stdout or "").strip()


def _deploy(image_uri: str, env: dict[str, str], *, cpu_only: bool) -> None:
    packed = ",".join(f"{key}={value}" for key, value in env.items())
    args = [
        "run",
        "jobs",
        "deploy",
        JOB,
        f"--project={PROJECT}",
        f"--region={REGION}",
        f"--image={image_uri}",
        f"--service-account={RUNTIME_SA}",
        "--tasks=1",
        "--parallelism=1",
        "--task-timeout=3600",
        "--max-retries=0",
        "--cpu=4",
        "--memory=16Gi",
        f"--set-env-vars={packed}",
        "--quiet",
    ]
    if not cpu_only:
        args.extend(
            [
                "--gpu=1",
                "--gpu-type=nvidia-l4",
                "--no-gpu-zonal-redundancy",
            ]
        )
    result = _gcloud(args, check=False)
    if result.returncode != 0:
        detail = result.stderr or result.stdout or "Cloud Run Job deploy failed"
        sys.stderr.write(detail)
        raise RuntimeError(detail)


def _job_describe() -> dict:
    result = _gcloud(
        [
            "run",
            "jobs",
            "describe",
            JOB,
            f"--project={PROJECT}",
            f"--region={REGION}",
            "--format=json",
        ]
    )
    return json.loads(result.stdout)


def _historical_fingerprint() -> dict[str, str]:
    adk = _gcloud(
        [
            "run",
            "services",
            "describe",
            HISTORICAL_SERVICE,
            f"--project={PROJECT}",
            f"--region={REGION}",
            "--format=json",
        ]
    )
    job = _gcloud(
        [
            "run",
            "jobs",
            "describe",
            EDA_JOB,
            f"--project={PROJECT}",
            f"--region={REGION}",
            "--format=json",
        ]
    )
    adk_json = json.loads(adk.stdout)
    job_json = json.loads(job.stdout)
    adk_spec = ((adk_json.get("spec") or {}).get("template") or {}).get("spec") or {}
    adk_image = ((adk_spec.get("containers") or [{}])[0]).get("image")
    job_spec = (
        (((job_json.get("spec") or {}).get("template") or {}).get("spec") or {}).get(
            "template"
        )
        or {}
    ).get("spec") or {}
    job_image = ((job_spec.get("containers") or [{}])[0]).get("image")
    return {
        "adk_revision": (adk_json.get("status") or {}).get("latestReadyRevisionName") or "",
        "adk_image": adk_image or "",
        "eda_image": job_image or "",
    }


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"DEPLOY_MERIDIAN_MODEL_WORKER_FAILED: {exc}")
        sys.exit(1)

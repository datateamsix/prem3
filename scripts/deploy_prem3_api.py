#!/usr/bin/env python3
"""Build and deploy the prem3-api Cloud Run service.

NEVER invoked by pytest/CI. Explicit operator command only.

Does not print secret values. Does not deploy over modelready-m3.
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
SERVICE = "prem3-api"
RUNTIME_SA = f"m3-runtime@{PROJECT}.iam.gserviceaccount.com"
IMAGE_REPO = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{SERVICE}"
GOOGLE_KMS_KEY = (
    f"projects/{PROJECT}/locations/{REGION}/keyRings/prem3/"
    "cryptoKeys/prem3-google-oauth-credentials"
)
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ENV_PATH = REPO_ROOT / "artifacts" / "deployment" / "prem3_api_runtime.env.yaml"
HISTORICAL_SERVICE = "modelready-m3"
EDA_JOB = "meridian-eda-worker"
EVALUATION_QUEUE = "prem3-evaluation-dispatch"
EVALUATION_JOB = "prem3-evaluation-worker"
DISPATCHER_SA = f"prem3-evaluation-dispatcher@{PROJECT}.iam.gserviceaccount.com"
DEFAULT_API_URL = "https://prem3-api-vkcd3cbiea-uc.a.run.app"

SECRET_ENV = {
    "CLERK_SECRET_KEY": "prem3-api-clerk-secret-key",
    "CLERK_WEBHOOK_SIGNING_SECRET": "prem3-api-clerk-webhook-signing-secret",
    "STRIPE_SECRET_KEY": "prem3-api-stripe-secret-key",
    "STRIPE_WEBHOOK_SECRET": "prem3-api-stripe-webhook-secret",
    "GOOGLE_OAUTH_CLIENT_SECRET": "prem3-api-google-oauth-client-secret",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument(
        "--no-traffic",
        action="store_true",
        help="Create a candidate revision without sending production traffic.",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        print("DEPLOY_PREM3_API_NOT_RUN")
        print("Pass --execute to build and deploy prem3-api.")
        return 2

    os.chdir(REPO_ROOT)
    source_sha = _git_sha()
    historical_before = _historical_fingerprint()
    if not args.skip_build:
        _build(source_sha)
    image_uri = f"{IMAGE_REPO}:{source_sha}"
    digest = _image_digest(image_uri)
    secrets = _available_secrets()
    _deploy(
        image_uri=f"{IMAGE_REPO}@{digest}" if digest else image_uri,
        secrets=secrets,
        no_traffic=args.no_traffic,
    )
    historical_after = _historical_fingerprint()
    if historical_before != historical_after:
        print("DEPLOY_PREM3_API_REFUSED")
        print("Historical modelready-m3 or meridian-eda-worker changed during deploy.")
        return 4
    describe = _service_describe()
    status = describe.get("status") or {}
    revision = (
        status.get("latestCreatedRevisionName")
        if args.no_traffic
        else status.get("latestReadyRevisionName")
    ) or status.get("latestCreatedRevisionName")
    url = ((describe.get("status") or {}).get("url")) or ""
    spec = ((describe.get("spec") or {}).get("template") or {}).get("spec") or {}
    sa = spec.get("serviceAccountName")
    print("DEPLOY_PREM3_API_OK")
    print(f"source_sha={source_sha}")
    print(f"image_uri={image_uri}")
    print(f"image_digest={digest}")
    print(f"service={SERVICE}")
    print(f"revision={revision}")
    print(f"url={url}")
    print(f"region={REGION}")
    print(f"service_account={sa}")
    print(f"secrets_injected={','.join(sorted(secrets))}")
    return 0


def _gcloud(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([GCLOUD, *args], check=check, capture_output=True, text=True)


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _build(tag: str) -> None:
    result = _gcloud(
        [
            "builds",
            "submit",
            f"--config={REPO_ROOT / 'deployment' / 'prem3_api' / 'cloudbuild.yaml'}",
            f"--project={PROJECT}",
            f"--substitutions=_TAG={tag}",
            "--quiet",
        ],
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise RuntimeError("Cloud Build failed")


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


def _secret_exists(name: str) -> bool:
    result = _gcloud(["secrets", "describe", name, f"--project={PROJECT}"], check=False)
    return result.returncode == 0


def _available_secrets() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for env_name, secret_name in SECRET_ENV.items():
        if _secret_exists(secret_name):
            mapping[env_name] = f"{secret_name}:latest"
    return mapping


def _runtime_env_file() -> Path:
    dest = REPO_ROOT / "artifacts" / "deployment" / "prem3_api_runtime.generated.env.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = RUNTIME_ENV_PATH.read_text() if RUNTIME_ENV_PATH.is_file() else ""
    if "GOOGLE_KMS_KEY:" not in existing:
        existing = existing.rstrip() + f'\nGOOGLE_KMS_KEY: "{GOOGLE_KMS_KEY}"\n'
    launch_url = f"{DEFAULT_API_URL}/internal/v1/evaluation-dispatches"
    extras = {
        "EVALUATION_DISPATCH_QUEUE": EVALUATION_QUEUE,
        "EVALUATION_WORKER_JOB": EVALUATION_JOB,
        "EVALUATION_DISPATCHER_SA": DISPATCHER_SA,
        "EVALUATION_LAUNCH_URL": launch_url,
        "EVALUATION_LAUNCH_AUDIENCE": launch_url,
        "MERIDIAN_FIT_DISPATCH_QUEUE": "prem3-meridian-fit-dispatch",
        "MERIDIAN_MODEL_WORKER_JOB": "prem3-meridian-model-worker",
        "MERIDIAN_FIT_DISPATCHER_SA": DISPATCHER_SA,
        "MERIDIAN_FIT_LAUNCH_URL": f"{DEFAULT_API_URL}/internal/v1/mmm-fit-dispatches",
        "MERIDIAN_FIT_LAUNCH_AUDIENCE": f"{DEFAULT_API_URL}/internal/v1/mmm-fit-dispatches",
        "PREM3_SOURCE_COMMIT_SHA": _git_sha(),
    }
    for key, value in extras.items():
        if key == "PREM3_SOURCE_COMMIT_SHA":
            if "PREM3_SOURCE_COMMIT_SHA:" in existing:
                lines = [
                    (
                        f'PREM3_SOURCE_COMMIT_SHA: "{value}"'
                        if line.startswith("PREM3_SOURCE_COMMIT_SHA:")
                        else line
                    )
                    for line in existing.splitlines()
                ]
                existing = "\n".join(lines) + "\n"
            else:
                existing = existing.rstrip() + f'\nPREM3_SOURCE_COMMIT_SHA: "{value}"\n'
            continue
        if f"{key}:" not in existing:
            existing = existing.rstrip() + f'\n{key}: "{value}"\n'
    dest.write_text(existing)
    return dest


def _deploy(*, image_uri: str, secrets: dict[str, str], no_traffic: bool = False) -> None:
    args = [
        "run",
        "deploy",
        SERVICE,
        f"--project={PROJECT}",
        f"--region={REGION}",
        f"--image={image_uri}",
        f"--service-account={RUNTIME_SA}",
        "--no-invoker-iam-check",
        "--ingress=all",
        "--cpu=1",
        "--memory=1Gi",
        "--timeout=60",
        "--min-instances=0",
        "--max-instances=3",
        "--concurrency=80",
        "--startup-probe=httpGet.path=/health,periodSeconds=5,timeoutSeconds=3,failureThreshold=12",
        "--quiet",
    ]
    if no_traffic:
        args.append("--no-traffic")
        args.append("--tag=m303")
    args.append(f"--env-vars-file={_runtime_env_file()}")
    if secrets:
        packed = ",".join(f"{env}={ref}" for env, ref in secrets.items())
        args.append(f"--set-secrets={packed}")
    result = _gcloud(args, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise RuntimeError("Cloud Run deploy failed")


def _service_describe() -> dict:
    result = _gcloud(
        [
            "run",
            "services",
            "describe",
            SERVICE,
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
        (((job_json.get("spec") or {}).get("template") or {}).get("spec") or {}).get("template")
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
        print(f"DEPLOY_PREM3_API_FAILED: {exc}")
        sys.exit(1)

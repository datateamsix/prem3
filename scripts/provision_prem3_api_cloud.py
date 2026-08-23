#!/usr/bin/env python3
"""Provision Firestore IAM and Secret Manager resources for prem3-api.

NEVER invoked by pytest/CI. Explicit operator command only.

Does not print secret values. Does not create placeholder secrets.
Live-mode Stripe keys are refused.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import load_settings

PROJECT = "modelready-m3"
RUNTIME_SA = f"m3-runtime@{PROJECT}.iam.gserviceaccount.com"
RUNTIME_MEMBER = f"serviceAccount:{RUNTIME_SA}"
DATASTORE_ROLE = "roles/datastore.user"
SECRET_ACCESSOR_ROLE = "roles/secretmanager.secretAccessor"
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ENV_PATH = REPO_ROOT / "artifacts" / "deployment" / "prem3_api_runtime.env.yaml"

SECRET_ENV_MAP = {
    "prem3-api-clerk-secret-key": "CLERK_SECRET_KEY",
    "prem3-api-clerk-webhook-signing-secret": "CLERK_WEBHOOK_SIGNING_SECRET",
    "prem3-api-stripe-secret-key": "STRIPE_SECRET_KEY",
    "prem3-api-stripe-webhook-secret": "STRIPE_WEBHOOK_SECRET",
    "prem3-api-google-oauth-client-secret": "GOOGLE_OAUTH_CLIENT_SECRET",
}
DEFAULT_CLERK_AUTHORIZED_PARTIES = (
    "http://localhost:3000,https://set-sole-4153.clerk.accounts.dev"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("PROVISION_PREM3_API_NOT_RUN")
        print("Pass --execute to grant IAM and upsert available secrets.")
        return 2

    settings = load_settings()
    stripe_key = settings.stripe_secret_key or ""
    if stripe_key.startswith("sk_live_"):
        print("PROVISION_PREM3_API_REFUSED")
        print("Live-mode Stripe credentials are refused.")
        return 3

    grants: list[str] = []
    _grant_project_role(DATASTORE_ROLE)
    grants.append(f"{RUNTIME_MEMBER} {DATASTORE_ROLE} on project {PROJECT}")
    _verify_project_role(DATASTORE_ROLE)

    configured_secrets: list[str] = []
    skipped_secrets: list[str] = []
    for secret_name, env_name in SECRET_ENV_MAP.items():
        value = os.getenv(env_name) or ""
        if env_name == "STRIPE_SECRET_KEY":
            value = stripe_key
        elif env_name == "STRIPE_WEBHOOK_SECRET":
            value = settings.stripe_webhook_secret or ""
        elif env_name == "CLERK_SECRET_KEY":
            value = settings.clerk_secret_key or ""
        elif env_name == "CLERK_WEBHOOK_SIGNING_SECRET":
            value = settings.clerk_webhook_signing_secret or ""
        elif env_name == "GOOGLE_OAUTH_CLIENT_SECRET":
            value = settings.google_oauth_client_secret or ""
        if not value:
            skipped_secrets.append(secret_name)
            continue
        _upsert_secret(secret_name, value)
        _grant_secret_accessor(secret_name)
        _verify_secret_accessor(secret_name)
        configured_secrets.append(secret_name)

    _write_runtime_env(settings)
    print("PROVISION_PREM3_API_OK")
    print(f"runtime_sa={RUNTIME_SA}")
    print(f"datastore_role={DATASTORE_ROLE}")
    print("secrets_configured=" + ",".join(configured_secrets))
    print("secrets_skipped=" + ",".join(skipped_secrets))
    for grant in grants:
        print(f"iam_grant={grant}")
    print(f"runtime_env={RUNTIME_ENV_PATH.as_posix()}")
    return 0


def _gcloud(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [GCLOUD, *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _grant_project_role(role: str) -> None:
    result = _gcloud(
        [
            "projects",
            "add-iam-policy-binding",
            PROJECT,
            f"--member={RUNTIME_MEMBER}",
            f"--role={role}",
            "--condition=None",
            "--quiet",
        ],
        check=False,
    )
    if result.returncode != 0 and "already has" not in (result.stderr + result.stdout):
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "IAM grant failed")


def _verify_project_role(role: str) -> None:
    result = _gcloud(
        [
            "projects",
            "get-iam-policy",
            PROJECT,
            "--flatten=bindings[].members",
            f"--filter=bindings.members:{RUNTIME_MEMBER} AND bindings.role:{role}",
            "--format=value(bindings.role)",
        ]
    )
    roles = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if role not in roles:
        raise RuntimeError(f"Failed to verify {role} on {RUNTIME_SA}")


def _secret_exists(name: str) -> bool:
    result = _gcloud(["secrets", "describe", name, f"--project={PROJECT}"], check=False)
    return result.returncode == 0


def _upsert_secret(name: str, value: str) -> None:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    try:
        handle.write(value)
        handle.close()
        if not _secret_exists(name):
            created = _gcloud(
                [
                    "secrets",
                    "create",
                    name,
                    f"--project={PROJECT}",
                    "--replication-policy=automatic",
                    f"--data-file={handle.name}",
                ],
                check=False,
            )
            if created.returncode != 0:
                raise RuntimeError(created.stderr.strip() or "secret create failed")
        else:
            added = _gcloud(
                [
                    "secrets",
                    "versions",
                    "add",
                    name,
                    f"--project={PROJECT}",
                    f"--data-file={handle.name}",
                ],
                check=False,
            )
            if added.returncode != 0:
                raise RuntimeError(added.stderr.strip() or "secret version add failed")
    finally:
        Path(handle.name).unlink(missing_ok=True)


def _grant_secret_accessor(name: str) -> None:
    result = _gcloud(
        [
            "secrets",
            "add-iam-policy-binding",
            name,
            f"--project={PROJECT}",
            f"--member={RUNTIME_MEMBER}",
            f"--role={SECRET_ACCESSOR_ROLE}",
            "--quiet",
        ],
        check=False,
    )
    if result.returncode != 0 and "already has" not in (result.stderr + result.stdout):
        raise RuntimeError(result.stderr.strip() or "secret IAM grant failed")


def _verify_secret_accessor(name: str) -> None:
    result = _gcloud(
        [
            "secrets",
            "get-iam-policy",
            name,
            f"--project={PROJECT}",
            "--format=json",
        ]
    )
    policy = json.loads(result.stdout or "{}")
    for binding in policy.get("bindings", []):
        if binding.get("role") != SECRET_ACCESSOR_ROLE:
            continue
        if RUNTIME_MEMBER in (binding.get("members") or []):
            return
    raise RuntimeError(f"Failed to verify {SECRET_ACCESSOR_ROLE} on secret {name}")


def _yaml_value(value: str) -> str:
    return json.dumps(value)


def _read_existing_runtime_env() -> dict[str, str]:
    if not RUNTIME_ENV_PATH.is_file():
        return {}
    parsed: dict[str, str] = {}
    for line in RUNTIME_ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if not key:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw.strip().strip('"')
        parsed[key] = str(value)
    return parsed


def _write_runtime_env(settings) -> None:
    RUNTIME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    origin = settings.prem3_frontend_origin or "http://localhost:3000"
    rows: list[tuple[str, str]] = [
        ("GOOGLE_CLOUD_PROJECT", PROJECT),
        ("GOOGLE_CLOUD_REGION", "us-central1"),
        ("FIRESTORE_DATABASE", "(default)"),
        ("PREM3_API_RUNTIME", "cloud"),
        ("PREM3_FRONTEND_ORIGIN", origin),
        ("M3_RUNTIME_SA", RUNTIME_SA),
        ("MODELREADY_CLOUD_RUN_SERVICE", "prem3-api"),
        ("MODELREADY_ENV", "demo"),
        ("MODELREADY_LOG_LEVEL", "INFO"),
        ("WEBHOOK_CLAIM_LEASE_SECONDS", "120"),
        ("STRIPE_TIMEOUT_SECONDS", "10"),
        ("STRIPE_MAX_NETWORK_RETRIES", "2"),
    ]
    if settings.google_oauth_client_id:
        rows.append(("GOOGLE_OAUTH_CLIENT_ID", settings.google_oauth_client_id))
    if settings.google_oauth_redirect_uri:
        rows.append(("GOOGLE_OAUTH_REDIRECT_URI", settings.google_oauth_redirect_uri))
    prices = {
        "STRIPE_PRICE_PROJECT": settings.stripe_price_project or os.getenv("STRIPE_PRICE_PROJECT"),
        "STRIPE_PRICE_PORTFOLIO": settings.stripe_price_portfolio
        or os.getenv("STRIPE_PRICE_PORTFOLIO"),
        "STRIPE_PRICE_ENTERPRISE": settings.stripe_price_enterprise
        or os.getenv("STRIPE_PRICE_ENTERPRISE"),
    }
    for key, value in prices.items():
        if value:
            rows.append((key, value))
    if prices["STRIPE_PRICE_PROJECT"]:
        rows.extend(
            [
                ("STRIPE_CATALOG_CURRENCY", settings.stripe_catalog_currency or "usd"),
                (
                    "STRIPE_CATALOG_PROJECT_AMOUNT",
                    os.getenv("STRIPE_CATALOG_PROJECT_AMOUNT") or "9900",
                ),
                (
                    "STRIPE_CATALOG_PORTFOLIO_AMOUNT",
                    os.getenv("STRIPE_CATALOG_PORTFOLIO_AMOUNT") or "24900",
                ),
                (
                    "STRIPE_CATALOG_ENTERPRISE_AMOUNT",
                    os.getenv("STRIPE_CATALOG_ENTERPRISE_AMOUNT") or "99900",
                ),
                (
                    "STRIPE_CATALOG_PROJECT_DISPLAY_PRICE",
                    os.getenv("STRIPE_CATALOG_PROJECT_DISPLAY_PRICE") or "$99/mo",
                ),
                (
                    "STRIPE_CATALOG_PORTFOLIO_DISPLAY_PRICE",
                    os.getenv("STRIPE_CATALOG_PORTFOLIO_DISPLAY_PRICE") or "$249/mo",
                ),
                (
                    "STRIPE_CATALOG_ENTERPRISE_DISPLAY_PRICE",
                    os.getenv("STRIPE_CATALOG_ENTERPRISE_DISPLAY_PRICE") or "$999/mo",
                ),
            ]
        )
    parties = ",".join(settings.clerk_authorized_parties) or DEFAULT_CLERK_AUTHORIZED_PARTIES
    rows.append(("CLERK_AUTHORIZED_PARTIES", parties))
    merged = _read_existing_runtime_env()
    for key, value in rows:
        merged[key] = value
    text = "".join(f"{key}: {_yaml_value(value)}\n" for key, value in merged.items())
    RUNTIME_ENV_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

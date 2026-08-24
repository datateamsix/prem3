"""Environment-driven configuration for PreM3.

`M3_*` and `MODELREADY_*` environment variables are legacy/internal PreM3
execution configuration. Do not rename them solely for branding.

Infrastructure identifiers on Settings remain process-global. Customer identity
is request-scoped (`app.core.tenancy`) and is not derived from this module.

`MODELREADY_ORGANIZATION_ID` / `MODELREADY_WORKSPACE_ID` are developer/CLI
bootstrap inputs only (`app.core.developer_bootstrap`). They are not Settings
fields and never bind `require_tenant()` / `require_workspace()`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv_env(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _optional_int_env(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return int(raw.strip())


def _frontend_origin_env() -> str | None:
    return (
        os.getenv("PREM3_FRONTEND_ORIGIN")
        or os.getenv("STRIPE_FRONTEND_ORIGIN")
        or None
    )


def _optional_multiline_env(name: str) -> str | None:
    value = os.getenv(name) or None
    if value is None:
        return None
    return value.replace("\\n", "\n").strip() or None


def _apply_env_file() -> None:
    """Load repo `.env` into os.environ without overriding already-set variables."""
    candidates = (
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    )
    env_path = next((path for path in candidates if path.is_file()), None)
    if env_path is None:
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True, slots=True)
class Settings:
    project_id: str
    vertex_location: str
    cloud_region: str
    gemini_model: str
    agent_name: str
    raw_bucket: str | None
    artifact_bucket: str | None
    bq_ops_dataset: str
    bq_experience_dataset: str
    bq_models_dataset: str
    environment: str
    log_level: str
    runtime_sa: str | None
    cloud_run_service: str | None
    eda_job: str | None
    eda_job_timeout_seconds: int
    domain_view_registry_gs_uri: str | None
    firestore_database: str
    clerk_secret_key: str | None
    clerk_publishable_key: str | None
    clerk_webhook_signing_secret: str | None
    clerk_jwt_key: str | None
    clerk_authorized_parties: tuple[str, ...]
    clerk_api_timeout_seconds: int
    stripe_secret_key: str | None
    stripe_webhook_secret: str | None
    stripe_price_project: str | None
    stripe_price_portfolio: str | None
    stripe_price_enterprise: str | None
    stripe_catalog_project_amount: int | None
    stripe_catalog_portfolio_amount: int | None
    stripe_catalog_enterprise_amount: int | None
    stripe_catalog_currency: str | None
    stripe_catalog_project_display_price: str | None
    stripe_catalog_portfolio_display_price: str | None
    stripe_catalog_enterprise_display_price: str | None
    stripe_portal_configuration_id: str | None
    prem3_frontend_origin: str | None
    stripe_timeout_seconds: float
    stripe_max_network_retries: int
    webhook_claim_lease_seconds: int
    upload_signed_url_ttl_seconds: int
    upload_max_files: int
    upload_max_file_bytes: int
    upload_max_total_bytes: int
    google_oauth_client_id: str | None
    google_oauth_client_secret: str | None
    google_oauth_redirect_uri: str | None
    google_credential_vault_key: str | None
    google_kms_key: str | None
    google_oauth_ttl_seconds: int
    evaluation_dispatch_queue: str | None
    evaluation_worker_job: str | None
    evaluation_dispatcher_sa: str | None
    evaluation_launch_url: str | None
    evaluation_launch_audience: str | None
    meridian_fit_dispatch_queue: str | None
    meridian_model_worker_job: str | None
    meridian_fit_dispatcher_sa: str | None
    meridian_fit_launch_url: str | None
    meridian_fit_launch_audience: str | None
    meridian_model_worker_image: str | None
    meridian_model_gpu: str | None
    meridian_model_cpu: str | None
    meridian_model_memory: str | None
    meridian_model_timeout_seconds: int


def load_settings() -> Settings:
    """Load runtime settings without hard-coding cloud resource identifiers.

    GOOGLE_CLOUD_LOCATION is the Vertex AI / Gemini endpoint (often `global`).
    GOOGLE_CLOUD_REGION is Cloud Run / GCS / BigQuery / Firestore regional
    infrastructure. Firestore uses ``project_id``; ``FIRESTORE_DATABASE``
    selects the Native database ID (default ``(default)``).
    """
    _apply_env_file()
    return Settings(
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "modelready-m3"),
        vertex_location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        cloud_region=os.getenv("GOOGLE_CLOUD_REGION", "us-central1"),
        gemini_model=os.getenv("M3_GEMINI_MODEL", "gemini-2.5-flash"),
        agent_name=os.getenv("M3_AGENT_NAME", "modelready_m3"),
        raw_bucket=os.getenv("MODELREADY_RAW_BUCKET") or None,
        artifact_bucket=os.getenv("MODELREADY_ARTIFACT_BUCKET") or None,
        bq_ops_dataset=os.getenv("MODELREADY_BQ_OPS_DATASET", "modelready_ops"),
        bq_experience_dataset=os.getenv(
            "MODELREADY_BQ_EXPERIENCE_DATASET", "modelready_experience"
        ),
        bq_models_dataset=os.getenv("MODELREADY_BQ_MODELS_DATASET", "modelready_models"),
        environment=os.getenv("MODELREADY_ENV", "dev"),
        log_level=os.getenv("MODELREADY_LOG_LEVEL", "INFO"),
        runtime_sa=os.getenv("M3_RUNTIME_SA") or None,
        cloud_run_service=os.getenv("MODELREADY_CLOUD_RUN_SERVICE") or None,
        eda_job=os.getenv("MODELREADY_EDA_JOB") or None,
        eda_job_timeout_seconds=int(os.getenv("MODELREADY_EDA_JOB_TIMEOUT", "3300")),
        domain_view_registry_gs_uri=os.getenv("MODELREADY_DOMAIN_VIEW_REGISTRY_GS_URI")
        or None,
        firestore_database=os.getenv("FIRESTORE_DATABASE", "(default)"),
        clerk_secret_key=os.getenv("CLERK_SECRET_KEY") or None,
        clerk_publishable_key=os.getenv("CLERK_PUBLISHABLE_KEY") or None,
        clerk_webhook_signing_secret=os.getenv("CLERK_WEBHOOK_SIGNING_SECRET") or None,
        clerk_jwt_key=_optional_multiline_env("CLERK_JWT_KEY"),
        clerk_authorized_parties=_csv_env("CLERK_AUTHORIZED_PARTIES"),
        clerk_api_timeout_seconds=int(os.getenv("CLERK_API_TIMEOUT_SECONDS", "5")),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY") or None,
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET") or None,
        stripe_price_project=os.getenv("STRIPE_PRICE_PROJECT") or None,
        stripe_price_portfolio=os.getenv("STRIPE_PRICE_PORTFOLIO") or None,
        stripe_price_enterprise=os.getenv("STRIPE_PRICE_ENTERPRISE") or None,
        stripe_catalog_project_amount=_optional_int_env("STRIPE_CATALOG_PROJECT_AMOUNT"),
        stripe_catalog_portfolio_amount=_optional_int_env("STRIPE_CATALOG_PORTFOLIO_AMOUNT"),
        stripe_catalog_enterprise_amount=_optional_int_env(
            "STRIPE_CATALOG_ENTERPRISE_AMOUNT"
        ),
        stripe_catalog_currency=(os.getenv("STRIPE_CATALOG_CURRENCY") or None),
        stripe_catalog_project_display_price=(
            os.getenv("STRIPE_CATALOG_PROJECT_DISPLAY_PRICE") or None
        ),
        stripe_catalog_portfolio_display_price=(
            os.getenv("STRIPE_CATALOG_PORTFOLIO_DISPLAY_PRICE") or None
        ),
        stripe_catalog_enterprise_display_price=(
            os.getenv("STRIPE_CATALOG_ENTERPRISE_DISPLAY_PRICE") or None
        ),
        stripe_portal_configuration_id=os.getenv("STRIPE_PORTAL_CONFIGURATION_ID") or None,
        prem3_frontend_origin=_frontend_origin_env(),
        stripe_timeout_seconds=float(os.getenv("STRIPE_TIMEOUT_SECONDS", "10")),
        stripe_max_network_retries=int(os.getenv("STRIPE_MAX_NETWORK_RETRIES", "2")),
        webhook_claim_lease_seconds=int(os.getenv("WEBHOOK_CLAIM_LEASE_SECONDS", "120")),
        upload_signed_url_ttl_seconds=int(os.getenv("UPLOAD_SIGNED_URL_TTL_SECONDS", "900")),
        upload_max_files=int(os.getenv("UPLOAD_MAX_FILES", "20")),
        upload_max_file_bytes=int(os.getenv("UPLOAD_MAX_FILE_BYTES", str(50 * 1024 * 1024))),
        upload_max_total_bytes=int(os.getenv("UPLOAD_MAX_TOTAL_BYTES", str(200 * 1024 * 1024))),
        google_oauth_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID") or None,
        google_oauth_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or None,
        google_oauth_redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or None,
        google_credential_vault_key=os.getenv("GOOGLE_CREDENTIAL_VAULT_KEY") or None,
        google_kms_key=os.getenv("GOOGLE_KMS_KEY") or None,
        google_oauth_ttl_seconds=int(os.getenv("GOOGLE_OAUTH_TTL_SECONDS", "600")),
        evaluation_dispatch_queue=os.getenv("EVALUATION_DISPATCH_QUEUE") or None,
        evaluation_worker_job=os.getenv("EVALUATION_WORKER_JOB") or None,
        evaluation_dispatcher_sa=os.getenv("EVALUATION_DISPATCHER_SA") or None,
        evaluation_launch_url=os.getenv("EVALUATION_LAUNCH_URL") or None,
        evaluation_launch_audience=os.getenv("EVALUATION_LAUNCH_AUDIENCE") or None,
        meridian_fit_dispatch_queue=os.getenv("MERIDIAN_FIT_DISPATCH_QUEUE") or None,
        meridian_model_worker_job=os.getenv("MERIDIAN_MODEL_WORKER_JOB") or None,
        meridian_fit_dispatcher_sa=os.getenv("MERIDIAN_FIT_DISPATCHER_SA") or None,
        meridian_fit_launch_url=os.getenv("MERIDIAN_FIT_LAUNCH_URL") or None,
        meridian_fit_launch_audience=os.getenv("MERIDIAN_FIT_LAUNCH_AUDIENCE") or None,
        meridian_model_worker_image=os.getenv("MERIDIAN_MODEL_WORKER_IMAGE") or None,
        meridian_model_gpu=os.getenv("MERIDIAN_MODEL_GPU") or None,
        meridian_model_cpu=os.getenv("MERIDIAN_MODEL_CPU") or None,
        meridian_model_memory=os.getenv("MERIDIAN_MODEL_MEMORY") or None,
        meridian_model_timeout_seconds=int(
            os.getenv("MERIDIAN_MODEL_TIMEOUT_SECONDS", "3600")
        ),
    )


settings = load_settings()

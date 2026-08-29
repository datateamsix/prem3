"""Server-owned Cloud Run Job mapping for Meridian compute profiles."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.modeling.mmm.contracts import ComputeProfile
from app.service.evaluation_jobs import (
    CloudRunEvaluationJobLauncher,
    FakeEvaluationJobLauncher,
    JobLaunchError,
    UnavailableEvaluationJobLauncher,
    execution_id_from_resource,
)

DEFAULT_MERIDIAN_MODEL_JOB_NAME = "prem3-meridian-model-worker"
DEFAULT_GPU_TYPE = "nvidia-l4"


def gpu_standard_job_spec(settings: Settings) -> dict[str, Any]:
    """GPU_STANDARD maps to a server-owned job. Request/agent values are ignored."""
    return compute_profile_job_spec(ComputeProfile.GPU_STANDARD, settings)


def compute_profile_job_spec(profile: ComputeProfile, settings: Settings) -> dict[str, Any]:
    """Map an approved compute profile to server-owned job resources."""
    job_name = settings.meridian_model_worker_job or DEFAULT_MERIDIAN_MODEL_JOB_NAME
    timeout = settings.meridian_model_timeout_seconds
    base = {
        "job_name": job_name,
        "region": settings.cloud_region,
        "image": settings.meridian_model_worker_image,
        "service_account": settings.runtime_sa,
        "timeout_seconds": timeout,
        "retry_policy": "server-owned",
        "compute_profile": profile.value,
    }
    if profile is ComputeProfile.CPU_TEST:
        return {
            **base,
            "cpu": settings.meridian_model_cpu or "4",
            "memory": settings.meridian_model_memory or "16Gi",
            "gpu": None,
            "runtime_mode": "OFFICIAL_CPU_SMOKE",
        }
    if profile is ComputeProfile.CPU_STANDARD:
        return {
            **base,
            "cpu": settings.meridian_model_cpu or "4",
            "memory": settings.meridian_model_memory or "16Gi",
            "gpu": None,
            "runtime_mode": "OFFICIAL_CPU",
        }
    if profile is ComputeProfile.CPU_LARGE:
        return {
            **base,
            "cpu": "8",
            "memory": "32Gi",
            "gpu": None,
            "runtime_mode": "OFFICIAL_CPU",
        }
    if profile is ComputeProfile.GPU_STANDARD:
        return {
            **base,
            "cpu": settings.meridian_model_cpu or "4",
            "memory": settings.meridian_model_memory or "16Gi",
            "gpu": settings.meridian_model_gpu or DEFAULT_GPU_TYPE,
            "runtime_mode": "OFFICIAL_GPU",
        }
    if profile is ComputeProfile.GPU_LARGE:
        return {
            **base,
            "cpu": "8",
            "memory": "32Gi",
            "gpu": settings.meridian_model_gpu or DEFAULT_GPU_TYPE,
            "runtime_mode": "OFFICIAL_GPU",
        }
    raise JobLaunchError(f"Unsupported compute profile {profile.value}.")


def assert_no_user_resource_authority(request: dict[str, Any]) -> None:
    forbidden = {
        "python",
        "script",
        "generated_python",
        "container_image",
        "service_account",
        "cloud_run_job_name",
        "destination_override",
        "storage_path",
        "gpu",
        "cpu",
        "memory",
        "region",
        "image_digest",
    }
    unexpected = forbidden.intersection(request)
    if unexpected:
        raise JobLaunchError(
            f"Fit dispatch rejected user resource authority: {sorted(unexpected)}"
        )


def compute_profile_job_name(profile: ComputeProfile, settings: Settings) -> str:
    return compute_profile_job_spec(profile, settings)["job_name"]


class MeridianJobLauncher:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def launch(self, dispatch_id: str) -> str:
        return self._inner.launch(dispatch_id)


def default_fit_launcher(settings: Settings, *, local: bool) -> Any:
    job_name = settings.meridian_model_worker_job or DEFAULT_MERIDIAN_MODEL_JOB_NAME
    if local:
        return FakeEvaluationJobLauncher()
    if not (
        settings.meridian_fit_dispatch_queue
        and settings.meridian_fit_dispatcher_sa
        and settings.meridian_fit_launch_url
    ):
        return UnavailableEvaluationJobLauncher()
    return CloudRunEvaluationJobLauncher(
        project_id=settings.project_id,
        location=settings.cloud_region,
        job_name=job_name,
        dispatch_env_var="PREM3_MMM_FIT_DISPATCH_ID",
    )


__all__ = [
    "DEFAULT_GPU_TYPE",
    "DEFAULT_MERIDIAN_MODEL_JOB_NAME",
    "JobLaunchError",
    "MeridianJobLauncher",
    "assert_no_user_resource_authority",
    "compute_profile_job_name",
    "compute_profile_job_spec",
    "default_fit_launcher",
    "execution_id_from_resource",
    "gpu_standard_job_spec",
]

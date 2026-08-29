"""Cloud Run Job launcher for prem3-mta-worker."""

from __future__ import annotations

from typing import Protocol

from app.service.evaluation_jobs import (
    CloudRunEvaluationJobLauncher,
    JobLaunchError,
)

MTA_WORKER_JOB_NAME = "prem3-mta-worker"
MTA_DISPATCH_ENV = "PREM3_MTA_DISPATCH_ID"
MTA_CLOUD_RUNTIME_ENV = "PREM3_MTA_CLOUD_RUNTIME"


class MTAJobLauncher(Protocol):
    def launch(self, dispatch_id: str) -> str: ...


class FakeMTAJobLauncher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def launch(self, dispatch_id: str) -> str:
        self.calls.append(dispatch_id)
        return f"prem3-mta-worker/{dispatch_id}"


class CloudRunMTAJobLauncher:
    def __init__(
        self,
        *,
        project_id: str,
        location: str = "us-central1",
        job_name: str = MTA_WORKER_JOB_NAME,
        client: object | None = None,
    ) -> None:
        self._inner = CloudRunEvaluationJobLauncher(
            project_id=project_id,
            location=location,
            job_name=job_name,
            client=client,
            dispatch_env_var=MTA_DISPATCH_ENV,
            extra_env=((MTA_CLOUD_RUNTIME_ENV, "1"),),
        )

    def launch(self, dispatch_id: str) -> str:
        return self._inner.launch(dispatch_id)


__all__ = [
    "CloudRunMTAJobLauncher",
    "FakeMTAJobLauncher",
    "JobLaunchError",
    "MTAJobLauncher",
    "MTA_CLOUD_RUNTIME_ENV",
    "MTA_DISPATCH_ENV",
    "MTA_WORKER_JOB_NAME",
]

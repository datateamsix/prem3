"""Cloud Run Job launcher. Starts one Evaluation execution; does not wait."""

from __future__ import annotations

from typing import Protocol

try:
    from google.cloud import run_v2
except ImportError:  # pragma: no cover - local tests use FakeEvaluationJobLauncher
    run_v2 = None


class EvaluationJobLauncher(Protocol):
    def launch(self, dispatch_id: str) -> str: ...


class FakeEvaluationJobLauncher:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.execution_prefix = "exec-fake"

    def launch(self, dispatch_id: str) -> str:
        name = f"{self.execution_prefix}-{dispatch_id}"
        self.calls.append(dispatch_id)
        return name


class UnavailableEvaluationJobLauncher:
    def launch(self, dispatch_id: str) -> str:
        del dispatch_id
        raise JobLaunchError("evaluation job launcher is not configured")


class JobLaunchError(RuntimeError):
    """Cloud Run Jobs API failed before the worker claimed the dispatch."""


def execution_id_from_resource(name: str) -> str:
    """Cloud Run env uses the short execution id; the Jobs API returns a resource name."""
    value = name.strip()
    if not value:
        return value
    return value.rsplit("/", 1)[-1]


class CloudRunEvaluationJobLauncher:
    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        job_name: str,
        client: object | None = None,
    ) -> None:
        self._job_path = f"projects/{project_id}/locations/{location}/jobs/{job_name}"
        self._client = client

    def launch(self, dispatch_id: str) -> str:
        client = self._client or _run_jobs_client()
        request = {
            "name": self._job_path,
            "overrides": {
                "container_overrides": [
                    {
                        "env": [
                            {
                                "name": "PREM3_EVALUATION_DISPATCH_ID",
                                "value": dispatch_id,
                            }
                        ]
                    }
                ]
            },
        }
        try:
            operation = client.run_job(request=request)
            response = operation.result(timeout=60)
        except Exception as exc:
            raise JobLaunchError("cloud run job launch failed") from exc
        return execution_id_from_resource(str(getattr(response, "name", None) or ""))


def _run_jobs_client() -> object:
    if run_v2 is None:
        raise JobLaunchError("google-cloud-run is not installed")
    return run_v2.JobsClient()

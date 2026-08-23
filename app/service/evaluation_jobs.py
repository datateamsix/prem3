"""Cloud Run Job launcher. Starts one Evaluation execution; does not wait."""

from __future__ import annotations

import time
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
            name = _execution_name_from_operation(operation)
        except JobLaunchError:
            raise
        except Exception as exc:
            raise JobLaunchError("cloud run job launch failed") from exc
        if not name:
            raise JobLaunchError("cloud run job launch returned no execution name")
        return execution_id_from_resource(name)


def _execution_name_from_operation(operation: object) -> str:
    """Return the execution id without waiting for the Job to finish."""
    deadline = time.time() + 15
    while time.time() <= deadline:
        metadata = getattr(operation, "metadata", None)
        name = getattr(metadata, "name", None) if metadata is not None else None
        if name:
            return str(name)
        done = getattr(operation, "done", None)
        if callable(done) and done():
            error = getattr(operation, "exception", None)
            if callable(error):
                exc = error()
                if exc is not None:
                    raise JobLaunchError("cloud run job launch failed") from exc
            result = getattr(operation, "result", None)
            if callable(result):
                response = result(timeout=1)
                return str(getattr(response, "name", None) or "")
            return ""
        time.sleep(0.25)
    return ""


def _run_jobs_client() -> object:
    if run_v2 is None:
        raise JobLaunchError("google-cloud-run is not installed")
    return run_v2.JobsClient()

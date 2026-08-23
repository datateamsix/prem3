"""Durable Evaluation enqueue. Cloud Tasks is the launcher queue, not the worker."""

from __future__ import annotations

import json
from typing import Protocol

from app.control_plane.models import EvaluationDispatch

try:
    from google.cloud import tasks_v2
except ImportError:  # pragma: no cover - local tests use FakeEvaluationDispatcher
    tasks_v2 = None


class EvaluationDispatcher(Protocol):
    def enqueue(self, dispatch: EvaluationDispatch) -> str: ...


class FakeEvaluationDispatcher:
    """Local/CI dispatcher. Records enqueue calls. Never talks to Cloud Tasks."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.fail_next = False

    def enqueue(self, dispatch: EvaluationDispatch) -> str:
        if self.fail_next:
            self.fail_next = False
            raise DispatchEnqueueError("fake enqueue failed")
        task_name = f"prem3-eval-{dispatch.dispatch_id}"
        self.calls.append(
            {
                "task_name": task_name,
                "dispatch_id": dispatch.dispatch_id,
                "payload": json.dumps({"dispatch_id": dispatch.dispatch_id}),
            }
        )
        return task_name


class UnavailableEvaluationDispatcher:
    """Cloud fail-closed dispatcher when queue configuration is missing."""

    def enqueue(self, dispatch: EvaluationDispatch) -> str:
        del dispatch
        raise DispatchEnqueueError("durable evaluation dispatcher is not configured")


class DispatchEnqueueError(RuntimeError):
    """Queue delivery failed. Evaluation must be reused, not replaced."""


class CloudTasksEvaluationDispatcher:
    """Enqueue a short launch command. Payload is dispatch_id only."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        queue: str,
        launch_url: str,
        service_account_email: str,
        audience: str,
        client: object | None = None,
    ) -> None:
        self._parent = f"projects/{project_id}/locations/{location}/queues/{queue}"
        self._launch_url = launch_url
        self._service_account_email = service_account_email
        self._audience = audience
        self._client = client

    def enqueue(self, dispatch: EvaluationDispatch) -> str:
        task_id = f"prem3-eval-{dispatch.dispatch_id}"
        task_name = f"{self._parent}/tasks/{task_id}"
        body = json.dumps({"dispatch_id": dispatch.dispatch_id}).encode("utf-8")
        launch_url = (
            f"{self._launch_url.rstrip('/')}/{dispatch.dispatch_id}/launch"
        )
        task = {
            "name": task_name,
            "dispatch_deadline": {"seconds": 60},
            "http_request": {
                "http_method": "POST",
                "url": launch_url,
                "headers": {"Content-Type": "application/json"},
                "body": body,
                "oidc_token": {
                    "service_account_email": self._service_account_email,
                    "audience": self._audience,
                },
            },
        }
        client = self._client or _cloud_tasks_client()
        try:
            created = client.create_task(request={"parent": self._parent, "task": task})
        except Exception as exc:
            if _already_exists(exc):
                return task_name
            raise DispatchEnqueueError("cloud tasks enqueue failed") from exc
        return str(getattr(created, "name", None) or task_name)


def _cloud_tasks_client() -> object:
    if tasks_v2 is None:
        raise DispatchEnqueueError("google-cloud-tasks is not installed")
    return tasks_v2.CloudTasksClient()


def _already_exists(exc: Exception) -> bool:
    return "AlreadyExists" in type(exc).__name__ or "already exists" in str(exc).lower()

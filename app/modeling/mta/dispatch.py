"""Cloud Tasks enqueue for MTA runs. Payload is dispatch_id only."""

from __future__ import annotations

import json
from typing import Protocol

from app.modeling.mta.runtime_contracts import MTAExecutionDispatch
from app.service.evaluation_dispatch import DispatchEnqueueError, _already_exists

try:
    from google.cloud import tasks_v2
except ImportError:  # pragma: no cover
    tasks_v2 = None


class MTADispatcher(Protocol):
    def enqueue(self, dispatch: MTAExecutionDispatch) -> str: ...


class FakeMTADispatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self._seen: set[str] = set()

    def enqueue(self, dispatch: MTAExecutionDispatch) -> str:
        task_name = f"prem3-mta-{dispatch.dispatch_id}"
        if task_name in self._seen:
            return task_name
        self._seen.add(task_name)
        self.calls.append(
            {
                "task_name": task_name,
                "dispatch_id": dispatch.dispatch_id,
                "payload": json.dumps({"dispatch_id": dispatch.dispatch_id}),
            }
        )
        return task_name


class CloudTasksMTADispatcher:
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

    def enqueue(self, dispatch: MTAExecutionDispatch) -> str:
        task_id = f"prem3-mta-{dispatch.dispatch_id}"
        task_name = f"{self._parent}/tasks/{task_id}"
        body = json.dumps({"dispatch_id": dispatch.dispatch_id}).encode("utf-8")
        launch_url = f"{self._launch_url.rstrip('/')}/{dispatch.dispatch_id}/launch"
        task = {
            "name": task_name,
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
            raise DispatchEnqueueError("cloud tasks mta enqueue failed") from exc
        return str(getattr(created, "name", None) or task_name)


def _cloud_tasks_client() -> object:
    if tasks_v2 is None:
        raise DispatchEnqueueError("google-cloud-tasks is not installed")
    return tasks_v2.CloudTasksClient()

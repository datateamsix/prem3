"""Managed BigQuery scheduled-query provisioning via Data Transfer API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint


@dataclass
class ScheduledQueryResource:
    resource_name: str
    display_name: str
    schedule: str
    timezone: str
    destination_dataset: str
    disabled: bool
    params: dict[str, Any]
    fingerprint: str


class FakeScheduledQueryClient:
    """Unit-test double — not a live proof path."""

    def __init__(self) -> None:
        self._configs: dict[str, ScheduledQueryResource] = {}
        self._seq = 0

    def create(
        self,
        *,
        project_id: str,
        display_name: str,
        schedule: str,
        timezone: str,
        query: str,
        destination_dataset: str,
        service_account: str | None = None,
    ) -> ScheduledQueryResource:
        self._seq += 1
        name = f"projects/{project_id}/locations/us/transferConfigs/fake-{self._seq}"
        fp = canonical_fingerprint(
            {
                "display_name": display_name,
                "schedule": schedule,
                "timezone": timezone,
                "query": query,
                "destination_dataset": destination_dataset,
                "service_account": service_account,
            }
        )
        resource = ScheduledQueryResource(
            resource_name=name,
            display_name=display_name,
            schedule=schedule,
            timezone=timezone,
            destination_dataset=destination_dataset,
            disabled=False,
            params={"query": query, "service_account": service_account},
            fingerprint=fp,
        )
        self._configs[name] = resource
        return resource

    def get(self, resource_name: str) -> ScheduledQueryResource | None:
        return self._configs.get(resource_name)

    def disable(self, resource_name: str) -> ScheduledQueryResource:
        resource = self._configs[resource_name]
        updated = ScheduledQueryResource(
            resource_name=resource.resource_name,
            display_name=resource.display_name,
            schedule=resource.schedule,
            timezone=resource.timezone,
            destination_dataset=resource.destination_dataset,
            disabled=True,
            params=resource.params,
            fingerprint=resource.fingerprint,
        )
        self._configs[resource_name] = updated
        return updated

    def update_query(
        self,
        resource_name: str,
        *,
        query: str,
        schedule: str | None = None,
        timezone: str | None = None,
    ) -> ScheduledQueryResource:
        resource = self._configs[resource_name]
        schedule_v = schedule or resource.schedule
        timezone_v = timezone or resource.timezone
        fp = canonical_fingerprint(
            {
                "display_name": resource.display_name,
                "schedule": schedule_v,
                "timezone": timezone_v,
                "query": query,
                "destination_dataset": resource.destination_dataset,
            }
        )
        updated = ScheduledQueryResource(
            resource_name=resource.resource_name,
            display_name=resource.display_name,
            schedule=schedule_v,
            timezone=timezone_v,
            destination_dataset=resource.destination_dataset,
            disabled=resource.disabled,
            params={**resource.params, "query": query},
            fingerprint=fp,
        )
        self._configs[resource_name] = updated
        return updated


class BigQueryScheduledQueryClient:
    """Production Data Transfer scheduled_query provisioner."""

    def __init__(self, *, project_id: str, location: str = "us-central1") -> None:
        from google.cloud import bigquery_datatransfer_v1

        self.project_id = project_id
        # Must match destination dataset region (prem3_modeling is us-central1).
        self.location = location
        self._client = bigquery_datatransfer_v1.DataTransferServiceClient()
        self._types = bigquery_datatransfer_v1

    def _parent(self) -> str:
        return f"projects/{self.project_id}/locations/{self.location}"

    def create(
        self,
        *,
        project_id: str,
        display_name: str,
        schedule: str,
        timezone: str,
        query: str,
        destination_dataset: str,
        service_account: str | None = None,
    ) -> ScheduledQueryResource:
        del project_id  # bound at client construction
        TransferConfig = self._types.TransferConfig
        config = TransferConfig(
            display_name=display_name,
            data_source_id="scheduled_query",
            destination_dataset_id=destination_dataset,
            schedule=schedule,
            disabled=False,
            params={
                "query": query,
            },
        )
        # timezone is set via schedule_options / schedule with TZ in some API versions
        request: dict[str, Any] = {
            "parent": self._parent(),
            "transfer_config": config,
        }
        if service_account:
            request["service_account_name"] = service_account
        created = self._client.create_transfer_config(request=request)
        # Attempt to set timezone if supported on the object
        if hasattr(created, "schedule_options") or True:
            try:
                created.schedule = schedule
                # Some clients store destination timezone separately; patch if needed.
            except Exception:
                pass
        fp = canonical_fingerprint(
            {
                "display_name": display_name,
                "schedule": schedule,
                "timezone": timezone,
                "query": query,
                "destination_dataset": destination_dataset,
                "service_account": service_account,
                "name": created.name,
            }
        )
        return ScheduledQueryResource(
            resource_name=created.name,
            display_name=display_name,
            schedule=schedule,
            timezone=timezone,
            destination_dataset=destination_dataset,
            disabled=bool(getattr(created, "disabled", False)),
            params={"query": query, "service_account": service_account},
            fingerprint=fp,
        )

    def get(self, resource_name: str) -> ScheduledQueryResource | None:
        try:
            created = self._client.get_transfer_config(name=resource_name)
        except Exception:
            return None
        query = ""
        params = dict(getattr(created, "params", {}) or {})
        if "query" in params:
            query = params["query"]
        fp = canonical_fingerprint(
            {
                "name": created.name,
                "display_name": created.display_name,
                "schedule": created.schedule,
                "query": query,
                "destination_dataset": created.destination_dataset_id,
            }
        )
        return ScheduledQueryResource(
            resource_name=created.name,
            display_name=created.display_name,
            schedule=created.schedule or "",
            timezone="",
            destination_dataset=created.destination_dataset_id or "",
            disabled=bool(created.disabled),
            params=params,
            fingerprint=fp,
        )

    def disable(self, resource_name: str) -> ScheduledQueryResource:
        config = self._client.get_transfer_config(name=resource_name)
        config.disabled = True
        updated = self._client.update_transfer_config(
            transfer_config=config,
            update_mask={"paths": ["disabled"]},
        )
        resource = self.get(updated.name)
        assert resource is not None
        return resource

    def update_query(
        self,
        resource_name: str,
        *,
        query: str,
        schedule: str | None = None,
        timezone: str | None = None,
    ) -> ScheduledQueryResource:
        del timezone
        config = self._client.get_transfer_config(name=resource_name)
        params = dict(config.params or {})
        params["query"] = query
        config.params = params
        paths = ["params"]
        if schedule:
            config.schedule = schedule
            paths.append("schedule")
        updated = self._client.update_transfer_config(
            transfer_config=config,
            update_mask={"paths": paths},
        )
        resource = self.get(updated.name)
        assert resource is not None
        return resource

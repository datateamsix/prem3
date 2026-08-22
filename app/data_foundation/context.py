"""Server-owned Data Foundation authority. Callers may not supply physical targets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.identifiers import validate_resource_identifier
from app.core.tenancy import TenantContext, require_tenant
from app.data_foundation.enums import ConnectionLifecycle


class DataFoundationContext(BaseModel):
    """Resolved from TenantContext + stored workspace bindings. Never from the body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    actor_id: str
    entitlement_snapshot_id: str | None = None
    google_connection_id: str | None = None
    destination_project_id: str | None = None
    destination_dataset_id: str = "prem3_modeling"
    destination_location: str | None = None
    source_project_ids: tuple[str, ...] = ()
    source_dataset_ids: tuple[str, ...] = ()
    drive_root_folder_id: str | None = None
    bq_lifecycle: ConnectionLifecycle = ConnectionLifecycle.NOT_CONNECTED
    drive_lifecycle: ConnectionLifecycle = ConnectionLifecycle.NOT_CONNECTED
    approved_foundation_plan_id: str | None = None
    approved_transformation_plan_id: str | None = None

    @field_validator("tenant_id")
    @classmethod
    def _tenant(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

    def require_same_tenant(self, tenant: TenantContext) -> None:
        if tenant.tenant_id != self.tenant_id:
            raise PermissionError("Cross-tenant Data Foundation access is denied.")

    def require_discovery_ready(self) -> None:
        if self.bq_lifecycle not in {
            ConnectionLifecycle.DISCOVERY_READY,
            ConnectionLifecycle.PROVISIONING_READY,
        }:
            raise PermissionError("BigQuery discovery is not ready.")

    def require_provisioning_ready(self) -> None:
        if self.bq_lifecycle is not ConnectionLifecycle.PROVISIONING_READY:
            raise PermissionError("BigQuery provisioning is not ready.")

    def authorize_project(self, project_id: str) -> None:
        allowed = set(self.source_project_ids)
        if self.destination_project_id:
            allowed.add(self.destination_project_id)
        if project_id not in allowed:
            raise PermissionError("BigQuery project is outside the bound workspace.")

    def authorize_drive_root(self, folder_id: str) -> None:
        if self.drive_root_folder_id is None or folder_id != self.drive_root_folder_id:
            raise PermissionError("Drive folder is outside the bound root.")


def context_from_tenant(
    *,
    workspace_id: str,
    destination_project_id: str | None = None,
    destination_location: str | None = None,
    source_project_ids: tuple[str, ...] = (),
    source_dataset_ids: tuple[str, ...] = (),
    drive_root_folder_id: str | None = None,
    google_connection_id: str | None = None,
    bq_lifecycle: ConnectionLifecycle = ConnectionLifecycle.NOT_CONNECTED,
    drive_lifecycle: ConnectionLifecycle = ConnectionLifecycle.NOT_CONNECTED,
    write_verified: bool = False,
    read_verified: bool = False,
) -> DataFoundationContext:
    tenant = require_tenant()
    resolved_bq = bq_lifecycle
    if read_verified and resolved_bq is ConnectionLifecycle.AUTHORIZED:
        resolved_bq = ConnectionLifecycle.DISCOVERY_READY
    if write_verified:
        resolved_bq = ConnectionLifecycle.PROVISIONING_READY
    return DataFoundationContext(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace_id,
        actor_id=tenant.user_id or tenant.tenant_id,
        entitlement_snapshot_id=tenant.entitlement_snapshot_id,
        google_connection_id=google_connection_id,
        destination_project_id=destination_project_id,
        destination_location=destination_location,
        source_project_ids=source_project_ids,
        source_dataset_ids=source_dataset_ids,
        drive_root_folder_id=drive_root_folder_id,
        bq_lifecycle=resolved_bq,
        drive_lifecycle=drive_lifecycle,
    )

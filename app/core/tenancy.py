"""Request-scoped tenant and workspace authority.

Workload identity (Cloud Run SA / ADC) authenticates PreM3 to Google Cloud.
Tenant identity is application state bound per request. They are never the same
value and are never derived from each other.

There is no default tenant, no ANONYMOUS auth_state, and no Settings/env fallback
inside require_tenant() / require_workspace(). The public Planner does not receive
TenantContext.

Dataset ownership is not proven by passing dataset_id into a helper. That check
belongs to the future product resource repository.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.errors import (
    SafetyViolationError,
    TenantContextMissingError,
    WorkspaceContextMissingError,
)
from app.core.identifiers import validate_resource_identifier

# Schema-level invariant: registered ADK tools must not accept model-supplied
# customer, storage, or commercial authority. Exact/normalized parameter names
# only — not every string containing "path". Semantic GCS/filesystem/BQ
# destinations under a generic name (for example `source`) are still forbidden
# and are caught by the manual registered-tool audit.
FORBIDDEN_MODEL_SUPPLIED_AUTHORITY_PARAMETERS = frozenset(
    {
        "tenant_id",
        "organization_id",
        "workspace_id",
        "dataset_id",
        "run_id",
        "requested_run_id",
        "gcs_uri",
        "gcs_path",
        "package_uri",
        "bucket",
        "artifact_path",
        "raw_path",
        "path",
        "file_path",
        "filesystem_path",
        "local_path",
        "artifact_uri",
        "raw_uri",
        "storage_uri",
        "object_uri",
        "bq_dataset",
        "bq_table",
        "bq_project",
        "bigquery_destination",
        "destination_table",
        "destination_dataset",
        "plan",
        "plan_id",
        "entitlement",
        "entitlement_snapshot_id",
        "google_access_token",
        "google_refresh_token",
        "refresh_token",
        "access_token",
        "connection_id",
        "google_connection_id",
        "root_folder_id",
        "drive_file_id",
        "drive_folder_id",
        "destination_project",
        "destination_project_id",
        "upload_id",
        "dispatch_id",
        "cloud_run_execution",
        "cloud_run_execution_name",
        "cloud_task_name",
    }
)


class AuthState(StrEnum):
    AUTHENTICATED = "AUTHENTICATED"
    SERVICE = "SERVICE"


class TenantContext(BaseModel):
    """Bound customer organization authority for one request or CLI bootstrap."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    user_id: str | None = None
    auth_state: AuthState
    entitlement_snapshot_id: str | None = None

    @field_validator("tenant_id")
    @classmethod
    def _validate_tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("entitlement_snapshot_id")
    @classmethod
    def _validate_entitlement_snapshot_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_resource_identifier(value, field="entitlement_snapshot_id")


class WorkspaceContext(BaseModel):
    """Bound MMM Project authority. dataset_id is optional selector, not proof."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    dataset_id: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

    @field_validator("dataset_id")
    @classmethod
    def _validate_dataset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_resource_identifier(value, field="dataset_id")


_current_tenant: ContextVar[TenantContext | None] = ContextVar(
    "prem3_tenant_context", default=None
)
_current_workspace: ContextVar[WorkspaceContext | None] = ContextVar(
    "prem3_workspace_context", default=None
)


def require_tenant() -> TenantContext:
    """Fail closed. There is no default tenant."""
    ctx = _current_tenant.get()
    if ctx is None:
        raise TenantContextMissingError(
            "No tenant context bound. Refusing authenticated tenant operation."
        )
    return ctx


def require_workspace() -> WorkspaceContext:
    """Fail closed for project-scoped operations."""
    ctx = _current_workspace.get()
    if ctx is None:
        raise WorkspaceContextMissingError(
            "No authorized MMM Project context bound. Refusing project operation."
        )
    return ctx


def current_tenant() -> TenantContext | None:
    return _current_tenant.get()


def current_workspace() -> WorkspaceContext | None:
    return _current_workspace.get()


@contextmanager
def bind_tenant(ctx: TenantContext) -> Iterator[TenantContext]:
    token = _current_tenant.set(ctx)
    try:
        yield ctx
    finally:
        _current_tenant.reset(token)


@contextmanager
def bind_workspace(ctx: WorkspaceContext) -> Iterator[WorkspaceContext]:
    token = _current_workspace.set(ctx)
    try:
        yield ctx
    finally:
        _current_workspace.reset(token)


def normalize_tool_parameter_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def is_forbidden_model_supplied_authority_parameter(name: str) -> bool:
    """True if an ADK/tool argument name must not be model-supplied authority."""
    return normalize_tool_parameter_name(name) in FORBIDDEN_MODEL_SUPPLIED_AUTHORITY_PARAMETERS


def assert_not_storage_authority(value: str, *, field: str) -> None:
    """Fail closed if a model-callable field looks like a URI or filesystem path."""
    text = str(value).strip()
    lowered = text.lower()
    if lowered.startswith(("gs://", "gcs://", "s3://", "file://", "http://", "https://")):
        raise SafetyViolationError(f"{field} must not be a storage or remote URI.")
    if "://" in text:
        raise SafetyViolationError(f"{field} must not be a URI.")
    if text.startswith("/") or "\\" in text or (len(text) >= 3 and text[1:3] in {":/", ":\\"}):
        raise SafetyViolationError(f"{field} must not be a filesystem path.")

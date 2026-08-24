"""Project Measurement Home authority. Presentation may report CONFLICT; use may not."""

from __future__ import annotations

from app.control_plane.models import Workspace, WorkspaceStatus
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import MeasurementHomeConflictError
from app.project.enums import CANONICAL_BQ_DATASET


def measurement_home_conflict(repo: ControlPlaneRepository, workspace: Workspace) -> bool:
    binding = repo.get_bigquery_binding(
        tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
    )
    if binding is None:
        return False
    if binding.destination_dataset_id != CANONICAL_BQ_DATASET:
        return False
    for other in repo.list_workspaces_for_tenant(workspace.tenant_id):
        if other.workspace_id == workspace.workspace_id:
            continue
        if other.status is not WorkspaceStatus.ACTIVE:
            continue
        other_binding = repo.get_bigquery_binding(
            tenant_id=other.tenant_id, workspace_id=other.workspace_id
        )
        if other_binding is None:
            continue
        if (
            other_binding.destination_project_id == binding.destination_project_id
            and other_binding.destination_dataset_id == CANONICAL_BQ_DATASET
        ):
            return True
    return False


def require_usable_measurement_home(
    repo: ControlPlaneRepository, workspace: Workspace
) -> None:
    if measurement_home_conflict(repo, workspace):
        raise MeasurementHomeConflictError(
            "A conflicted prem3_modeling Measurement Home cannot be used "
            "as resource authority."
        )


def require_usable_measurement_home_ids(
    repo: ControlPlaneRepository, *, tenant_id: str, workspace_id: str
) -> None:
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant_id, workspace_id=workspace_id
    )
    if workspace is None:
        return
    require_usable_measurement_home(repo, workspace)

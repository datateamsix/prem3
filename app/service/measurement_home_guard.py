"""Fail-closed Measurement Home authority. Presentation may still report CONFLICT."""

from __future__ import annotations

from app.control_plane.models import Workspace
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import MeasurementHomeConflictError
from app.project.measurement_home import (
    require_usable_measurement_home,
    require_usable_measurement_home_ids,
)
from app.service.errors import measurement_home_conflict_denied


def deny_conflicted_measurement_home(
    repo: ControlPlaneRepository,
    workspace: Workspace | None = None,
    *,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
) -> None:
    try:
        if workspace is not None:
            require_usable_measurement_home(repo, workspace)
            return
        if tenant_id is None or workspace_id is None:
            return
        require_usable_measurement_home_ids(
            repo, tenant_id=tenant_id, workspace_id=workspace_id
        )
    except MeasurementHomeConflictError as exc:
        raise measurement_home_conflict_denied() from exc

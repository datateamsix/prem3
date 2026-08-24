"""Canonical Drive depot binding. Folder IDs are authority; names are not."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.models import DriveWorkspaceBinding, Feature, GoogleConnection
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.governance.codes import DRIVE_DEPOT_NAME, BindingStatus, ConnectionStatus, GoogleCapability
from app.integrations.google.adapters import DriveClient
from app.service.entitlements import require_feature
from app.service.errors import ProblemFieldError, resource_not_found, validation_error
from app.service.google_oauth import GoogleConnectionService
from app.service.measurement_home_guard import deny_conflicted_measurement_home

CHILD_FOLDERS = ("imports", "exports", "reports")


class DriveBindingService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        connections: GoogleConnectionService,
        drive: DriveClient,
    ) -> None:
        self._repo = repo
        self._connections = connections
        self._drive = drive

    def get_binding(self, *, workspace_id: str) -> DriveWorkspaceBinding | None:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        deny_conflicted_measurement_home(
            self._repo, tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        return self._repo.get_drive_binding(tenant_id=tenant.tenant_id, workspace_id=workspace_id)

    def setup(
        self, *, workspace_id: str, connection_id: str, import_enabled: bool, export_enabled: bool
    ) -> DriveWorkspaceBinding:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        workspace = self._repo.get_workspace_for_tenant(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if workspace is None:
            raise resource_not_found()
        deny_conflicted_measurement_home(self._repo, workspace)
        connection = self._require_drive_connection(connection_id)
        existing = self._repo.get_drive_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        access_token = self._connections.user_access_token(connection=connection)
        now = datetime.now(UTC)
        if existing is not None:
            root = self._drive.get_file(access_token=access_token, file_id=existing.root_folder_id)
            if root is None or root.trashed:
                degraded = existing.model_copy(
                    update={
                        "status": BindingStatus.DEGRADED.value,
                        "import_enabled": False,
                        "export_enabled": False,
                        "updated_at": now,
                    }
                )
                return self._repo.put_drive_binding(degraded)
            repaired = existing.model_copy(
                update={
                    "connection_id": connection.connection_id,
                    "status": BindingStatus.ACTIVE.value,
                    "import_enabled": import_enabled,
                    "export_enabled": export_enabled,
                    "updated_at": now,
                    "last_verified_at": now,
                }
            )
            return self._repo.put_drive_binding(repaired)
        root = self._drive.create_folder(
            access_token=access_token, name=DRIVE_DEPOT_NAME, parent_id=None
        )
        children: dict[str, str] = {}
        for name in CHILD_FOLDERS:
            folder = self._drive.create_folder(
                access_token=access_token, name=name, parent_id=root.file_id
            )
            children[name] = folder.file_id
        binding = DriveWorkspaceBinding(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            connection_id=connection.connection_id,
            root_folder_id=root.file_id,
            root_folder_name=DRIVE_DEPOT_NAME,
            imports_folder_id=children["imports"],
            exports_folder_id=children["exports"],
            reports_folder_id=children["reports"],
            status=BindingStatus.ACTIVE.value,
            import_enabled=import_enabled,
            export_enabled=export_enabled,
            created_at=now,
            updated_at=now,
            last_verified_at=now,
        )
        return self._repo.put_drive_binding(binding)

    def repair(self, *, workspace_id: str, connection_id: str) -> DriveWorkspaceBinding:
        return self.setup(
            workspace_id=workspace_id,
            connection_id=connection_id,
            import_enabled=True,
            export_enabled=True,
        )

    def _require_drive_connection(self, connection_id: str) -> GoogleConnection:
        connection = self._connections.get_connection(connection_id=connection_id)
        if connection.status != ConnectionStatus.ACTIVE.value:
            raise validation_error(
                [
                    ProblemFieldError(
                        field="connection_id",
                        message="Google connection is not active.",
                    )
                ]
            )
        if GoogleCapability.GOOGLE_DRIVE.value not in connection.capabilities:
            raise validation_error(
                [
                    ProblemFieldError(
                        field="connection_id",
                        message="GOOGLE_DRIVE capability is not granted.",
                    )
                ]
            )
        return connection

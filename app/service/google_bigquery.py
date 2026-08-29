"""BigQuery discovery and canonical prem3_modeling depot binding."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.models import BigQueryWorkspaceBinding, Feature, GoogleConnection
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.governance.codes import (
    BIGQUERY_DEPOT_DATASET_ID,
    BIGQUERY_DEPOT_FRIENDLY_NAME,
    BindingStatus,
    ConnectionStatus,
    GoogleCapability,
)
from app.integrations.google.adapters import BigQueryClient, BigQueryTableInfo
from app.service.entitlements import require_feature
from app.service.errors import ProblemFieldError, resource_not_found, validation_error
from app.service.google_oauth import GoogleConnectionService
from app.service.measurement_home_guard import deny_conflicted_measurement_home


class BigQueryBindingService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        connections: GoogleConnectionService,
        bigquery: BigQueryClient,
    ) -> None:
        self._repo = repo
        self._connections = connections
        self._bigquery = bigquery

    def get_binding(self, *, workspace_id: str) -> BigQueryWorkspaceBinding | None:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        deny_conflicted_measurement_home(
            self._repo, tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        return self._repo.get_bigquery_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )

    def list_projects(self, *, workspace_id: str, connection_id: str) -> list[dict[str, str]]:
        connection, access_token = self._user_read_context(
            workspace_id=workspace_id, connection_id=connection_id
        )
        del connection
        return self._bigquery.list_projects(access_token=access_token)

    def list_datasets(
        self, *, workspace_id: str, connection_id: str, project_id: str
    ) -> list[dict[str, str]]:
        _connection, access_token = self._user_read_context(
            workspace_id=workspace_id, connection_id=connection_id
        )
        return self._bigquery.list_datasets(access_token=access_token, project_id=project_id)

    def list_tables(
        self, *, workspace_id: str, connection_id: str, project_id: str, dataset_id: str
    ) -> list[BigQueryTableInfo]:
        _connection, access_token = self._user_read_context(
            workspace_id=workspace_id, connection_id=connection_id
        )
        return self._bigquery.list_tables(
            access_token=access_token, project_id=project_id, dataset_id=dataset_id
        )

    def setup(
        self,
        *,
        workspace_id: str,
        connection_id: str,
        destination_project_id: str,
        location: str,
        source_project_ids: list[str],
        source_dataset_ids: list[str],
        create_if_missing: bool,
    ) -> BigQueryWorkspaceBinding:
        require_feature(self._repo, Feature.BIGQUERY_PUBLISH)
        tenant = require_tenant()
        workspace = self._repo.get_workspace_for_tenant(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if workspace is None:
            raise resource_not_found()
        deny_conflicted_measurement_home(self._repo, workspace)
        connection = self._require_bq_connection(connection_id, write=True)
        access_token = self._connections.user_access_token(connection=connection)
        now = datetime.now(UTC)
        existing = self._bigquery.get_dataset(
            access_token=access_token,
            project_id=destination_project_id,
            dataset_id=BIGQUERY_DEPOT_DATASET_ID,
        )
        if existing is None:
            if not create_if_missing:
                raise validation_error(
                    [
                        ProblemFieldError(
                            field="destination_project_id",
                            message="Canonical prem3_modeling dataset does not exist.",
                        )
                    ]
                )
            existing = self._bigquery.create_dataset(
                access_token=access_token,
                project_id=destination_project_id,
                dataset_id=BIGQUERY_DEPOT_DATASET_ID,
                friendly_name=BIGQUERY_DEPOT_FRIENDLY_NAME,
                location=location,
            )
        dataset_location = str(existing.get("location") or location)
        if dataset_location and location and dataset_location != location:
            raise validation_error(
                [
                    ProblemFieldError(
                        field="location",
                        message="DESTINATION_LOCATION_MISMATCH",
                    )
                ]
            )
        write_ok = self._bigquery.can_write_dataset(
            access_token=access_token,
            project_id=destination_project_id,
            dataset_id=BIGQUERY_DEPOT_DATASET_ID,
        )
        binding = BigQueryWorkspaceBinding(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            connection_id=connection.connection_id,
            source_project_ids=tuple(source_project_ids),
            source_dataset_ids=tuple(source_dataset_ids),
            destination_project_id=destination_project_id,
            destination_dataset_id=BIGQUERY_DEPOT_DATASET_ID,
            destination_friendly_name=BIGQUERY_DEPOT_FRIENDLY_NAME,
            location=dataset_location,
            read_verified=True,
            write_verified=write_ok,
            status=BindingStatus.ACTIVE.value if write_ok else BindingStatus.DEGRADED.value,
            created_at=now,
            updated_at=now,
            last_verified_at=now,
        )
        previous = self._repo.get_bigquery_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if previous is not None:
            binding = binding.model_copy(update={"created_at": previous.created_at})
        return self._repo.put_bigquery_binding(binding)

    def _user_read_context(
        self, *, workspace_id: str, connection_id: str
    ) -> tuple[GoogleConnection, str]:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        workspace = self._repo.get_workspace_for_tenant(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if workspace is None:
            raise resource_not_found()
        deny_conflicted_measurement_home(self._repo, workspace)
        connection = self._require_bq_connection(connection_id, write=False)
        return connection, self._connections.user_access_token(connection=connection)

    def _require_bq_connection(self, connection_id: str, *, write: bool) -> GoogleConnection:
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
        needed = (
            GoogleCapability.BIGQUERY_WRITE.value
            if write
            else GoogleCapability.BIGQUERY_READ.value
        )
        if needed not in connection.capabilities and (
            write or GoogleCapability.BIGQUERY_WRITE.value not in connection.capabilities
        ):
            raise validation_error(
                [
                    ProblemFieldError(
                        field="connection_id",
                        message="Required BigQuery capability is not granted.",
                    )
                ]
            )
        return connection

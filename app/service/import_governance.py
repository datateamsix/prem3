"""Compile Dataset import selections into PreM3ImportContractV1 and evaluate readiness."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.ids import new_import_object_id
from app.control_plane.models import (
    DatasetImportSelection,
    DatasetUpload,
    Feature,
    UploadStatus,
)
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import InvalidResourceIdentifierError
from app.core.identifiers import validate_resource_identifier
from app.core.source_inventory import CanonicalRole
from app.core.tenancy import require_tenant
from app.governance.codes import (
    IMPORT_CONTRACT_VERSION,
    ConnectionStatus,
    ImportReadinessStatus,
    SourceType,
)
from app.governance.import_contract import (
    ImportReadinessReceipt,
    ImportSourceObject,
    PreM3ImportContractV1,
    RoleAssignment,
)
from app.governance.import_evaluator import evaluate_import_readiness
from app.integrations.google.adapters import DriveClient
from app.integrations.google.formats import drive_format, gcs_format
from app.service.entitlements import require_feature
from app.service.errors import ProblemFieldError, resource_not_found, validation_error
from app.service.google_oauth import GoogleConnectionService
from app.service.measurement_home_guard import deny_conflicted_measurement_home


class ImportGovernanceService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        connections: GoogleConnectionService,
        drive: DriveClient,
        bigquery,
    ) -> None:
        self._repo = repo
        self._connections = connections
        self._drive = drive
        self._bigquery = bigquery

    def put_selection(
        self,
        *,
        workspace_id: str,
        dataset_id: str,
        source_type: str,
        connection_id: str | None,
        upload_id: str | None,
        selected_object_ids: list[str],
        role_assignments: list[dict[str, str]],
    ) -> DatasetImportSelection:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        dataset = self._repo.get_dataset_for_workspace(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )
        if dataset is None:
            raise resource_not_found()
        try:
            parsed_type = SourceType(source_type)
        except ValueError as exc:
            raise validation_error(
                [ProblemFieldError(field="source_type", message="Unsupported import source type.")]
            ) from exc
        now = datetime.now(UTC)
        if parsed_type in {SourceType.GOOGLE_DRIVE, SourceType.BIGQUERY}:
            deny_conflicted_measurement_home(
                self._repo, tenant_id=tenant.tenant_id, workspace_id=workspace_id
            )
        previous = self._repo.get_import_selection(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )
        binding_id = None
        if parsed_type is SourceType.GOOGLE_DRIVE:
            drive = self._repo.get_drive_binding(
                tenant_id=tenant.tenant_id, workspace_id=workspace_id
            )
            binding_id = drive.root_folder_id if drive is not None else None
        elif parsed_type is SourceType.BIGQUERY:
            bq = self._repo.get_bigquery_binding(
                tenant_id=tenant.tenant_id, workspace_id=workspace_id
            )
            binding_id = (
                f"{bq.destination_project_id}.{bq.destination_dataset_id}"
                if bq is not None
                else None
            )
        elif parsed_type is SourceType.GCS_UPLOAD:
            binding_id = upload_id
        selection = DatasetImportSelection(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            source_type=parsed_type.value,
            connection_id=connection_id,
            binding_id=binding_id,
            upload_id=upload_id,
            selected_object_ids=tuple(selected_object_ids),
            role_assignments=tuple(role_assignments),
            current_receipt_id=None,
            created_at=previous.created_at if previous is not None else now,
            updated_at=now,
        )
        stored = self._repo.put_import_selection(selection)
        return stored

    def get_selection(
        self, *, workspace_id: str, dataset_id: str
    ) -> DatasetImportSelection | None:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        return self._repo.get_import_selection(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )

    def evaluate(
        self, *, workspace_id: str, dataset_id: str
    ) -> tuple[PreM3ImportContractV1, ImportReadinessReceipt]:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        selection = self._repo.get_import_selection(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )
        if selection is None:
            raise validation_error(
                [
                    ProblemFieldError(
                        field="import_binding",
                        message="Dataset import selection is required before readiness.",
                    )
                ]
            )
        contract = self.compile_contract(selection)
        receipt = evaluate_import_readiness(contract)
        stored_receipt = self._repo.put_import_receipt(receipt)
        updated = selection.model_copy(
            update={
                "current_receipt_id": stored_receipt.receipt_id,
                "updated_at": datetime.now(UTC),
            }
        )
        self._repo.put_import_selection(updated)
        return contract, stored_receipt

    def current_receipt(
        self, *, workspace_id: str, dataset_id: str
    ) -> ImportReadinessReceipt | None:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        return self._repo.get_current_import_receipt(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )

    def compile_contract(self, selection: DatasetImportSelection) -> PreM3ImportContractV1:
        source_type = SourceType(selection.source_type)
        if source_type is SourceType.GCS_UPLOAD:
            objects, roles = self._compile_gcs(selection)
        elif source_type is SourceType.GOOGLE_DRIVE:
            objects, roles = self._compile_drive(selection)
        else:
            objects, roles = self._compile_bigquery(selection)
        now = datetime.now(UTC)
        draft = PreM3ImportContractV1(
            contract_version=IMPORT_CONTRACT_VERSION,
            tenant_id=selection.tenant_id,
            workspace_id=selection.workspace_id,
            dataset_id=selection.dataset_id,
            source_type=source_type,
            source_binding_id=selection.upload_id or selection.binding_id,
            objects=objects,
            role_assignments=roles,
            created_at=now,
            verified_at=None,
            status=ImportReadinessStatus.NOT_IMPORT_READY,
            manifest_fingerprint="pending",
        )
        fingerprint = draft.compute_fingerprint()
        return draft.model_copy(update={"manifest_fingerprint": fingerprint})

    def _compile_gcs(
        self, selection: DatasetImportSelection
    ) -> tuple[list[ImportSourceObject], list[RoleAssignment]]:
        if not selection.upload_id:
            return [], []
        upload = self._repo.get_upload(
            tenant_id=selection.tenant_id,
            workspace_id=selection.workspace_id,
            dataset_id=selection.dataset_id,
            upload_id=selection.upload_id,
        )
        if upload is None or upload.status is not UploadStatus.VERIFIED:
            return [], []
        roles_by_id = _roles_by_object(selection.role_assignments)
        selected = set(selection.selected_object_ids) or {
            item.upload_file_id for item in upload.files
        }
        objects: list[ImportSourceObject] = []
        roles: list[RoleAssignment] = []
        for file_rec in upload.files:
            if file_rec.upload_file_id not in selected:
                continue
            fmt = gcs_format(
                filename=file_rec.original_filename, content_type=file_rec.content_type
            )
            assignment = roles_by_id.get(file_rec.upload_file_id)
            role = assignment[0] if assignment else CanonicalRole.UNKNOWN
            provider = assignment[1] if assignment else "unresolved"
            version = f"{file_rec.generation or ''}:{file_rec.md5_hash or file_rec.crc32c or ''}"
            obj = ImportSourceObject(
                object_id=file_rec.upload_file_id,
                provider=provider,
                role=role,
                logical_name=file_rec.original_filename,
                source_identity=file_rec.upload_file_id,
                version_identity=version,
                object_type="file",
                format=fmt,
                schema_fingerprint=None,
                size_bytes=file_rec.actual_size_bytes or file_rec.declared_size_bytes,
                row_estimate=None,
                source_metadata={
                    "generation": file_rec.generation or "",
                    "content_type": file_rec.content_type,
                },
            )
            objects.append(obj)
            if assignment:
                roles.append(
                    RoleAssignment(
                        object_id=file_rec.upload_file_id, role=role, provider=provider
                    )
                )
        return objects, roles

    def _compile_drive(
        self, selection: DatasetImportSelection
    ) -> tuple[list[ImportSourceObject], list[RoleAssignment]]:
        if not selection.connection_id:
            return [], []
        connection = self._repo.get_google_connection(
            tenant_id=selection.tenant_id, connection_id=selection.connection_id
        )
        if connection is None or connection.status != ConnectionStatus.ACTIVE.value:
            return [], []
        access_token = self._connections.user_access_token(connection=connection)
        roles_by_id = _roles_by_object(selection.role_assignments)
        objects: list[ImportSourceObject] = []
        roles: list[RoleAssignment] = []
        for source_id in selection.selected_object_ids:
            meta = self._drive.get_file(access_token=access_token, file_id=source_id)
            assignment = roles_by_id.get(source_id)
            role = assignment[0] if assignment else CanonicalRole.UNKNOWN
            provider = assignment[1] if assignment else "unresolved"
            if meta is None or meta.trashed:
                obj = ImportSourceObject(
                    object_id=_safe_object_id(source_id),
                    provider=provider,
                    role=role,
                    logical_name=source_id,
                    source_identity=source_id,
                    version_identity="",
                    object_type="missing",
                    format=None,
                    schema_fingerprint=None,
                    size_bytes=0,
                    row_estimate=None,
                    source_metadata={},
                )
            else:
                fmt = drive_format(mime_type=meta.mime_type, name=meta.name)
                version = meta.md5 or meta.head_revision_id or meta.version or ""
                obj = ImportSourceObject(
                    object_id=_safe_object_id(source_id),
                    provider=provider,
                    role=role,
                    logical_name=meta.name,
                    source_identity=meta.file_id,
                    version_identity=version,
                    object_type=meta.mime_type,
                    format=fmt,
                    schema_fingerprint=None,
                    size_bytes=meta.size_bytes,
                    row_estimate=None,
                    source_metadata={"mime_type": meta.mime_type},
                )
            objects.append(obj)
            if assignment:
                roles.append(
                    RoleAssignment(object_id=obj.object_id, role=role, provider=provider)
                )
        return objects, roles

    def _compile_bigquery(
        self, selection: DatasetImportSelection
    ) -> tuple[list[ImportSourceObject], list[RoleAssignment]]:
        if not selection.connection_id:
            return [], []
        connection = self._repo.get_google_connection(
            tenant_id=selection.tenant_id, connection_id=selection.connection_id
        )
        if connection is None or connection.status != ConnectionStatus.ACTIVE.value:
            return [], []
        access_token = self._connections.user_access_token(connection=connection)
        roles_by_id = _roles_by_object(selection.role_assignments)
        objects: list[ImportSourceObject] = []
        roles: list[RoleAssignment] = []
        for source_id in selection.selected_object_ids:
            parts = source_id.split(".")
            assignment = roles_by_id.get(source_id)
            role = assignment[0] if assignment else CanonicalRole.UNKNOWN
            provider = assignment[1] if assignment else "unresolved"
            if len(parts) != 3:
                obj = ImportSourceObject(
                    object_id=_safe_object_id(source_id),
                    provider=provider,
                    role=role,
                    logical_name=source_id,
                    source_identity=source_id,
                    version_identity="",
                    object_type="UNKNOWN",
                    format=None,
                    schema_fingerprint=None,
                    size_bytes=0,
                    row_estimate=None,
                    source_metadata={},
                )
            else:
                project_id, dataset_id, table_id = parts
                table = self._bigquery.get_table(
                    access_token=access_token,
                    project_id=project_id,
                    dataset_id=dataset_id,
                    table_id=table_id,
                )
                if table is None:
                    obj = ImportSourceObject(
                        object_id=_safe_object_id(source_id),
                        provider=provider,
                        role=role,
                        logical_name=source_id,
                        source_identity=source_id,
                        version_identity="",
                        object_type="UNKNOWN",
                        format=None,
                        schema_fingerprint=None,
                        size_bytes=0,
                        row_estimate=None,
                        source_metadata={},
                    )
                else:
                    version = (
                        f"{table.etag}:{table.last_modified}"
                        if table.etag or table.last_modified
                        else ""
                    )
                    obj = ImportSourceObject(
                        object_id=_safe_object_id(source_id),
                        provider=provider,
                        role=role,
                        logical_name=table.table_id,
                        source_identity=f"{table.project_id}.{table.dataset_id}.{table.table_id}",
                        version_identity=version,
                        object_type=table.object_type,
                        format=None,
                        schema_fingerprint=table.schema_fingerprint,
                        size_bytes=table.num_bytes,
                        row_estimate=table.num_rows,
                        source_metadata={"location": table.location},
                    )
            objects.append(obj)
            if assignment:
                roles.append(
                    RoleAssignment(object_id=obj.object_id, role=role, provider=provider)
                )
        return objects, roles


def compile_verified_gcs_upload(
    *,
    upload: DatasetUpload,
    role_assignments: list[RoleAssignment],
) -> PreM3ImportContractV1:
    """Test/helper path: compile a verified GCS upload without HTTP selection."""
    objects: list[ImportSourceObject] = []
    assigned = {item.object_id: item for item in role_assignments}
    for file_rec in upload.files:
        assignment = assigned.get(file_rec.upload_file_id)
        role = assignment.role if assignment else CanonicalRole.UNKNOWN
        provider = assignment.provider if assignment else "unresolved"
        fmt = gcs_format(filename=file_rec.original_filename, content_type=file_rec.content_type)
        objects.append(
            ImportSourceObject(
                object_id=file_rec.upload_file_id,
                provider=provider,
                role=role,
                logical_name=file_rec.original_filename,
                source_identity=file_rec.upload_file_id,
                version_identity=f"{file_rec.generation or ''}:{file_rec.md5_hash or ''}",
                object_type="file",
                format=fmt,
                schema_fingerprint=None,
                size_bytes=file_rec.actual_size_bytes or file_rec.declared_size_bytes,
                row_estimate=None,
                source_metadata={"generation": file_rec.generation or ""},
            )
        )
    now = datetime.now(UTC)
    draft = PreM3ImportContractV1(
        contract_version=IMPORT_CONTRACT_VERSION,
        tenant_id=upload.tenant_id,
        workspace_id=upload.workspace_id,
        dataset_id=upload.dataset_id,
        source_type=SourceType.GCS_UPLOAD,
        source_binding_id=upload.upload_id,
        objects=objects,
        role_assignments=role_assignments,
        created_at=now,
        verified_at=now,
        status=ImportReadinessStatus.NOT_IMPORT_READY,
        manifest_fingerprint="pending",
    )
    return draft.model_copy(update={"manifest_fingerprint": draft.compute_fingerprint()})


def _roles_by_object(
    assignments: tuple[dict[str, str], ...]
) -> dict[str, tuple[CanonicalRole, str]]:
    mapped: dict[str, tuple[CanonicalRole, str]] = {}
    for item in assignments:
        object_id = item.get("object_id") or item.get("selected_object_id") or ""
        role_raw = item.get("role") or CanonicalRole.UNKNOWN.value
        provider = item.get("provider") or "unresolved"
        try:
            role = CanonicalRole(role_raw)
        except ValueError:
            role = CanonicalRole.UNKNOWN
        if object_id:
            mapped[object_id] = (role, provider)
    return mapped


def _safe_object_id(source_id: str) -> str:
    try:
        return validate_resource_identifier(source_id, field="object_id")
    except InvalidResourceIdentifierError:
        return new_import_object_id()

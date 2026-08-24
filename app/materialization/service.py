"""Copy a current IMPORT_READY source into an immutable DatasetUpload."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.ids import new_materialization_id, new_receipt_id
from app.control_plane.models import DatasetUpload, Feature, UploadStatus
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.governance.codes import (
    ConnectionStatus,
    GovernanceCheckCode,
    ImportReadinessStatus,
    SourceType,
)
from app.governance.import_contract import ImportSourceObject
from app.materialization.bigquery import (
    BOUNDED_EXPORT_MAX_ROWS,
    BigQueryMaterializationRuntime,
    FakeBigQueryMaterializationRuntime,
)
from app.materialization.contracts import (
    MaterializationResultKind,
    MaterializationStatus,
    SourceMaterializationReceipt,
    SourceObjectLineage,
    authority_fingerprint,
    materialization_result_fingerprint,
)
from app.materialization.drive import (
    content_type_for_format,
    file_inside_root,
    supported_drive_format,
)
from app.materialization.foundation_compat import (
    FOUNDATION_SOURCE_READY,
    FoundationLineageError,
    FoundationSourceAuthorityDenied,
    FoundationSourceEvidence,
    FoundationSourceGate,
    NullFoundationSourceGate,
)
from app.service.entitlements import require_feature
from app.service.errors import governance_denied, resource_not_found
from app.service.google_oauth import GoogleConnectionService
from app.service.import_governance import ImportGovernanceService
from app.service.measurement_home_guard import deny_conflicted_measurement_home
from app.service.upload_config import UploadConfig
from app.service.upload_service import UploadService


class MaterializationService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        import_governance: ImportGovernanceService,
        upload_service: UploadService,
        connections: GoogleConnectionService,
        drive,
        bigquery,
        object_store,
        upload_config: UploadConfig,
        foundation_gate: FoundationSourceGate | None = None,
        bq_runtime: BigQueryMaterializationRuntime | None = None,
    ) -> None:
        self._repo = repo
        self._import_governance = import_governance
        self._uploads = upload_service
        self._connections = connections
        self._drive = drive
        self._bigquery = bigquery
        self._store = object_store
        self._upload_config = upload_config
        self._foundation = foundation_gate or NullFoundationSourceGate()
        self._bq_runtime = bq_runtime or FakeBigQueryMaterializationRuntime(bigquery)

    def list_materializations(
        self, *, workspace_id: str, dataset_id: str
    ) -> list[SourceMaterializationReceipt]:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        return self._repo.list_materializations(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )

    def get_materialization(
        self, *, workspace_id: str, dataset_id: str, materialization_id: str
    ) -> SourceMaterializationReceipt:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        receipt = self._repo.get_materialization(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            materialization_id=materialization_id,
        )
        if receipt is None:
            raise resource_not_found()
        return receipt

    def materialize(
        self,
        *,
        workspace_id: str,
        dataset_id: str,
        idempotency_key: str | None = None,
    ) -> SourceMaterializationReceipt:
        require_feature(self._repo, Feature.DATA_UPLOAD)
        tenant = require_tenant()
        deny_conflicted_measurement_home(
            self._repo, tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        dataset = self._repo.get_dataset_for_workspace(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )
        if dataset is None:
            raise resource_not_found()
        receipt = self._repo.get_current_import_receipt(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )
        if receipt is None or receipt.status is not ImportReadinessStatus.IMPORT_READY:
            raise governance_denied(
                code=GovernanceCheckCode.IMPORT_NOT_READY.value,
                detail="A current IMPORT_READY receipt is required before materialization.",
            )
        if receipt.superseded:
            raise governance_denied(
                code=GovernanceCheckCode.IMPORT_RECEIPT_SUPERSEDED.value,
                detail="The import receipt has been superseded. Re-run import governance.",
            )
        selection = self._repo.get_import_selection(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id, dataset_id=dataset_id
        )
        if selection is None:
            raise governance_denied(
                code=GovernanceCheckCode.IMPORT_NOT_READY.value,
                detail="Dataset import selection is required before materialization.",
            )
        live = self._import_governance.compile_contract(selection)
        if live.compute_fingerprint() != receipt.manifest_fingerprint:
            raise governance_denied(
                code=GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                detail="Source version changed since IMPORT_READY. Re-run import governance.",
            )
        source_binding_id = (
            live.source_binding_id or selection.binding_id or selection.upload_id or ""
        )
        source_identities = tuple(item.source_identity for item in live.objects)
        import_roles = tuple(item.role.value for item in live.objects)
        try:
            foundation = self._foundation.get_source_materialization_evidence(
                tenant_id=tenant.tenant_id,
                workspace_id=workspace_id,
                source_binding_id=source_binding_id,
                source_identities=source_identities,
                import_roles=import_roles,
            )
        except FoundationSourceAuthorityDenied:
            raise resource_not_found() from None
        except FoundationLineageError as exc:
            raise governance_denied(
                code=GovernanceCheckCode.FOUNDATION_LINEAGE_MISMATCH.value,
                detail=exc.detail,
            ) from exc
        if foundation is not None:
            self._require_dual_gate(
                foundation,
                tenant_id=tenant.tenant_id,
                workspace_id=workspace_id,
                source_binding_id=foundation.source_binding_id,
            )
        versions = [item.version_identity for item in live.objects]
        authority = authority_fingerprint(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            import_receipt_id=receipt.receipt_id,
            import_status=receipt.status.value,
            import_manifest_fingerprint=receipt.manifest_fingerprint,
            source_version_identities=versions,
            foundation_source_receipt_id=(
                None if foundation is None else foundation.source_foundation_receipt_id
            ),
            foundation_status=None if foundation is None else foundation.status_code,
        )
        if idempotency_key:
            cached = self._repo.get_idempotent_result(
                tenant_id=tenant.tenant_id,
                operation="materialize_dataset_source",
                key=idempotency_key,
            )
            if cached is not None:
                existing = self._repo.get_materialization(
                    tenant_id=tenant.tenant_id,
                    workspace_id=workspace_id,
                    dataset_id=dataset_id,
                    materialization_id=str(cached["materialization_id"]),
                )
                if existing is not None and existing.status is MaterializationStatus.COMPLETE:
                    return existing
        reused = self._repo.get_materialization_by_authority(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            authority_fingerprint=authority,
        )
        if reused is not None and reused.status is MaterializationStatus.COMPLETE:
            return reused
        primary = live.objects[0] if live.objects else None
        now = datetime.now(UTC)
        materialization_id = new_materialization_id()
        try:
            upload, result_kind, lineages = self._copy_or_reuse(
                source_type=live.source_type,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                objects=live.objects,
                selection_upload_id=selection.upload_id,
                connection_id=selection.connection_id,
                binding_id=selection.binding_id,
            )
        except MaterializationFailure as exc:
            failed = self._failed_receipt(
                materialization_id=materialization_id,
                tenant_id=tenant.tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                source_type=live.source_type,
                source_binding_id=live.source_binding_id,
                import_receipt_id=receipt.receipt_id,
                import_manifest_fingerprint=receipt.manifest_fingerprint,
                foundation=foundation,
                objects=live.objects,
                versions=versions,
                authority=authority,
                started_at=now,
                primary=primary,
                code=exc.code,
                detail=exc.detail,
            )
            stored = self._repo.put_materialization(failed)
            raise governance_denied(code=exc.code, detail=exc.detail) from exc
        completed = datetime.now(UTC)
        result_fp = materialization_result_fingerprint(
            authority=authority,
            upload_id=upload.upload_id,
            upload_package_fingerprint=upload.package_fingerprint,
        )
        completed_receipt = SourceMaterializationReceipt(
            receipt_id=new_receipt_id(),
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            materialization_id=materialization_id,
            source_type=live.source_type,
            source_binding_id=live.source_binding_id,
            import_receipt_id=receipt.receipt_id,
            import_manifest_fingerprint=receipt.manifest_fingerprint,
            foundation_source_receipt_id=(
                None if foundation is None else foundation.source_foundation_receipt_id
            ),
            foundation_status=None if foundation is None else foundation.status_code,
            business_profile_snapshot_id=(
                None if foundation is None else foundation.business_profile_snapshot_id
            ),
            business_profile_snapshot_fingerprint=(
                None
                if foundation is None
                else foundation.business_profile_snapshot_fingerprint
            ),
            evidence_requirement_ids=(
                [] if foundation is None else list(foundation.evidence_requirement_ids)
            ),
            source_objects=lineages,
            source_version_identities=versions,
            status=MaterializationStatus.COMPLETE,
            result_kind=result_kind,
            upload_id=upload.upload_id,
            upload_package_fingerprint=upload.package_fingerprint,
            upload_status=upload.status.value,
            authority_fingerprint=authority,
            materialization_fingerprint=result_fp,
            started_at=now,
            completed_at=completed,
            premodel_review_remaining=(
                False if foundation is None else foundation.premodel_review_remaining
            ),
            premodel_review_findings=(
                [] if foundation is None else list(foundation.premodel_review_findings)
            ),
            provider=None if foundation is None else foundation.provider,
            business_role=(
                None
                if foundation is None
                else foundation.business_role
            )
            or (None if primary is None else primary.role.value),
            history=None if foundation is None else foundation.history,
            refresh_cadence=None if foundation is None else foundation.refresh_cadence,
            freshness=None if foundation is None else foundation.freshness,
            grain=None if foundation is None else foundation.grain,
            geography=None if foundation is None else foundation.geography,
            metrics=[] if foundation is None else list(foundation.metrics),
        )
        if completed_receipt.provider is None and primary is not None:
            completed_receipt = completed_receipt.model_copy(
                update={"provider": primary.provider}
            )
        stored = self._repo.put_materialization(completed_receipt)
        if idempotency_key:
            self._repo.put_idempotent_result(
                tenant_id=tenant.tenant_id,
                operation="materialize_dataset_source",
                key=idempotency_key,
                result={"materialization_id": stored.materialization_id},
            )
        return stored

    def _require_dual_gate(
        self,
        foundation: FoundationSourceEvidence,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
    ) -> None:
        lineage_ok = (
            (foundation.tenant_id is None or foundation.tenant_id == tenant_id)
            and (foundation.workspace_id is None or foundation.workspace_id == workspace_id)
            and foundation.source_binding_id == source_binding_id
        )
        ready = (
            foundation.status_code == FOUNDATION_SOURCE_READY
            and foundation.governance_import_ready
            and lineage_ok
        )
        if not ready:
            raise governance_denied(
                code=GovernanceCheckCode.FOUNDATION_SOURCE_NOT_READY.value,
                detail="Data Foundation-managed sources require FOUNDATION_SOURCE_READY.",
            )

    def _copy_or_reuse(
        self,
        *,
        source_type: SourceType,
        workspace_id: str,
        dataset_id: str,
        objects: list[ImportSourceObject],
        selection_upload_id: str | None,
        connection_id: str | None,
        binding_id: str | None,
    ) -> tuple[DatasetUpload, MaterializationResultKind, list[SourceObjectLineage]]:
        if source_type is SourceType.GCS_UPLOAD:
            return self._reuse_gcs(
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                upload_id=selection_upload_id,
                objects=objects,
            )
        files = self._load_source_bytes(
            source_type=source_type,
            objects=objects,
            connection_id=connection_id,
            binding_id=binding_id,
            workspace_id=workspace_id,
        )
        if len(files) != len(objects):
            raise MaterializationFailure(
                GovernanceCheckCode.SOURCE_COPY_INCOMPLETE.value,
                "Partial logical source copy is not VERIFIED.",
            )
        created, _signed = self._uploads.create_upload(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            files=[
                {
                    "filename": item["filename"],
                    "content_type": item["content_type"],
                    "size_bytes": len(item["data"]),
                }
                for item in files
            ],
        )
        try:
            for file_rec, item in zip(created.files, files, strict=True):
                self._store.write_bytes(
                    bucket=self._upload_config.raw_bucket,
                    object_name=file_rec.object_name,
                    data=item["data"],
                    content_type=item["content_type"],
                )
        except Exception as exc:
            raise MaterializationFailure(
                GovernanceCheckCode.SOURCE_COPY_INCOMPLETE.value,
                "Source bytes could not be written to DatasetUpload storage.",
            ) from exc
        verified = self._uploads.complete_upload(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=created.upload_id,
        )
        if verified.status is not UploadStatus.VERIFIED:
            raise MaterializationFailure(
                GovernanceCheckCode.UPLOAD_VERIFICATION_FAILED.value,
                "DatasetUpload verification failed.",
            )
        lineages = [
            SourceObjectLineage(
                object_id=src.object_id,
                provider=src.provider,
                role=src.role.value,
                logical_name=src.logical_name,
                source_identity=src.source_identity,
                version_identity=src.version_identity,
                object_type=src.object_type,
                format=src.format,
                schema_fingerprint=src.schema_fingerprint,
                upload_file_id=file_rec.upload_file_id,
                target_generation=file_rec.generation,
                target_checksum=file_rec.md5_hash or file_rec.crc32c,
            )
            for src, file_rec in zip(objects, verified.files, strict=True)
        ]
        return verified, MaterializationResultKind.CREATED_NEW_UPLOAD, lineages

    def _reuse_gcs(
        self,
        *,
        workspace_id: str,
        dataset_id: str,
        upload_id: str | None,
        objects: list[ImportSourceObject],
    ) -> tuple[DatasetUpload, MaterializationResultKind, list[SourceObjectLineage]]:
        if not upload_id:
            raise MaterializationFailure(
                GovernanceCheckCode.IMPORT_NOT_READY.value,
                "GCS_UPLOAD materialization requires the bound DatasetUpload.",
            )
        tenant = require_tenant()
        upload = self._repo.get_upload(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=upload_id,
        )
        if upload is None or upload.status is not UploadStatus.VERIFIED:
            raise MaterializationFailure(
                GovernanceCheckCode.UPLOAD_VERIFICATION_FAILED.value,
                "GCS_UPLOAD reuse requires an existing VERIFIED DatasetUpload.",
            )
        by_id = {item.upload_file_id: item for item in upload.files}
        for obj in objects:
            file_rec = by_id.get(obj.source_identity)
            if file_rec is None:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "Bound upload object set no longer matches the import contract.",
                )
            current = f"{file_rec.generation or ''}:{file_rec.md5_hash or file_rec.crc32c or ''}"
            if current != obj.version_identity:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "Upload object generation changed since IMPORT_READY.",
                )
        lineages = [
            SourceObjectLineage(
                object_id=obj.object_id,
                provider=obj.provider,
                role=obj.role.value,
                logical_name=obj.logical_name,
                source_identity=obj.source_identity,
                version_identity=obj.version_identity,
                object_type=obj.object_type,
                format=obj.format,
                schema_fingerprint=obj.schema_fingerprint,
                upload_file_id=obj.source_identity,
                target_generation=by_id[obj.source_identity].generation,
                target_checksum=by_id[obj.source_identity].md5_hash,
            )
            for obj in objects
        ]
        return upload, MaterializationResultKind.REUSED_EXISTING_UPLOAD, lineages

    def _load_source_bytes(
        self,
        *,
        source_type: SourceType,
        objects: list[ImportSourceObject],
        connection_id: str | None,
        binding_id: str | None,
        workspace_id: str,
    ) -> list[dict[str, object]]:
        tenant = require_tenant()
        if not connection_id:
            raise MaterializationFailure(
                GovernanceCheckCode.GOOGLE_REAUTH_REQUIRED.value,
                "An active Google connection is required.",
            )
        connection = self._repo.get_google_connection(
            tenant_id=tenant.tenant_id, connection_id=connection_id
        )
        if connection is None or connection.status != ConnectionStatus.ACTIVE.value:
            raise MaterializationFailure(
                GovernanceCheckCode.GOOGLE_REAUTH_REQUIRED.value,
                "Google connection is not active.",
            )
        access_token = self._connections.user_access_token(connection=connection)
        if source_type is SourceType.GOOGLE_DRIVE:
            return self._download_drive(
                access_token=access_token,
                objects=objects,
                workspace_id=workspace_id,
            )
        return self._export_bigquery(access_token=access_token, objects=objects)

    def _download_drive(
        self,
        *,
        access_token: str,
        objects: list[ImportSourceObject],
        workspace_id: str,
    ) -> list[dict[str, object]]:
        tenant = require_tenant()
        binding = self._repo.get_drive_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if binding is None:
            raise MaterializationFailure(
                GovernanceCheckCode.SOURCE_MATERIALIZATION_FAILED.value,
                "Drive root binding is required.",
            )
        files: list[dict[str, object]] = []
        for obj in objects:
            meta = self._drive.get_file(access_token=access_token, file_id=obj.source_identity)
            if meta is None or meta.trashed:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "Drive file is missing or trashed.",
                )
            if not file_inside_root(
                self._drive,
                access_token=access_token,
                file=meta,
                root_folder_id=binding.root_folder_id,
            ):
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_MATERIALIZATION_FAILED.value,
                    "Drive file is outside the bound prem3-modeling root.",
                )
            fmt = supported_drive_format(meta)
            if fmt is None:
                raise MaterializationFailure(
                    GovernanceCheckCode.FORMAT_UNSUPPORTED.value,
                    "Direct Google Sheets and unsupported Drive formats cannot be materialized.",
                )
            version = meta.md5 or meta.head_revision_id or meta.version or ""
            if version != obj.version_identity:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "Drive revision changed since IMPORT_READY.",
                )
            data = self._drive.download_file(access_token=access_token, file_id=meta.file_id)
            if not data:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_COPY_INCOMPLETE.value,
                    "Drive file download returned no bytes.",
                )
            filename = obj.logical_name
            if not filename.endswith(f".{fmt}") and "." not in filename:
                filename = f"{filename}.{fmt}"
            files.append(
                {
                    "filename": filename,
                    "content_type": content_type_for_format(fmt),
                    "data": data,
                }
            )
        return files

    def _export_bigquery(
        self, *, access_token: str, objects: list[ImportSourceObject]
    ) -> list[dict[str, object]]:
        files: list[dict[str, object]] = []
        for obj in objects:
            parts = obj.source_identity.split(".")
            if len(parts) != 3:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_MATERIALIZATION_FAILED.value,
                    "BigQuery source identity is not a frozen project.dataset.table.",
                )
            project_id, dataset_id, table_id = parts
            table = self._bigquery.get_table(
                access_token=access_token,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
            )
            if table is None:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "BigQuery table is missing.",
                )
            version = (
                f"{table.etag}:{table.last_modified}"
                if table.etag or table.last_modified
                else ""
            )
            if version != obj.version_identity:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "BigQuery version identity changed since IMPORT_READY.",
                )
            if obj.schema_fingerprint and table.schema_fingerprint != obj.schema_fingerprint:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "BigQuery schema fingerprint changed since IMPORT_READY.",
                )
            try:
                exported = self._bq_runtime.export_table(
                    access_token=access_token,
                    project_id=project_id,
                    dataset_id=dataset_id,
                    table_id=table_id,
                    max_rows=BOUNDED_EXPORT_MAX_ROWS,
                )
            except OverflowError as exc:
                raise MaterializationFailure(
                    GovernanceCheckCode.MATERIALIZATION_LIMIT_EXCEEDED.value,
                    "BigQuery materialization is bounded at 100000 rows. "
                    "Unsupported size is rejected; the table is not truncated.",
                ) from exc
            except LookupError as exc:
                raise MaterializationFailure(
                    GovernanceCheckCode.SOURCE_CHANGED_SINCE_IMPORT_READY.value,
                    "BigQuery table could not be exported.",
                ) from exc
            files.append(
                {
                    "filename": exported.filename
                    if exported.filename.endswith(".json")
                    else f"{table_id}.json",
                    "content_type": exported.content_type,
                    "data": exported.payload,
                }
            )
        return files

    def _failed_receipt(
        self,
        *,
        materialization_id: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        source_type: SourceType,
        source_binding_id: str | None,
        import_receipt_id: str,
        import_manifest_fingerprint: str,
        foundation: FoundationSourceEvidence | None,
        objects: list[ImportSourceObject],
        versions: list[str],
        authority: str,
        started_at: datetime,
        primary: ImportSourceObject | None,
        code: str,
        detail: str,
    ) -> SourceMaterializationReceipt:
        return SourceMaterializationReceipt(
            receipt_id=new_receipt_id(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            materialization_id=materialization_id,
            source_type=source_type,
            source_binding_id=source_binding_id,
            import_receipt_id=import_receipt_id,
            import_manifest_fingerprint=import_manifest_fingerprint,
            foundation_source_receipt_id=(
                None if foundation is None else foundation.source_foundation_receipt_id
            ),
            foundation_status=None if foundation is None else foundation.status_code,
            business_profile_snapshot_id=(
                None if foundation is None else foundation.business_profile_snapshot_id
            ),
            business_profile_snapshot_fingerprint=(
                None
                if foundation is None
                else foundation.business_profile_snapshot_fingerprint
            ),
            evidence_requirement_ids=(
                [] if foundation is None else list(foundation.evidence_requirement_ids)
            ),
            source_objects=[
                SourceObjectLineage(
                    object_id=item.object_id,
                    provider=item.provider,
                    role=item.role.value,
                    logical_name=item.logical_name,
                    source_identity=item.source_identity,
                    version_identity=item.version_identity,
                    object_type=item.object_type,
                    format=item.format,
                    schema_fingerprint=item.schema_fingerprint,
                )
                for item in objects
            ],
            source_version_identities=versions,
            status=MaterializationStatus.FAILED,
            authority_fingerprint=authority,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            premodel_review_remaining=(
                False if foundation is None else foundation.premodel_review_remaining
            ),
            premodel_review_findings=(
                [] if foundation is None else list(foundation.premodel_review_findings)
            ),
            failure_code=code,
            failure_detail=detail,
            provider=None if primary is None else primary.provider,
            business_role=None if primary is None else primary.role.value,
        )


class MaterializationFailure(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

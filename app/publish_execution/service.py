"""Execute PUBLISH_READY destinations and persist verification receipts."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.ids import new_publish_id, new_receipt_id
from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.governance.codes import (
    BIGQUERY_DEPOT_DATASET_ID,
    PUBLISH_DRIVE_ARTIFACTS,
    BindingStatus,
    ConnectionStatus,
    GovernanceCheckCode,
    PublishReadinessStatus,
)
from app.governance.publish_contract import PublishDestinationKind
from app.governance.publish_evaluator import (
    customer_model_ready_current_view_id,
    customer_model_ready_table_id,
)
from app.materialization.drive import PROTECTED_DRIVE_PLANES
from app.publish_execution.contracts import (
    DestinationResult,
    DestinationResultKind,
    DestinationWriteStatus,
    PublishedArtifact,
    PublishExecutionReceipt,
    PublishExecutionStatus,
    publish_authority_fingerprint,
)
from app.publish_execution.model_ready import ModelReadyEvidenceResolver
from app.publish_execution.namespace import is_reserved_bigquery_table
from app.service.entitlements import require_feature
from app.service.errors import governance_denied, resource_not_found
from app.service.google_oauth import GoogleConnectionService
from app.service.publish_governance import PublishGovernanceService


class PublishExecutionService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        publish_governance: PublishGovernanceService,
        connections: GoogleConnectionService,
        drive,
        bigquery,
        model_ready: ModelReadyEvidenceResolver,
    ) -> None:
        self._repo = repo
        self._governance = publish_governance
        self._connections = connections
        self._drive = drive
        self._bigquery = bigquery
        self._model_ready = model_ready

    def list_publishes(
        self, *, workspace_id: str, dataset_id: str, run_id: str
    ) -> list[PublishExecutionReceipt]:
        require_feature(self._repo, Feature.BIGQUERY_PUBLISH)
        tenant = require_tenant()
        return self._repo.list_publish_executions(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )

    def get_publish(
        self, *, workspace_id: str, dataset_id: str, run_id: str, publish_id: str
    ) -> PublishExecutionReceipt:
        require_feature(self._repo, Feature.BIGQUERY_PUBLISH)
        tenant = require_tenant()
        receipt = self._repo.get_publish_execution(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
            publish_id=publish_id,
        )
        if receipt is None:
            raise resource_not_found()
        return receipt

    def get_publish_readiness(
        self, *, workspace_id: str, dataset_id: str, run_id: str
    ):
        require_feature(self._repo, Feature.BIGQUERY_PUBLISH)
        tenant = require_tenant()
        stored = self._repo.get_current_publish_receipt(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
        if stored is None:
            raise resource_not_found()
        return stored

    def publish(
        self, *, workspace_id: str, dataset_id: str, run_id: str
    ) -> PublishExecutionReceipt:
        require_feature(self._repo, Feature.BIGQUERY_PUBLISH)
        tenant = require_tenant()
        evaluation = self._repo.get_evaluation_ref(tenant_id=tenant.tenant_id, run_id=run_id)
        if (
            evaluation is None
            or evaluation.workspace_id != workspace_id
            or evaluation.dataset_id != dataset_id
        ):
            raise resource_not_found()
        contract, readiness = self._governance.evaluate(
            workspace_id=workspace_id, dataset_id=dataset_id, run_id=run_id
        )
        self._repo.put_publish_receipt(readiness)
        if readiness.status is not PublishReadinessStatus.PUBLISH_READY:
            raise governance_denied(
                code=GovernanceCheckCode.PUBLISH_NOT_READY.value,
                detail="PUBLISH_READY is required before customer publication.",
            )
        if not contract.model_ready_fingerprint:
            raise governance_denied(
                code=GovernanceCheckCode.MODEL_READY_REQUIRED.value,
                detail="MODEL_READY fingerprint is required before publication.",
            )
        evidence = self._model_ready.resolve(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
        if evidence is None or evidence.fingerprint != contract.model_ready_fingerprint:
            raise governance_denied(
                code=GovernanceCheckCode.MODEL_READY_REQUIRED.value,
                detail="Deterministic MODEL_READY evidence does not match the publish contract.",
            )
        bindings = [item.binding_id for item in contract.destinations]
        authority = publish_authority_fingerprint(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
            model_ready_fingerprint=contract.model_ready_fingerprint,
            publish_contract_fingerprint=contract.contract_fingerprint,
            destination_bindings=bindings,
        )
        existing = self._repo.get_publish_execution_by_authority(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
            authority_fingerprint=authority,
        )
        if existing is not None and existing.status is PublishExecutionStatus.COMPLETE:
            return existing
        started = datetime.now(UTC)
        publish_id = new_publish_id()
        results: list[DestinationResult] = []
        for dest in contract.destinations:
            if dest.kind is PublishDestinationKind.GOOGLE_DRIVE:
                results.append(
                    self._publish_drive(
                        workspace_id=workspace_id,
                        dataset_id=dataset_id,
                        run_id=run_id,
                        dest_binding=dest.binding_id,
                        dest_identity=dest.target_identity,
                        evidence_artifacts=evidence.artifacts,
                    )
                )
            else:
                results.append(
                    self._publish_bigquery(
                        workspace_id=workspace_id,
                        dest_binding=dest.binding_id,
                        dest_identity=dest.target_identity,
                        location=dest.location or "",
                        dataset_id=dataset_id,
                        run_id=run_id,
                        evidence=evidence,
                    )
                )
        verified_count = sum(
            1
            for item in results
            if item.status
            in {DestinationWriteStatus.VERIFIED, DestinationWriteStatus.VERIFIED_EXISTING}
        )
        if verified_count == len(results) and results:
            status = PublishExecutionStatus.COMPLETE
            failure_code = None
        elif verified_count:
            status = PublishExecutionStatus.PARTIAL
            failure_code = GovernanceCheckCode.PARTIAL_PUBLISH.value
        else:
            status = PublishExecutionStatus.FAILED
            failure_code = GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value
        receipt = PublishExecutionReceipt(
            receipt_id=new_receipt_id(),
            publish_id=publish_id,
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
            publish_contract_fingerprint=contract.contract_fingerprint,
            publish_readiness_receipt_id=readiness.receipt_id,
            model_ready_fingerprint=contract.model_ready_fingerprint,
            status=status,
            destination_results=results,
            started_at=started,
            completed_at=datetime.now(UTC),
            failure_code=failure_code,
            failure_detail=None
            if status is PublishExecutionStatus.COMPLETE
            else "One or more destinations were not verified.",
        )
        stored = self._repo.put_publish_execution(receipt, authority_fingerprint=authority)
        if status is PublishExecutionStatus.FAILED:
            raise governance_denied(
                code=failure_code or GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value,
                detail=stored.failure_detail or "Publish verification failed.",
            )
        return stored

    def _access_token(self, *, workspace_id: str, connection_id: str) -> str:
        tenant = require_tenant()
        connection = self._repo.get_google_connection(
            tenant_id=tenant.tenant_id, connection_id=connection_id
        )
        if connection is None or connection.status != ConnectionStatus.ACTIVE.value:
            raise governance_denied(
                code=GovernanceCheckCode.GOOGLE_REAUTH_REQUIRED.value,
                detail="Google connection is not active.",
            )
        return self._connections.user_access_token(connection=connection)

    def _publish_drive(
        self,
        *,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
        dest_binding: str,
        dest_identity: str,
        evidence_artifacts: dict[str, bytes],
    ) -> DestinationResult:
        tenant = require_tenant()
        binding = self._repo.get_drive_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if binding is None or binding.status != BindingStatus.ACTIVE.value:
            return DestinationResult(
                kind=DestinationResultKind.GOOGLE_DRIVE,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.DESTINATION_NOT_WRITABLE.value,
                failure_detail="Drive binding is not writable.",
            )
        if dest_binding != binding.root_folder_id:
            return DestinationResult(
                kind=DestinationResultKind.GOOGLE_DRIVE,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.DESTINATION_NOT_WRITABLE.value,
                failure_detail="Caller cannot override the bound Drive root.",
            )
        missing = [name for name in PUBLISH_DRIVE_ARTIFACTS if name not in evidence_artifacts]
        if missing:
            return DestinationResult(
                kind=DestinationResultKind.GOOGLE_DRIVE,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.PUBLISH_ARTIFACT_MISSING.value,
                failure_detail="Required MODEL_READY artifacts are missing.",
            )
        try:
            token = self._access_token(
                workspace_id=workspace_id, connection_id=binding.connection_id
            )
            run_folder = self._ensure_export_folder(
                access_token=token,
                exports_folder_id=binding.exports_folder_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                run_id=run_id,
            )
            written: list[PublishedArtifact] = []
            verified: list[PublishedArtifact] = []
            all_existing = True
            for name in PUBLISH_DRIVE_ARTIFACTS:
                existing = self._drive.find_child(
                    access_token=token, parent_id=run_folder.file_id, name=name
                )
                data = evidence_artifacts[name]
                if existing is not None:
                    if existing.size_bytes != len(data):
                        return DestinationResult(
                            kind=DestinationResultKind.GOOGLE_DRIVE,
                            binding_id=dest_binding,
                            target_presentation_identity=dest_identity,
                            status=DestinationWriteStatus.FAILED,
                            failure_code=GovernanceCheckCode.PUBLISH_TARGET_CONFLICT.value,
                            failure_detail=f"Existing Drive artifact {name} conflicts.",
                        )
                    artifact = PublishedArtifact(
                        name=name,
                        identity=existing.file_id,
                        size_bytes=existing.size_bytes,
                        checksum=existing.md5,
                        verified=True,
                    )
                    written.append(artifact)
                    verified.append(artifact)
                    continue
                all_existing = False
                uploaded = self._drive.upload_file(
                    access_token=token,
                    name=name,
                    parent_id=run_folder.file_id,
                    data=data,
                    mime_type=_drive_mime(name),
                )
                if uploaded.parents and any(
                    self._folder_name(token, parent) in PROTECTED_DRIVE_PLANES
                    for parent in uploaded.parents
                ):
                    return DestinationResult(
                        kind=DestinationResultKind.GOOGLE_DRIVE,
                        binding_id=dest_binding,
                        target_presentation_identity=dest_identity,
                        status=DestinationWriteStatus.FAILED,
                        failure_code=GovernanceCheckCode.PUBLISH_TARGET_CONFLICT.value,
                        failure_detail="Drive publish cannot write input evidence planes.",
                    )
                reread = self._drive.get_file(access_token=token, file_id=uploaded.file_id)
                if reread is None or reread.size_bytes != len(data):
                    return DestinationResult(
                        kind=DestinationResultKind.GOOGLE_DRIVE,
                        binding_id=dest_binding,
                        target_presentation_identity=dest_identity,
                        status=DestinationWriteStatus.FAILED,
                        failure_code=GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value,
                        failure_detail=f"Drive readback failed for {name}.",
                    )
                artifact = PublishedArtifact(
                    name=name,
                    identity=reread.file_id,
                    size_bytes=reread.size_bytes,
                    checksum=reread.md5,
                    verified=True,
                )
                written.append(artifact)
                verified.append(artifact)
            presentation = (
                f"prem3-modeling/exports/{workspace_id}/{dataset_id}/{run_id}/"
            )
            return DestinationResult(
                kind=DestinationResultKind.GOOGLE_DRIVE,
                binding_id=dest_binding,
                target_presentation_identity=presentation,
                versioned_resource_identity=run_folder.file_id,
                artifacts_written=written,
                artifacts_verified=verified,
                write_completed=True,
                readback_verified=True,
                status=(
                    DestinationWriteStatus.VERIFIED_EXISTING
                    if all_existing
                    else DestinationWriteStatus.VERIFIED
                ),
            )
        except Exception:
            return DestinationResult(
                kind=DestinationResultKind.GOOGLE_DRIVE,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value,
                failure_detail="Drive publication failed.",
            )

    def _folder_name(self, access_token: str, folder_id: str) -> str:
        folder = self._drive.get_file(access_token=access_token, file_id=folder_id)
        return "" if folder is None else folder.name

    def _ensure_export_folder(
        self,
        *,
        access_token: str,
        exports_folder_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
    ):
        current = self._drive.get_file(access_token=access_token, file_id=exports_folder_id)
        if current is None or current.trashed:
            raise FileNotFoundError(exports_folder_id)
        for name in (workspace_id, dataset_id, run_id):
            child = self._drive.find_child(
                access_token=access_token, parent_id=current.file_id, name=name
            )
            if child is None:
                child = self._drive.create_folder(
                    access_token=access_token, name=name, parent_id=current.file_id
                )
            current = child
        return current

    def _publish_bigquery(
        self,
        *,
        workspace_id: str,
        dest_binding: str,
        dest_identity: str,
        location: str,
        dataset_id: str,
        run_id: str,
        evidence,
    ) -> DestinationResult:
        tenant = require_tenant()
        binding = self._repo.get_bigquery_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if binding is None or not binding.write_verified:
            return DestinationResult(
                kind=DestinationResultKind.BIGQUERY,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.DESTINATION_NOT_WRITABLE.value,
                failure_detail="BigQuery destination is not writable.",
            )
        expected_binding = f"{binding.destination_project_id}.{binding.destination_dataset_id}"
        if dest_binding != expected_binding:
            return DestinationResult(
                kind=DestinationResultKind.BIGQUERY,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.DESTINATION_NOT_WRITABLE.value,
                failure_detail="Caller cannot override the bound BigQuery destination.",
            )
        table_id = customer_model_ready_table_id(dataset_id, run_id)
        view_id = customer_model_ready_current_view_id(dataset_id)
        if is_reserved_bigquery_table(table_id) or is_reserved_bigquery_table(view_id):
            return DestinationResult(
                kind=DestinationResultKind.BIGQUERY,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.PUBLISH_TARGET_CONFLICT.value,
                failure_detail="Publish target collides with Data Foundation namespace.",
            )
        columns = ["artifact", "bytes"]
        rows = [[name, len(payload)] for name, payload in sorted(evidence.artifacts.items())]
        fingerprint = evidence.fingerprint
        try:
            token = self._access_token(
                workspace_id=workspace_id, connection_id=binding.connection_id
            )
            existing = self._bigquery.get_table_rows(
                access_token=token,
                project_id=binding.destination_project_id,
                dataset_id=BIGQUERY_DEPOT_DATASET_ID,
                table_id=table_id,
            )
            if existing is not None:
                if existing[1] != rows:
                    return DestinationResult(
                        kind=DestinationResultKind.BIGQUERY,
                        binding_id=dest_binding,
                        target_presentation_identity=dest_identity,
                        status=DestinationWriteStatus.FAILED,
                        failure_code=GovernanceCheckCode.PUBLISH_TARGET_CONFLICT.value,
                        failure_detail="Existing versioned model-ready table conflicts.",
                    )
                status = DestinationWriteStatus.VERIFIED_EXISTING
            else:
                written = self._bigquery.write_versioned_table(
                    access_token=token,
                    project_id=binding.destination_project_id,
                    dataset_id=BIGQUERY_DEPOT_DATASET_ID,
                    table_id=table_id,
                    columns=columns,
                    rows=rows,
                    location=location or binding.location,
                )
                readback = self._bigquery.get_table_rows(
                    access_token=token,
                    project_id=binding.destination_project_id,
                    dataset_id=BIGQUERY_DEPOT_DATASET_ID,
                    table_id=table_id,
                )
                if readback is None or readback[1] != rows or written.num_rows != len(rows):
                    return DestinationResult(
                        kind=DestinationResultKind.BIGQUERY,
                        binding_id=dest_binding,
                        target_presentation_identity=dest_identity,
                        versioned_resource_identity=table_id,
                        write_completed=True,
                        readback_verified=False,
                        status=DestinationWriteStatus.FAILED,
                        failure_code=GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value,
                        failure_detail="Versioned table readback failed.",
                    )
                status = DestinationWriteStatus.VERIFIED
            view = self._bigquery.set_current_view(
                access_token=token,
                project_id=binding.destination_project_id,
                dataset_id=BIGQUERY_DEPOT_DATASET_ID,
                view_id=view_id,
                table_id=table_id,
            )
            pointer = self._bigquery.get_current_view(
                access_token=token,
                project_id=binding.destination_project_id,
                dataset_id=BIGQUERY_DEPOT_DATASET_ID,
                view_id=view_id,
            )
            if pointer is None or pointer.get("table_id") != table_id:
                return DestinationResult(
                    kind=DestinationResultKind.BIGQUERY,
                    binding_id=dest_binding,
                    target_presentation_identity=dest_identity,
                    versioned_resource_identity=table_id,
                    write_completed=True,
                    readback_verified=False,
                    status=DestinationWriteStatus.FAILED,
                    failure_code=GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value,
                    failure_detail="Current model-ready pointer did not verify.",
                )
            presentation = (
                f"{binding.destination_project_id}.{BIGQUERY_DEPOT_DATASET_ID}.{table_id}"
            )
            return DestinationResult(
                kind=DestinationResultKind.BIGQUERY,
                binding_id=dest_binding,
                target_presentation_identity=presentation,
                versioned_resource_identity=table_id,
                stable_pointer_identity=view.get("view_id"),
                row_count=len(rows),
                schema_fingerprint=evidence.schema_fingerprint,
                content_fingerprint=fingerprint,
                write_completed=True,
                readback_verified=True,
                status=status,
            )
        except PermissionError:
            return DestinationResult(
                kind=DestinationResultKind.BIGQUERY,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.PUBLISH_TARGET_CONFLICT.value,
                failure_detail="Publish target collides with Data Foundation namespace.",
            )
        except Exception:
            return DestinationResult(
                kind=DestinationResultKind.BIGQUERY,
                binding_id=dest_binding,
                target_presentation_identity=dest_identity,
                status=DestinationWriteStatus.FAILED,
                failure_code=GovernanceCheckCode.PUBLISH_VERIFICATION_FAILED.value,
                failure_detail="BigQuery publication failed.",
            )


def _drive_mime(name: str) -> str:
    if name.endswith(".html"):
        return "text/html"
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".parquet"):
        return "application/parquet"
    return "application/octet-stream"

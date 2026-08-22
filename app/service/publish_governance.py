"""Compile publish contracts from MODEL_READY evidence and bound destinations."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.governance.codes import (
    BIGQUERY_DEPOT_DATASET_ID,
    DRIVE_DEPOT_NAME,
    PUBLISH_CONTRACT_VERSION,
    PUBLISH_DRIVE_ARTIFACTS,
    BindingStatus,
    PublishReadinessStatus,
)
from app.governance.publish_contract import (
    PreM3PublishContractV1,
    PublishDestination,
    PublishDestinationKind,
)
from app.governance.publish_evaluator import (
    customer_model_ready_current_view_id,
    customer_model_ready_table_id,
    evaluate_publish_readiness,
)
from app.publish_execution.model_ready import (
    ModelReadyEvidenceResolver,
    NullModelReadyEvidenceResolver,
)
from app.service.entitlements import require_feature
from app.service.errors import resource_not_found


class PublishGovernanceService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        model_ready: ModelReadyEvidenceResolver | None = None,
    ) -> None:
        self._repo = repo
        self._model_ready = model_ready or NullModelReadyEvidenceResolver()

    def evaluate(self, *, workspace_id: str, dataset_id: str, run_id: str):
        require_feature(self._repo, Feature.BIGQUERY_PUBLISH)
        tenant = require_tenant()
        evaluation = self._repo.get_evaluation_ref(tenant_id=tenant.tenant_id, run_id=run_id)
        if (
            evaluation is None
            or evaluation.workspace_id != workspace_id
            or evaluation.dataset_id != dataset_id
        ):
            raise resource_not_found()
        evidence = self._model_ready.resolve(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
        model_ready_verified = evidence is not None and bool(evidence.fingerprint)
        model_ready_fingerprint = None if evidence is None else evidence.fingerprint
        destinations: list[PublishDestination] = []
        drive = self._repo.get_drive_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if drive is not None and drive.status == BindingStatus.ACTIVE.value:
            destinations.append(
                PublishDestination(
                    kind=PublishDestinationKind.GOOGLE_DRIVE,
                    binding_id=drive.root_folder_id,
                    target_identity=drive.root_folder_id,
                    location=None,
                    write_verified=drive.export_enabled,
                )
            )
        bq = self._repo.get_bigquery_binding(
            tenant_id=tenant.tenant_id, workspace_id=workspace_id
        )
        if bq is not None and bq.status == BindingStatus.ACTIVE.value:
            destinations.append(
                PublishDestination(
                    kind=PublishDestinationKind.BIGQUERY,
                    binding_id=f"{bq.destination_project_id}.{bq.destination_dataset_id}",
                    target_identity=f"{bq.destination_project_id}.{BIGQUERY_DEPOT_DATASET_ID}",
                    location=bq.location,
                    write_verified=bq.write_verified,
                )
            )
        now = datetime.now(UTC)
        contract = PreM3PublishContractV1(
            contract_version=PUBLISH_CONTRACT_VERSION,
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            run_id=run_id,
            model_ready_fingerprint=model_ready_fingerprint,
            model_ready_verified=model_ready_verified,
            destinations=destinations,
            required_artifacts=list(PUBLISH_DRIVE_ARTIFACTS),
            created_at=now,
            status=PublishReadinessStatus.NOT_PUBLISH_READY,
            contract_fingerprint="pending",
        )
        contract = contract.model_copy(
            update={"contract_fingerprint": contract.compute_fingerprint()}
        )
        receipt = evaluate_publish_readiness(contract)
        self._repo.put_publish_receipt(receipt)
        return contract, receipt


def drive_export_path(workspace_id: str, dataset_id: str, run_id: str) -> str:
    return f"{DRIVE_DEPOT_NAME}/exports/{workspace_id}/{dataset_id}/{run_id}/"


def drive_reports_path(workspace_id: str, dataset_id: str, run_id: str) -> str:
    return f"{DRIVE_DEPOT_NAME}/reports/{workspace_id}/{dataset_id}/{run_id}/"


def bq_model_ready_table(dataset_id: str, run_id: str) -> str:
    return customer_model_ready_table_id(dataset_id, run_id)


def bq_model_ready_current_view(dataset_id: str) -> str:
    return customer_model_ready_current_view_id(dataset_id)

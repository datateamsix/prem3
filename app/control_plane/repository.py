"""ControlPlaneRepository protocol — injectable persistence for prem3-api.

Business/service code must not import Firestore document operations directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from app.control_plane.models import (
    BigQueryWorkspaceBinding,
    CredentialEnvelope,
    Dataset,
    DatasetEvaluationRef,
    DatasetImportSelection,
    DatasetUpload,
    DriveWorkspaceBinding,
    EntitlementSnapshot,
    EvaluationDispatch,
    GoogleConnection,
    GoogleOAuthTransaction,
    IdentityProviderOrganizationMapping,
    MeasurementTrack,
    MembershipProjection,
    ProcessedWebhookEvent,
    StripeCustomerMapping,
    SubscriptionProjection,
    Tenant,
    WebhookClaimResult,
    WebhookProvider,
    Workspace,
    WorkspaceStatus,
)
from app.governance.import_contract import ImportReadinessReceipt
from app.governance.publish_contract import PublishReadinessReceipt
from app.materialization.contracts import SourceMaterializationReceipt
from app.publish_execution.contracts import PublishExecutionReceipt


@runtime_checkable
class ControlPlaneRepository(Protocol):
    """Authority-qualified Mission 2 operational control plane."""

    # --- Tenant ---
    def create_tenant(
        self,
        *,
        display_name: str,
        identity_mapping: IdentityProviderOrganizationMapping | None = None,
        with_planner_entitlement: bool = True,
    ) -> Tenant: ...

    def get_tenant(self, tenant_id: str) -> Tenant | None: ...

    def set_tenant_status(self, *, tenant_id: str, status: str) -> Tenant: ...

    # --- Identity ---
    def put_identity_organization_mapping(
        self, mapping: IdentityProviderOrganizationMapping
    ) -> IdentityProviderOrganizationMapping: ...

    def get_tenant_id_for_provider_org(
        self, *, provider: str, provider_organization_id: str
    ) -> str | None: ...

    def get_identity_organization_mapping(
        self, *, provider: str, provider_organization_id: str
    ) -> IdentityProviderOrganizationMapping | None: ...

    def upsert_membership_projection(
        self, membership: MembershipProjection
    ) -> MembershipProjection: ...

    def get_membership_projection(
        self,
        *,
        tenant_id: str,
        provider: str,
        provider_user_id: str,
    ) -> MembershipProjection | None: ...

    # --- Workspace / MMM Project ---
    def list_workspaces_for_tenant(self, tenant_id: str) -> list[Workspace]: ...

    def get_workspace_for_tenant(
        self, *, tenant_id: str, workspace_id: str
    ) -> Workspace | None: ...

    def create_workspace_with_capacity(
        self, *, tenant_id: str, name: str, workspace_id: str | None = None
    ) -> Workspace: ...

    def put_workspace(self, workspace: Workspace) -> Workspace: ...

    def update_workspace_status(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        status: WorkspaceStatus,
    ) -> Workspace: ...

    def put_measurement_track(self, track: MeasurementTrack) -> MeasurementTrack: ...

    def get_measurement_track(
        self, *, tenant_id: str, workspace_id: str, track_id: str
    ) -> MeasurementTrack | None: ...

    def list_measurement_tracks(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        cycle_id: str | None = None,
    ) -> list[MeasurementTrack]: ...

    # --- Dataset ---
    def list_datasets_for_workspace(
        self, *, tenant_id: str, workspace_id: str
    ) -> list[Dataset]: ...

    def get_dataset_for_workspace(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> Dataset | None: ...

    def create_dataset(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        name: str,
        dataset_id: str | None = None,
    ) -> Dataset: ...

    # --- Entitlement ---
    def put_entitlement_snapshot(
        self, snapshot: EntitlementSnapshot, *, make_current: bool = True
    ) -> EntitlementSnapshot: ...

    def get_entitlement_snapshot(
        self, *, tenant_id: str, snapshot_id: str
    ) -> EntitlementSnapshot | None: ...

    def get_current_entitlement(self, tenant_id: str) -> EntitlementSnapshot: ...

    # --- Billing ---
    def put_stripe_customer_mapping(
        self, mapping: StripeCustomerMapping
    ) -> StripeCustomerMapping: ...

    def get_stripe_customer_mapping(
        self, tenant_id: str
    ) -> StripeCustomerMapping | None: ...

    def put_subscription_projection(
        self, projection: SubscriptionProjection
    ) -> SubscriptionProjection: ...

    def get_subscription_projection(
        self, tenant_id: str
    ) -> SubscriptionProjection | None: ...

    # --- Webhook idempotency ---
    def claim_webhook_event(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        event_type: str,
        lease_seconds: int = 120,
        now: datetime | None = None,
    ) -> WebhookClaimResult: ...

    def mark_webhook_event_processed(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        result: str | None = None,
    ) -> ProcessedWebhookEvent: ...

    def mark_webhook_event_failed(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        result: str | None = None,
    ) -> ProcessedWebhookEvent: ...

    def get_webhook_event(
        self, *, provider: WebhookProvider | str, provider_event_id: str
    ) -> ProcessedWebhookEvent | None: ...

    # --- Dataset uploads ---
    def create_upload(self, upload: DatasetUpload) -> DatasetUpload: ...

    def get_upload(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        upload_id: str,
    ) -> DatasetUpload | None: ...

    def update_upload(self, upload: DatasetUpload) -> DatasetUpload: ...

    # --- Evaluation linkage ---
    def put_evaluation_ref(self, ref: DatasetEvaluationRef) -> DatasetEvaluationRef: ...

    def get_evaluation_ref(
        self, *, tenant_id: str, run_id: str
    ) -> DatasetEvaluationRef | None: ...

    def list_evaluations_for_dataset(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
    ) -> list[DatasetEvaluationRef]: ...

    def put_evaluation_dispatch(self, dispatch: EvaluationDispatch) -> EvaluationDispatch: ...

    def get_evaluation_dispatch(self, dispatch_id: str) -> EvaluationDispatch | None: ...

    def get_evaluation_dispatch_for_run(
        self, *, tenant_id: str, run_id: str
    ) -> EvaluationDispatch | None: ...

    def claim_evaluation_dispatch(
        self,
        *,
        dispatch_id: str,
        owner: str,
        execution_name: str,
        now: datetime,
    ) -> tuple[str, EvaluationDispatch | None]: ...

    # --- Idempotency (tenant-scoped; key is not authority) ---
    def get_idempotent_result(
        self, *, tenant_id: str, operation: str, key: str
    ) -> dict[str, Any] | None: ...

    def put_idempotent_result(
        self,
        *,
        tenant_id: str,
        operation: str,
        key: str,
        result: dict[str, Any],
    ) -> None: ...

    # --- Google connections / governance ---
    def put_oauth_transaction(self, txn: GoogleOAuthTransaction) -> GoogleOAuthTransaction: ...

    def get_oauth_transaction_by_state_hash(
        self, state_hash: str
    ) -> GoogleOAuthTransaction | None: ...

    def consume_oauth_transaction(
        self, *, state_hash: str, consumed_at: datetime
    ) -> GoogleOAuthTransaction | None: ...

    def put_google_connection(self, connection: GoogleConnection) -> GoogleConnection: ...

    def get_google_connection(
        self, *, tenant_id: str, connection_id: str
    ) -> GoogleConnection | None: ...

    def list_google_connections(self, *, tenant_id: str) -> list[GoogleConnection]: ...

    def put_credential_envelope(self, envelope: CredentialEnvelope) -> CredentialEnvelope: ...

    def get_credential_envelope(
        self, *, tenant_id: str, credential_ref: str
    ) -> CredentialEnvelope | None: ...

    def delete_credential_envelope(self, *, tenant_id: str, credential_ref: str) -> None: ...

    def list_credential_envelopes(self) -> list[CredentialEnvelope]: ...

    def put_drive_binding(self, binding: DriveWorkspaceBinding) -> DriveWorkspaceBinding: ...

    def get_drive_binding(
        self, *, tenant_id: str, workspace_id: str
    ) -> DriveWorkspaceBinding | None: ...

    def put_bigquery_binding(
        self, binding: BigQueryWorkspaceBinding
    ) -> BigQueryWorkspaceBinding: ...

    def get_bigquery_binding(
        self, *, tenant_id: str, workspace_id: str
    ) -> BigQueryWorkspaceBinding | None: ...

    def put_import_selection(
        self, selection: DatasetImportSelection
    ) -> DatasetImportSelection: ...

    def get_import_selection(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> DatasetImportSelection | None: ...

    def put_import_receipt(self, receipt: ImportReadinessReceipt) -> ImportReadinessReceipt: ...

    def get_import_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, receipt_id: str
    ) -> ImportReadinessReceipt | None: ...

    def get_current_import_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> ImportReadinessReceipt | None: ...

    def put_materialization(
        self, receipt: SourceMaterializationReceipt
    ) -> SourceMaterializationReceipt: ...

    def get_materialization(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        materialization_id: str,
    ) -> SourceMaterializationReceipt | None: ...

    def list_materializations(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> list[SourceMaterializationReceipt]: ...

    def get_materialization_by_authority(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        authority_fingerprint: str,
    ) -> SourceMaterializationReceipt | None: ...

    def put_publish_receipt(self, receipt: PublishReadinessReceipt) -> PublishReadinessReceipt: ...

    def get_current_publish_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, run_id: str
    ) -> PublishReadinessReceipt | None: ...

    def put_publish_execution(
        self, receipt: PublishExecutionReceipt, *, authority_fingerprint: str
    ) -> PublishExecutionReceipt: ...

    def get_publish_execution(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
        publish_id: str,
    ) -> PublishExecutionReceipt | None: ...

    def list_publish_executions(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, run_id: str
    ) -> list[PublishExecutionReceipt]: ...

    def get_publish_execution_by_authority(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
        authority_fingerprint: str,
    ) -> PublishExecutionReceipt | None: ...

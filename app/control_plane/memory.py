"""In-memory ControlPlaneRepository for CI, API tests, and concurrency proofs.

Not more permissive than Firestore. Uses an RLock around mutating transactions.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.control_plane.entitlements import default_planner_entitlement
from app.control_plane.ids import new_dataset_id, new_tenant_id, new_workspace_id
from app.control_plane.layout import (
    billing_customer_doc_id,
    billing_subscription_doc_id,
    identity_mapping_doc_id,
    membership_doc_id,
    webhook_event_doc_id,
)
from app.control_plane.models import (
    BigQueryWorkspaceBinding,
    BillingProvider,
    CredentialEnvelope,
    Dataset,
    DatasetEvaluationRef,
    DatasetImportSelection,
    DatasetStatus,
    DatasetUpload,
    DriveWorkspaceBinding,
    EntitlementSnapshot,
    GoogleConnection,
    GoogleOAuthTransaction,
    IdentityProviderOrganizationMapping,
    MembershipProjection,
    ProcessedWebhookEvent,
    StripeCustomerMapping,
    SubscriptionProjection,
    Tenant,
    TenantStatus,
    WebhookClaimResult,
    WebhookClaimStatus,
    WebhookEventStatus,
    WebhookProvider,
    Workspace,
    WorkspaceStatus,
)
from app.control_plane.webhook_claim import (
    DEFAULT_WEBHOOK_CLAIM_LEASE_SECONDS,
    decide_webhook_claim,
)
from app.core.errors import (
    DatasetNotFoundError,
    EntitlementUnavailableError,
    ProjectLimitReachedError,
    ProviderMappingConflictError,
    TenantNotFoundError,
    WebhookAlreadyProcessedError,
    WorkspaceNotFoundError,
)
from app.core.identifiers import validate_resource_identifier
from app.governance.import_contract import ImportReadinessReceipt
from app.governance.publish_contract import PublishReadinessReceipt
from app.materialization.contracts import SourceMaterializationReceipt
from app.publish_execution.contracts import PublishExecutionReceipt


class InMemoryControlPlaneRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tenants: dict[str, Tenant] = {}
        self._identity_mappings: dict[str, IdentityProviderOrganizationMapping] = {}
        self._memberships: dict[str, MembershipProjection] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._datasets: dict[str, Dataset] = {}
        self._entitlements: dict[str, EntitlementSnapshot] = {}
        self._customers: dict[str, StripeCustomerMapping] = {}
        self._subscriptions: dict[str, SubscriptionProjection] = {}
        self._webhooks: dict[str, ProcessedWebhookEvent] = {}
        self._evaluation_refs: dict[str, DatasetEvaluationRef] = {}
        self._uploads: dict[str, DatasetUpload] = {}
        self._dataset_evaluations: dict[str, DatasetEvaluationRef] = {}
        self._idempotency: dict[str, dict[str, Any]] = {}
        self._oauth_txns: dict[str, GoogleOAuthTransaction] = {}
        self._google_connections: dict[str, GoogleConnection] = {}
        self._credential_envelopes: dict[str, CredentialEnvelope] = {}
        self._drive_bindings: dict[str, DriveWorkspaceBinding] = {}
        self._bq_bindings: dict[str, BigQueryWorkspaceBinding] = {}
        self._import_selections: dict[str, DatasetImportSelection] = {}
        self._import_receipts: dict[str, ImportReadinessReceipt] = {}
        self._current_import_receipts: dict[str, str] = {}
        self._materializations: dict[str, SourceMaterializationReceipt] = {}
        self._materialization_authority: dict[str, str] = {}
        self._publish_receipts: dict[str, PublishReadinessReceipt] = {}
        self._publish_executions: dict[str, PublishExecutionReceipt] = {}
        self._publish_authority: dict[str, str] = {}

    def create_tenant(
        self,
        *,
        display_name: str,
        identity_mapping: IdentityProviderOrganizationMapping | None = None,
        with_planner_entitlement: bool = True,
    ) -> Tenant:
        with self._lock:
            now = datetime.now(UTC)
            tenant_id = new_tenant_id()
            tenant = Tenant(
                tenant_id=tenant_id,
                display_name=display_name,
                status=TenantStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                current_entitlement_snapshot_id=None,
                active_workspace_count=0,
            )
            self._tenants[tenant_id] = tenant
            if identity_mapping is not None:
                mapped = identity_mapping.model_copy(
                    update={
                        "tenant_id": tenant_id,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self._put_identity_mapping_locked(mapped)
            if with_planner_entitlement:
                snapshot = default_planner_entitlement(tenant_id=tenant_id, now=now)
                self._put_entitlement_locked(snapshot, make_current=True)
                tenant = self._tenants[tenant_id]
            return deepcopy(tenant)

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            return deepcopy(tenant) if tenant is not None else None

    def set_tenant_status(self, *, tenant_id: str, status: str) -> Tenant:
        with self._lock:
            tenant = self._require_tenant_locked(tenant_id)
            updated = tenant.model_copy(
                update={"status": TenantStatus(status), "updated_at": datetime.now(UTC)}
            )
            self._tenants[tenant_id] = updated
            return deepcopy(updated)

    def put_identity_organization_mapping(
        self, mapping: IdentityProviderOrganizationMapping
    ) -> IdentityProviderOrganizationMapping:
        with self._lock:
            return deepcopy(self._put_identity_mapping_locked(mapping))

    def get_tenant_id_for_provider_org(
        self, *, provider: str, provider_organization_id: str
    ) -> str | None:
        mapping = self.get_identity_organization_mapping(
            provider=provider, provider_organization_id=provider_organization_id
        )
        return mapping.tenant_id if mapping is not None else None

    def get_identity_organization_mapping(
        self, *, provider: str, provider_organization_id: str
    ) -> IdentityProviderOrganizationMapping | None:
        with self._lock:
            key = identity_mapping_doc_id(provider, provider_organization_id)
            mapping = self._identity_mappings.get(key)
            return deepcopy(mapping) if mapping is not None else None

    def upsert_membership_projection(
        self, membership: MembershipProjection
    ) -> MembershipProjection:
        with self._lock:
            self._require_tenant_locked(membership.tenant_id)
            key = (
                f"{membership.tenant_id}/"
                f"{membership_doc_id(membership.provider, membership.provider_user_id)}"
            )
            self._memberships[key] = membership
            return deepcopy(membership)

    def get_membership_projection(
        self,
        *,
        tenant_id: str,
        provider: str,
        provider_user_id: str,
    ) -> MembershipProjection | None:
        with self._lock:
            key = f"{tenant_id}/{membership_doc_id(provider, provider_user_id)}"
            membership = self._memberships.get(key)
            return deepcopy(membership) if membership is not None else None

    def list_workspaces_for_tenant(self, tenant_id: str) -> list[Workspace]:
        with self._lock:
            self._require_tenant_locked(tenant_id)
            rows = [
                deepcopy(ws)
                for key, ws in self._workspaces.items()
                if key.startswith(f"{tenant_id}/")
            ]
            rows.sort(key=lambda item: item.created_at)
            return rows

    def get_workspace_for_tenant(
        self, *, tenant_id: str, workspace_id: str
    ) -> Workspace | None:
        with self._lock:
            ws = self._workspaces.get(f"{tenant_id}/{workspace_id}")
            if ws is None or ws.tenant_id != tenant_id:
                return None
            return deepcopy(ws)

    def create_workspace_with_capacity(
        self, *, tenant_id: str, name: str, workspace_id: str | None = None
    ) -> Workspace:
        with self._lock:
            tenant = self._require_tenant_locked(tenant_id)
            entitlement = self._require_current_entitlement_locked(tenant_id)
            if tenant.active_workspace_count >= entitlement.max_active_projects:
                raise ProjectLimitReachedError(
                    "Active MMM Project capacity reached for current entitlement."
                )
            now = datetime.now(UTC)
            wsp_id = workspace_id or new_workspace_id()
            validate_resource_identifier(wsp_id, field="workspace_id")
            key = f"{tenant_id}/{wsp_id}"
            if key in self._workspaces:
                raise ProviderMappingConflictError("workspace_id already exists for tenant.")
            workspace = Workspace(
                tenant_id=tenant_id,
                workspace_id=wsp_id,
                name=name,
                status=WorkspaceStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            self._workspaces[key] = workspace
            self._tenants[tenant_id] = tenant.model_copy(
                update={
                    "active_workspace_count": tenant.active_workspace_count + 1,
                    "updated_at": now,
                }
            )
            return deepcopy(workspace)

    def list_datasets_for_workspace(
        self, *, tenant_id: str, workspace_id: str
    ) -> list[Dataset]:
        with self._lock:
            self._require_workspace_locked(tenant_id, workspace_id)
            prefix = f"{tenant_id}/{workspace_id}/"
            rows = [
                deepcopy(ds)
                for key, ds in self._datasets.items()
                if key.startswith(prefix)
            ]
            rows.sort(key=lambda item: item.created_at)
            return rows

    def get_dataset_for_workspace(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> Dataset | None:
        with self._lock:
            ds = self._datasets.get(f"{tenant_id}/{workspace_id}/{dataset_id}")
            if ds is None:
                return None
            if ds.tenant_id != tenant_id or ds.workspace_id != workspace_id:
                return None
            return deepcopy(ds)

    def create_dataset(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        name: str,
        dataset_id: str | None = None,
    ) -> Dataset:
        with self._lock:
            self._require_workspace_locked(tenant_id, workspace_id)
            now = datetime.now(UTC)
            dset_id = dataset_id or new_dataset_id()
            validate_resource_identifier(dset_id, field="dataset_id")
            key = f"{tenant_id}/{workspace_id}/{dset_id}"
            if key in self._datasets:
                raise ProviderMappingConflictError("dataset_id already exists for workspace.")
            dataset = Dataset(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dset_id,
                name=name,
                status=DatasetStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            self._datasets[key] = dataset
            return deepcopy(dataset)

    def put_entitlement_snapshot(
        self, snapshot: EntitlementSnapshot, *, make_current: bool = True
    ) -> EntitlementSnapshot:
        with self._lock:
            return deepcopy(self._put_entitlement_locked(snapshot, make_current=make_current))

    def get_entitlement_snapshot(
        self, *, tenant_id: str, snapshot_id: str
    ) -> EntitlementSnapshot | None:
        with self._lock:
            snap = self._entitlements.get(f"{tenant_id}/{snapshot_id}")
            if snap is None or snap.tenant_id != tenant_id:
                return None
            return deepcopy(snap)

    def get_current_entitlement(self, tenant_id: str) -> EntitlementSnapshot:
        with self._lock:
            return deepcopy(self._require_current_entitlement_locked(tenant_id))

    def put_stripe_customer_mapping(
        self, mapping: StripeCustomerMapping
    ) -> StripeCustomerMapping:
        with self._lock:
            self._require_tenant_locked(mapping.tenant_id)
            key = f"{mapping.tenant_id}/{billing_customer_doc_id(mapping.billing_provider)}"
            self._customers[key] = mapping
            return deepcopy(mapping)

    def get_stripe_customer_mapping(self, tenant_id: str) -> StripeCustomerMapping | None:
        with self._lock:
            key = f"{tenant_id}/{billing_customer_doc_id(BillingProvider.STRIPE)}"
            mapping = self._customers.get(key)
            return deepcopy(mapping) if mapping is not None else None

    def put_subscription_projection(
        self, projection: SubscriptionProjection
    ) -> SubscriptionProjection:
        with self._lock:
            self._require_tenant_locked(projection.tenant_id)
            key = (
                f"{projection.tenant_id}/"
                f"{billing_subscription_doc_id(projection.billing_provider)}"
            )
            self._subscriptions[key] = projection
            return deepcopy(projection)

    def get_subscription_projection(self, tenant_id: str) -> SubscriptionProjection | None:
        with self._lock:
            key = f"{tenant_id}/{billing_subscription_doc_id(BillingProvider.STRIPE)}"
            projection = self._subscriptions.get(key)
            return deepcopy(projection) if projection is not None else None

    def claim_webhook_event(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        event_type: str,
        lease_seconds: int = DEFAULT_WEBHOOK_CLAIM_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> WebhookClaimResult:
        with self._lock:
            key = webhook_event_doc_id(provider, provider_event_id)
            existing = self._webhooks.get(key)
            provider_enum = (
                provider if isinstance(provider, WebhookProvider) else WebhookProvider(provider)
            )
            result = decide_webhook_claim(
                existing,
                provider=provider_enum,
                provider_event_id=provider_event_id,
                event_type=event_type,
                now=now or datetime.now(UTC),
                lease_seconds=lease_seconds,
            )
            if result.status == WebhookClaimStatus.WON:
                self._webhooks[key] = result.event
            return WebhookClaimResult(status=result.status, event=deepcopy(result.event))

    def mark_webhook_event_processed(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        result: str | None = None,
    ) -> ProcessedWebhookEvent:
        with self._lock:
            key = webhook_event_doc_id(provider, provider_event_id)
            existing = self._webhooks.get(key)
            if existing is None:
                raise WebhookAlreadyProcessedError("Webhook event was not claimed.")
            if existing.status == WebhookEventStatus.PROCESSED:
                return deepcopy(existing)
            updated = existing.model_copy(
                update={
                    "status": WebhookEventStatus.PROCESSED,
                    "processed_at": datetime.now(UTC),
                    "result": result,
                }
            )
            self._webhooks[key] = updated
            return deepcopy(updated)

    def mark_webhook_event_failed(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        result: str | None = None,
    ) -> ProcessedWebhookEvent:
        with self._lock:
            key = webhook_event_doc_id(provider, provider_event_id)
            existing = self._webhooks.get(key)
            if existing is None:
                raise WebhookAlreadyProcessedError("Webhook event was not claimed.")
            updated = existing.model_copy(
                update={
                    "status": WebhookEventStatus.FAILED,
                    "processed_at": datetime.now(UTC),
                    "result": result,
                }
            )
            self._webhooks[key] = updated
            return deepcopy(updated)

    def get_webhook_event(
        self, *, provider: WebhookProvider | str, provider_event_id: str
    ) -> ProcessedWebhookEvent | None:
        with self._lock:
            event = self._webhooks.get(webhook_event_doc_id(provider, provider_event_id))
            return deepcopy(event) if event is not None else None

    def create_upload(self, upload: DatasetUpload) -> DatasetUpload:
        with self._lock:
            dataset = self.get_dataset_for_workspace(
                tenant_id=upload.tenant_id,
                workspace_id=upload.workspace_id,
                dataset_id=upload.dataset_id,
            )
            if dataset is None:
                raise DatasetNotFoundError("Dataset does not exist for upload.")
            key = self._upload_key(
                upload.tenant_id, upload.workspace_id, upload.dataset_id, upload.upload_id
            )
            if key in self._uploads:
                raise ProviderMappingConflictError("Upload already exists.")
            self._uploads[key] = upload
            return deepcopy(upload)

    def get_upload(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        upload_id: str,
    ) -> DatasetUpload | None:
        with self._lock:
            upload = self._uploads.get(
                self._upload_key(tenant_id, workspace_id, dataset_id, upload_id)
            )
            if upload is None:
                return None
            if (
                upload.tenant_id != tenant_id
                or upload.workspace_id != workspace_id
                or upload.dataset_id != dataset_id
            ):
                return None
            return deepcopy(upload)

    def update_upload(self, upload: DatasetUpload) -> DatasetUpload:
        with self._lock:
            key = self._upload_key(
                upload.tenant_id, upload.workspace_id, upload.dataset_id, upload.upload_id
            )
            existing = self._uploads.get(key)
            if existing is None:
                raise DatasetNotFoundError("Upload does not exist.")
            if (
                existing.tenant_id != upload.tenant_id
                or existing.workspace_id != upload.workspace_id
                or existing.dataset_id != upload.dataset_id
            ):
                raise ProviderMappingConflictError("Upload cannot be re-parented.")
            self._uploads[key] = upload
            return deepcopy(upload)

    def put_evaluation_ref(self, ref: DatasetEvaluationRef) -> DatasetEvaluationRef:
        with self._lock:
            dataset = self.get_dataset_for_workspace(
                tenant_id=ref.tenant_id,
                workspace_id=ref.workspace_id,
                dataset_id=ref.dataset_id,
            )
            if dataset is None:
                raise DatasetNotFoundError("Dataset does not exist for evaluation linkage.")
            run_key = f"{ref.tenant_id}/{ref.run_id}"
            existing = self._evaluation_refs.get(run_key)
            if existing is not None and (
                existing.workspace_id != ref.workspace_id
                or existing.dataset_id != ref.dataset_id
                or existing.upload_id != ref.upload_id
            ):
                raise ProviderMappingConflictError("Evaluation linkage is immutable.")
            self._evaluation_refs[run_key] = ref
            dataset_key = self._dataset_evaluation_key(
                ref.tenant_id, ref.workspace_id, ref.dataset_id, ref.run_id
            )
            self._dataset_evaluations[dataset_key] = ref
            return deepcopy(ref)

    def get_evaluation_ref(
        self, *, tenant_id: str, run_id: str
    ) -> DatasetEvaluationRef | None:
        with self._lock:
            ref = self._evaluation_refs.get(f"{tenant_id}/{run_id}")
            if ref is None or ref.tenant_id != tenant_id:
                return None
            return deepcopy(ref)

    def list_evaluations_for_dataset(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
    ) -> list[DatasetEvaluationRef]:
        with self._lock:
            rows = [
                deepcopy(ref)
                for key, ref in self._dataset_evaluations.items()
                if key.startswith(f"{tenant_id}/{workspace_id}/{dataset_id}/")
                and ref.tenant_id == tenant_id
                and ref.workspace_id == workspace_id
                and ref.dataset_id == dataset_id
            ]
            rows.sort(key=lambda item: item.run_id)
            return rows

    def get_idempotent_result(
        self, *, tenant_id: str, operation: str, key: str
    ) -> dict[str, Any] | None:
        with self._lock:
            stored = self._idempotency.get(self._idempotency_key(tenant_id, operation, key))
            return deepcopy(stored) if stored is not None else None

    def put_idempotent_result(
        self,
        *,
        tenant_id: str,
        operation: str,
        key: str,
        result: dict[str, Any],
    ) -> None:
        with self._lock:
            self._require_tenant_locked(tenant_id)
            self._idempotency[self._idempotency_key(tenant_id, operation, key)] = deepcopy(
                result
            )

    def put_oauth_transaction(self, txn: GoogleOAuthTransaction) -> GoogleOAuthTransaction:
        with self._lock:
            self._require_tenant_locked(txn.tenant_id)
            self._oauth_txns[txn.state_hash] = txn
            return deepcopy(txn)

    def get_oauth_transaction_by_state_hash(
        self, state_hash: str
    ) -> GoogleOAuthTransaction | None:
        with self._lock:
            txn = self._oauth_txns.get(state_hash)
            return deepcopy(txn) if txn is not None else None

    def consume_oauth_transaction(
        self, *, state_hash: str, consumed_at: datetime
    ) -> GoogleOAuthTransaction | None:
        with self._lock:
            txn = self._oauth_txns.get(state_hash)
            if txn is None:
                return None
            if txn.consumed_at is not None:
                return None
            updated = txn.model_copy(update={"consumed_at": consumed_at})
            self._oauth_txns[state_hash] = updated
            return deepcopy(updated)

    def put_google_connection(self, connection: GoogleConnection) -> GoogleConnection:
        with self._lock:
            self._require_tenant_locked(connection.tenant_id)
            self._google_connections[f"{connection.tenant_id}/{connection.connection_id}"] = (
                connection
            )
            return deepcopy(connection)

    def get_google_connection(
        self, *, tenant_id: str, connection_id: str
    ) -> GoogleConnection | None:
        with self._lock:
            conn = self._google_connections.get(f"{tenant_id}/{connection_id}")
            if conn is None or conn.tenant_id != tenant_id:
                return None
            return deepcopy(conn)

    def list_google_connections(self, *, tenant_id: str) -> list[GoogleConnection]:
        with self._lock:
            rows = [
                deepcopy(item)
                for key, item in self._google_connections.items()
                if item.tenant_id == tenant_id
            ]
            rows.sort(key=lambda item: item.connection_id)
            return rows

    def put_credential_envelope(self, envelope: CredentialEnvelope) -> CredentialEnvelope:
        with self._lock:
            self._require_tenant_locked(envelope.tenant_id)
            self._credential_envelopes[f"{envelope.tenant_id}/{envelope.credential_ref}"] = (
                envelope
            )
            return deepcopy(envelope)

    def get_credential_envelope(
        self, *, tenant_id: str, credential_ref: str
    ) -> CredentialEnvelope | None:
        with self._lock:
            envelope = self._credential_envelopes.get(f"{tenant_id}/{credential_ref}")
            if envelope is None or envelope.tenant_id != tenant_id:
                return None
            return deepcopy(envelope)

    def delete_credential_envelope(self, *, tenant_id: str, credential_ref: str) -> None:
        with self._lock:
            self._credential_envelopes.pop(f"{tenant_id}/{credential_ref}", None)

    def list_credential_envelopes(self) -> list[CredentialEnvelope]:
        with self._lock:
            return [deepcopy(item) for item in self._credential_envelopes.values()]

    def put_drive_binding(self, binding: DriveWorkspaceBinding) -> DriveWorkspaceBinding:
        with self._lock:
            self._require_workspace_locked(binding.tenant_id, binding.workspace_id)
            self._drive_bindings[f"{binding.tenant_id}/{binding.workspace_id}"] = binding
            return deepcopy(binding)

    def get_drive_binding(
        self, *, tenant_id: str, workspace_id: str
    ) -> DriveWorkspaceBinding | None:
        with self._lock:
            binding = self._drive_bindings.get(f"{tenant_id}/{workspace_id}")
            if binding is None or binding.tenant_id != tenant_id:
                return None
            return deepcopy(binding)

    def put_bigquery_binding(
        self, binding: BigQueryWorkspaceBinding
    ) -> BigQueryWorkspaceBinding:
        with self._lock:
            self._require_workspace_locked(binding.tenant_id, binding.workspace_id)
            self._bq_bindings[f"{binding.tenant_id}/{binding.workspace_id}"] = binding
            return deepcopy(binding)

    def get_bigquery_binding(
        self, *, tenant_id: str, workspace_id: str
    ) -> BigQueryWorkspaceBinding | None:
        with self._lock:
            binding = self._bq_bindings.get(f"{tenant_id}/{workspace_id}")
            if binding is None or binding.tenant_id != tenant_id:
                return None
            return deepcopy(binding)

    def put_import_selection(
        self, selection: DatasetImportSelection
    ) -> DatasetImportSelection:
        with self._lock:
            dataset = self.get_dataset_for_workspace(
                tenant_id=selection.tenant_id,
                workspace_id=selection.workspace_id,
                dataset_id=selection.dataset_id,
            )
            if dataset is None:
                raise DatasetNotFoundError("Dataset does not exist.")
            key = f"{selection.tenant_id}/{selection.workspace_id}/{selection.dataset_id}"
            self._import_selections[key] = selection
            return deepcopy(selection)

    def get_import_selection(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> DatasetImportSelection | None:
        with self._lock:
            selection = self._import_selections.get(f"{tenant_id}/{workspace_id}/{dataset_id}")
            if selection is None or selection.tenant_id != tenant_id:
                return None
            return deepcopy(selection)

    def put_import_receipt(self, receipt: ImportReadinessReceipt) -> ImportReadinessReceipt:
        with self._lock:
            key = (
                f"{receipt.tenant_id}/{receipt.workspace_id}/"
                f"{receipt.dataset_id}/{receipt.receipt_id}"
            )
            self._import_receipts[key] = receipt
            current_key = f"{receipt.tenant_id}/{receipt.workspace_id}/{receipt.dataset_id}"
            previous_id = self._current_import_receipts.get(current_key)
            if previous_id and previous_id != receipt.receipt_id:
                prev_key = (
                    f"{receipt.tenant_id}/{receipt.workspace_id}/"
                    f"{receipt.dataset_id}/{previous_id}"
                )
                previous = self._import_receipts.get(prev_key)
                if previous is not None:
                    self._import_receipts[prev_key] = previous.model_copy(
                        update={"superseded": True}
                    )
            self._current_import_receipts[current_key] = receipt.receipt_id
            return deepcopy(receipt)

    def get_import_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, receipt_id: str
    ) -> ImportReadinessReceipt | None:
        with self._lock:
            receipt = self._import_receipts.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{receipt_id}"
            )
            if receipt is None or receipt.tenant_id != tenant_id:
                return None
            return deepcopy(receipt)

    def get_current_import_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> ImportReadinessReceipt | None:
        with self._lock:
            receipt_id = self._current_import_receipts.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}"
            )
            if receipt_id is None:
                return None
            receipt = self._import_receipts.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{receipt_id}"
            )
            if receipt is None or receipt.tenant_id != tenant_id:
                return None
            return deepcopy(receipt)

    def put_materialization(
        self, receipt: SourceMaterializationReceipt
    ) -> SourceMaterializationReceipt:
        with self._lock:
            key = (
                f"{receipt.tenant_id}/{receipt.workspace_id}/"
                f"{receipt.dataset_id}/{receipt.materialization_id}"
            )
            self._materializations[key] = receipt
            if receipt.status.value == "COMPLETE":
                auth_key = (
                    f"{receipt.tenant_id}/{receipt.workspace_id}/"
                    f"{receipt.dataset_id}/{receipt.authority_fingerprint}"
                )
                self._materialization_authority[auth_key] = receipt.materialization_id
            return deepcopy(receipt)

    def get_materialization(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        materialization_id: str,
    ) -> SourceMaterializationReceipt | None:
        with self._lock:
            receipt = self._materializations.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{materialization_id}"
            )
            if receipt is None or receipt.tenant_id != tenant_id:
                return None
            return deepcopy(receipt)

    def list_materializations(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> list[SourceMaterializationReceipt]:
        with self._lock:
            prefix = f"{tenant_id}/{workspace_id}/{dataset_id}/"
            rows = [
                deepcopy(item)
                for key, item in self._materializations.items()
                if key.startswith(prefix) and item.tenant_id == tenant_id
            ]
            return sorted(rows, key=lambda row: row.started_at)

    def get_materialization_by_authority(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        authority_fingerprint: str,
    ) -> SourceMaterializationReceipt | None:
        with self._lock:
            materialization_id = self._materialization_authority.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{authority_fingerprint}"
            )
            if materialization_id is None:
                return None
            return self.get_materialization(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                materialization_id=materialization_id,
            )

    def put_publish_receipt(self, receipt: PublishReadinessReceipt) -> PublishReadinessReceipt:
        with self._lock:
            key = (
                f"{receipt.tenant_id}/{receipt.workspace_id}/"
                f"{receipt.dataset_id}/{receipt.run_id}"
            )
            self._publish_receipts[key] = receipt
            return deepcopy(receipt)

    def get_current_publish_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, run_id: str
    ) -> PublishReadinessReceipt | None:
        with self._lock:
            receipt = self._publish_receipts.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{run_id}"
            )
            if receipt is None or receipt.tenant_id != tenant_id:
                return None
            return deepcopy(receipt)

    def put_publish_execution(
        self, receipt: PublishExecutionReceipt, *, authority_fingerprint: str
    ) -> PublishExecutionReceipt:
        with self._lock:
            key = (
                f"{receipt.tenant_id}/{receipt.workspace_id}/"
                f"{receipt.dataset_id}/{receipt.run_id}/{receipt.publish_id}"
            )
            self._publish_executions[key] = receipt
            if receipt.status.value == "COMPLETE":
                auth_key = (
                    f"{receipt.tenant_id}/{receipt.workspace_id}/"
                    f"{receipt.dataset_id}/{receipt.run_id}/{authority_fingerprint}"
                )
                self._publish_authority[auth_key] = receipt.publish_id
            return deepcopy(receipt)

    def get_publish_execution(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
        publish_id: str,
    ) -> PublishExecutionReceipt | None:
        with self._lock:
            receipt = self._publish_executions.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{run_id}/{publish_id}"
            )
            if receipt is None or receipt.tenant_id != tenant_id:
                return None
            return deepcopy(receipt)

    def list_publish_executions(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, run_id: str
    ) -> list[PublishExecutionReceipt]:
        with self._lock:
            prefix = f"{tenant_id}/{workspace_id}/{dataset_id}/{run_id}/"
            rows = [
                deepcopy(item)
                for key, item in self._publish_executions.items()
                if key.startswith(prefix) and item.tenant_id == tenant_id
            ]
            return sorted(rows, key=lambda row: row.started_at)

    def get_publish_execution_by_authority(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
        authority_fingerprint: str,
    ) -> PublishExecutionReceipt | None:
        with self._lock:
            publish_id = self._publish_authority.get(
                f"{tenant_id}/{workspace_id}/{dataset_id}/{run_id}/{authority_fingerprint}"
            )
            if publish_id is None:
                return None
            return self.get_publish_execution(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                run_id=run_id,
                publish_id=publish_id,
            )

    @staticmethod
    def _upload_key(
        tenant_id: str, workspace_id: str, dataset_id: str, upload_id: str
    ) -> str:
        return f"{tenant_id}/{workspace_id}/{dataset_id}/{upload_id}"

    @staticmethod
    def _dataset_evaluation_key(
        tenant_id: str, workspace_id: str, dataset_id: str, run_id: str
    ) -> str:
        return f"{tenant_id}/{workspace_id}/{dataset_id}/{run_id}"

    @staticmethod
    def _idempotency_key(tenant_id: str, operation: str, key: str) -> str:
        return f"{tenant_id}/{operation}/{key}"

    # --- locked helpers ---

    def _put_identity_mapping_locked(
        self, mapping: IdentityProviderOrganizationMapping
    ) -> IdentityProviderOrganizationMapping:
        self._require_tenant_locked(mapping.tenant_id)
        key = identity_mapping_doc_id(mapping.provider, mapping.provider_organization_id)
        existing = self._identity_mappings.get(key)
        if existing is not None and existing.tenant_id != mapping.tenant_id:
            raise ProviderMappingConflictError(
                "Provider organization is already mapped to another PreM3 tenant."
            )
        self._identity_mappings[key] = mapping
        return mapping

    def _put_entitlement_locked(
        self, snapshot: EntitlementSnapshot, *, make_current: bool
    ) -> EntitlementSnapshot:
        tenant = self._require_tenant_locked(snapshot.tenant_id)
        key = f"{snapshot.tenant_id}/{snapshot.snapshot_id}"
        existing = self._entitlements.get(key)
        if existing is not None and existing != snapshot:
            raise ProviderMappingConflictError(
                "Entitlement snapshot_id is immutable and already exists with different content."
            )
        if existing is None:
            self._entitlements[key] = snapshot
        if make_current:
            self._tenants[snapshot.tenant_id] = tenant.model_copy(
                update={
                    "current_entitlement_snapshot_id": snapshot.snapshot_id,
                    "updated_at": datetime.now(UTC),
                }
            )
        return snapshot

    def _require_tenant_locked(self, tenant_id: str) -> Tenant:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Tenant does not exist.")
        return tenant

    def _require_workspace_locked(self, tenant_id: str, workspace_id: str) -> Workspace:
        self._require_tenant_locked(tenant_id)
        workspace = self._workspaces.get(f"{tenant_id}/{workspace_id}")
        if workspace is None or workspace.tenant_id != tenant_id:
            raise WorkspaceNotFoundError("MMM Project does not exist.")
        return workspace

    def _require_current_entitlement_locked(self, tenant_id: str) -> EntitlementSnapshot:
        tenant = self._require_tenant_locked(tenant_id)
        if tenant.current_entitlement_snapshot_id is None:
            raise EntitlementUnavailableError("No current entitlement snapshot for tenant.")
        snap = self._entitlements.get(
            f"{tenant_id}/{tenant.current_entitlement_snapshot_id}"
        )
        if snap is None:
            raise EntitlementUnavailableError("Current entitlement snapshot is missing.")
        return snap

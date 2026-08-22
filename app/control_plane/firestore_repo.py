"""Firestore-backed ControlPlaneRepository.

Uses google.cloud.firestore.Client (sync) with ADC or FIRESTORE_EMULATOR_HOST.
Inject the client — no hidden module-level singleton required by callers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore
from google.cloud.firestore import transactional

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
from app.control_plane.serialization import document_to_model, model_to_document
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

COLLECTION_TENANTS = "tenants"
COLLECTION_IDENTITY_MAPPINGS = "identity_org_mappings"
COLLECTION_MEMBERSHIPS = "memberships"
COLLECTION_WORKSPACES = "workspaces"
COLLECTION_DATASETS = "datasets"
COLLECTION_ENTITLEMENTS = "entitlements"
COLLECTION_BILLING_CUSTOMERS = "billing_customers"
COLLECTION_BILLING_SUBSCRIPTIONS = "billing_subscriptions"
COLLECTION_EVALUATION_REFS = "evaluation_refs"
COLLECTION_UPLOADS = "uploads"
COLLECTION_EVALUATIONS = "evaluations"
COLLECTION_IDEMPOTENCY = "idempotency"
COLLECTION_WEBHOOKS = "processed_webhook_events"
COLLECTION_OAUTH_TXNS = "google_oauth_transactions"
COLLECTION_GOOGLE_CONNECTIONS = "google_connections"
COLLECTION_CREDENTIAL_ENVELOPES = "credential_envelopes"
COLLECTION_DRIVE_BINDINGS = "drive_bindings"
COLLECTION_BQ_BINDINGS = "bigquery_bindings"
COLLECTION_IMPORT_SELECTIONS = "import_selections"
COLLECTION_IMPORT_RECEIPTS = "import_receipts"


class FirestoreControlPlaneRepository:
    def __init__(self, client: firestore.Client) -> None:
        self._db = client

    @property
    def client(self) -> firestore.Client:
        return self._db

    @classmethod
    def from_settings(
        cls,
        *,
        project_id: str,
        database: str = "(default)",
    ) -> FirestoreControlPlaneRepository:
        return cls(firestore.Client(project=project_id, database=database))

    # --- refs ---

    def _tenant_ref(self, tenant_id: str):
        return self._db.collection(COLLECTION_TENANTS).document(tenant_id)

    def _workspace_ref(self, tenant_id: str, workspace_id: str):
        return (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_WORKSPACES)
            .document(workspace_id)
        )

    def _dataset_ref(self, tenant_id: str, workspace_id: str, dataset_id: str):
        return (
            self._workspace_ref(tenant_id, workspace_id)
            .collection(COLLECTION_DATASETS)
            .document(dataset_id)
        )

    def _entitlement_ref(self, tenant_id: str, snapshot_id: str):
        return (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_ENTITLEMENTS)
            .document(snapshot_id)
        )

    def _membership_ref(self, tenant_id: str, provider: str, provider_user_id: str):
        return (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_MEMBERSHIPS)
            .document(membership_doc_id(provider, provider_user_id))
        )

    def _customer_ref(self, tenant_id: str, billing_provider: BillingProvider | str):
        return (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_BILLING_CUSTOMERS)
            .document(billing_customer_doc_id(billing_provider))
        )

    def _subscription_ref(self, tenant_id: str, billing_provider: BillingProvider | str):
        return (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_BILLING_SUBSCRIPTIONS)
            .document(billing_subscription_doc_id(billing_provider))
        )

    def _evaluation_ref_doc(self, tenant_id: str, run_id: str):
        return (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_EVALUATION_REFS)
            .document(run_id)
        )

    def _upload_ref(
        self, tenant_id: str, workspace_id: str, dataset_id: str, upload_id: str
    ):
        return (
            self._dataset_ref(tenant_id, workspace_id, dataset_id)
            .collection(COLLECTION_UPLOADS)
            .document(upload_id)
        )

    def _dataset_evaluation_doc(
        self, tenant_id: str, workspace_id: str, dataset_id: str, run_id: str
    ):
        return (
            self._dataset_ref(tenant_id, workspace_id, dataset_id)
            .collection(COLLECTION_EVALUATIONS)
            .document(run_id)
        )

    def _idempotency_ref(self, tenant_id: str, operation: str, key: str):
        doc_id = f"{_safe_firestore_segment(operation)}__{_safe_firestore_segment(key)}"
        return self._tenant_ref(tenant_id).collection(COLLECTION_IDEMPOTENCY).document(doc_id)

    def _identity_ref(self, provider: str, provider_organization_id: str):
        return self._db.collection(COLLECTION_IDENTITY_MAPPINGS).document(
            identity_mapping_doc_id(provider, provider_organization_id)
        )

    def _webhook_ref(self, provider: WebhookProvider | str, provider_event_id: str):
        return self._db.collection(COLLECTION_WEBHOOKS).document(
            webhook_event_doc_id(provider, provider_event_id)
        )

    # --- Tenant ---

    def create_tenant(
        self,
        *,
        display_name: str,
        identity_mapping: IdentityProviderOrganizationMapping | None = None,
        with_planner_entitlement: bool = True,
    ) -> Tenant:
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
        batch = self._db.batch()
        batch.create(self._tenant_ref(tenant_id), model_to_document(tenant))
        if identity_mapping is not None:
            mapped = identity_mapping.model_copy(
                update={"tenant_id": tenant_id, "created_at": now, "updated_at": now}
            )
            mapping_ref = self._identity_ref(
                mapped.provider.value, mapped.provider_organization_id
            )
            existing = mapping_ref.get()
            if existing.exists:
                prior = document_to_model(
                    IdentityProviderOrganizationMapping, existing.to_dict()
                )
                if prior.tenant_id != tenant_id:
                    raise ProviderMappingConflictError(
                        "Provider organization is already mapped to another PreM3 tenant."
                    )
            batch.set(mapping_ref, model_to_document(mapped))
        if with_planner_entitlement:
            snapshot = default_planner_entitlement(tenant_id=tenant_id, now=now)
            batch.create(
                self._entitlement_ref(tenant_id, snapshot.snapshot_id),
                model_to_document(snapshot),
            )
            tenant = tenant.model_copy(
                update={"current_entitlement_snapshot_id": snapshot.snapshot_id}
            )
            batch.set(self._tenant_ref(tenant_id), model_to_document(tenant))
        batch.commit()
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        snap = self._tenant_ref(tenant_id).get()
        if not snap.exists:
            return None
        return document_to_model(Tenant, snap.to_dict())

    def set_tenant_status(self, *, tenant_id: str, status: str) -> Tenant:
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Tenant does not exist.")
        updated = tenant.model_copy(
            update={"status": TenantStatus(status), "updated_at": datetime.now(UTC)}
        )
        self._tenant_ref(tenant_id).set(model_to_document(updated))
        return updated

    def put_identity_organization_mapping(
        self, mapping: IdentityProviderOrganizationMapping
    ) -> IdentityProviderOrganizationMapping:
        if self.get_tenant(mapping.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        ref = self._identity_ref(mapping.provider.value, mapping.provider_organization_id)
        existing = ref.get()
        if existing.exists:
            prior = document_to_model(
                IdentityProviderOrganizationMapping, existing.to_dict()
            )
            if prior.tenant_id != mapping.tenant_id:
                raise ProviderMappingConflictError(
                    "Provider organization is already mapped to another PreM3 tenant."
                )
        ref.set(model_to_document(mapping))
        return mapping

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
        snap = self._identity_ref(provider, provider_organization_id).get()
        if not snap.exists:
            return None
        return document_to_model(IdentityProviderOrganizationMapping, snap.to_dict())

    def upsert_membership_projection(
        self, membership: MembershipProjection
    ) -> MembershipProjection:
        if self.get_tenant(membership.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._membership_ref(
            membership.tenant_id,
            membership.provider.value,
            membership.provider_user_id,
        ).set(model_to_document(membership))
        return membership

    def get_membership_projection(
        self,
        *,
        tenant_id: str,
        provider: str,
        provider_user_id: str,
    ) -> MembershipProjection | None:
        snap = self._membership_ref(tenant_id, provider, provider_user_id).get()
        if not snap.exists:
            return None
        return document_to_model(MembershipProjection, snap.to_dict())

    def list_workspaces_for_tenant(self, tenant_id: str) -> list[Workspace]:
        if self.get_tenant(tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        rows: list[Workspace] = []
        for snap in self._tenant_ref(tenant_id).collection(COLLECTION_WORKSPACES).stream():
            rows.append(document_to_model(Workspace, snap.to_dict()))
        rows.sort(key=lambda item: item.created_at)
        return rows

    def get_workspace_for_tenant(
        self, *, tenant_id: str, workspace_id: str
    ) -> Workspace | None:
        snap = self._workspace_ref(tenant_id, workspace_id).get()
        if not snap.exists:
            return None
        workspace = document_to_model(Workspace, snap.to_dict())
        if workspace.tenant_id != tenant_id:
            return None
        return workspace

    def create_workspace_with_capacity(
        self, *, tenant_id: str, name: str, workspace_id: str | None = None
    ) -> Workspace:
        wsp_id = workspace_id or new_workspace_id()
        validate_resource_identifier(wsp_id, field="workspace_id")
        transaction = self._db.transaction()

        @transactional
        def _create(txn: firestore.Transaction) -> Workspace:
            tenant_ref = self._tenant_ref(tenant_id)
            tenant_snap = tenant_ref.get(transaction=txn)
            if not tenant_snap.exists:
                raise TenantNotFoundError("Tenant does not exist.")
            tenant = document_to_model(Tenant, tenant_snap.to_dict())
            if tenant.current_entitlement_snapshot_id is None:
                raise EntitlementUnavailableError(
                    "No current entitlement snapshot for tenant."
                )
            ent_ref = self._entitlement_ref(
                tenant_id, tenant.current_entitlement_snapshot_id
            )
            ent_snap = ent_ref.get(transaction=txn)
            if not ent_snap.exists:
                raise EntitlementUnavailableError("Current entitlement snapshot is missing.")
            entitlement = document_to_model(EntitlementSnapshot, ent_snap.to_dict())
            if tenant.active_workspace_count >= entitlement.max_active_projects:
                raise ProjectLimitReachedError(
                    "Active MMM Project capacity reached for current entitlement."
                )
            workspace_ref = self._workspace_ref(tenant_id, wsp_id)
            existing = workspace_ref.get(transaction=txn)
            if existing.exists:
                raise ProviderMappingConflictError(
                    "workspace_id already exists for tenant."
                )
            now = datetime.now(UTC)
            workspace = Workspace(
                tenant_id=tenant_id,
                workspace_id=wsp_id,
                name=name,
                status=WorkspaceStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            txn.create(workspace_ref, model_to_document(workspace))
            updated_tenant = tenant.model_copy(
                update={
                    "active_workspace_count": tenant.active_workspace_count + 1,
                    "updated_at": now,
                }
            )
            txn.set(tenant_ref, model_to_document(updated_tenant))
            return workspace

        return _create(transaction)

    def list_datasets_for_workspace(
        self, *, tenant_id: str, workspace_id: str
    ) -> list[Dataset]:
        if self.get_workspace_for_tenant(tenant_id=tenant_id, workspace_id=workspace_id) is None:
            raise WorkspaceNotFoundError("MMM Project does not exist.")
        rows: list[Dataset] = []
        for snap in (
            self._workspace_ref(tenant_id, workspace_id)
            .collection(COLLECTION_DATASETS)
            .stream()
        ):
            rows.append(document_to_model(Dataset, snap.to_dict()))
        rows.sort(key=lambda item: item.created_at)
        return rows

    def get_dataset_for_workspace(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> Dataset | None:
        snap = self._dataset_ref(tenant_id, workspace_id, dataset_id).get()
        if not snap.exists:
            return None
        dataset = document_to_model(Dataset, snap.to_dict())
        if dataset.tenant_id != tenant_id or dataset.workspace_id != workspace_id:
            return None
        return dataset

    def create_dataset(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        name: str,
        dataset_id: str | None = None,
    ) -> Dataset:
        if self.get_workspace_for_tenant(tenant_id=tenant_id, workspace_id=workspace_id) is None:
            raise WorkspaceNotFoundError("MMM Project does not exist.")
        dset_id = dataset_id or new_dataset_id()
        validate_resource_identifier(dset_id, field="dataset_id")
        ref = self._dataset_ref(tenant_id, workspace_id, dset_id)
        if ref.get().exists:
            raise ProviderMappingConflictError("dataset_id already exists for workspace.")
        now = datetime.now(UTC)
        dataset = Dataset(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=dset_id,
            name=name,
            status=DatasetStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        ref.create(model_to_document(dataset))
        return dataset

    def put_entitlement_snapshot(
        self, snapshot: EntitlementSnapshot, *, make_current: bool = True
    ) -> EntitlementSnapshot:
        tenant = self.get_tenant(snapshot.tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Tenant does not exist.")
        ref = self._entitlement_ref(snapshot.tenant_id, snapshot.snapshot_id)
        existing = ref.get()
        if existing.exists:
            prior = document_to_model(EntitlementSnapshot, existing.to_dict())
            if prior != snapshot:
                raise ProviderMappingConflictError(
                    "Entitlement snapshot_id is immutable and already exists "
                    "with different content."
                )
        else:
            ref.create(model_to_document(snapshot))
        if make_current:
            updated = tenant.model_copy(
                update={
                    "current_entitlement_snapshot_id": snapshot.snapshot_id,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._tenant_ref(snapshot.tenant_id).set(model_to_document(updated))
        return snapshot

    def get_entitlement_snapshot(
        self, *, tenant_id: str, snapshot_id: str
    ) -> EntitlementSnapshot | None:
        snap = self._entitlement_ref(tenant_id, snapshot_id).get()
        if not snap.exists:
            return None
        entitlement = document_to_model(EntitlementSnapshot, snap.to_dict())
        if entitlement.tenant_id != tenant_id:
            return None
        return entitlement

    def get_current_entitlement(self, tenant_id: str) -> EntitlementSnapshot:
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Tenant does not exist.")
        if tenant.current_entitlement_snapshot_id is None:
            raise EntitlementUnavailableError("No current entitlement snapshot for tenant.")
        snap = self.get_entitlement_snapshot(
            tenant_id=tenant_id, snapshot_id=tenant.current_entitlement_snapshot_id
        )
        if snap is None:
            raise EntitlementUnavailableError("Current entitlement snapshot is missing.")
        return snap

    def put_stripe_customer_mapping(
        self, mapping: StripeCustomerMapping
    ) -> StripeCustomerMapping:
        if self.get_tenant(mapping.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._customer_ref(mapping.tenant_id, mapping.billing_provider).set(
            model_to_document(mapping)
        )
        return mapping

    def get_stripe_customer_mapping(self, tenant_id: str) -> StripeCustomerMapping | None:
        snap = self._customer_ref(tenant_id, BillingProvider.STRIPE).get()
        if not snap.exists:
            return None
        return document_to_model(StripeCustomerMapping, snap.to_dict())

    def put_subscription_projection(
        self, projection: SubscriptionProjection
    ) -> SubscriptionProjection:
        if self.get_tenant(projection.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._subscription_ref(projection.tenant_id, projection.billing_provider).set(
            model_to_document(projection)
        )
        return projection

    def get_subscription_projection(self, tenant_id: str) -> SubscriptionProjection | None:
        snap = self._subscription_ref(tenant_id, BillingProvider.STRIPE).get()
        if not snap.exists:
            return None
        return document_to_model(SubscriptionProjection, snap.to_dict())

    def claim_webhook_event(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        event_type: str,
        lease_seconds: int = DEFAULT_WEBHOOK_CLAIM_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> WebhookClaimResult:
        transaction = self._db.transaction()
        provider_enum = (
            provider if isinstance(provider, WebhookProvider) else WebhookProvider(provider)
        )
        claimed_at = now

        @transactional
        def _claim(txn: firestore.Transaction) -> WebhookClaimResult:
            ref = self._webhook_ref(provider_enum, provider_event_id)
            snap = ref.get(transaction=txn)
            existing = (
                document_to_model(ProcessedWebhookEvent, snap.to_dict()) if snap.exists else None
            )
            stamp = claimed_at or datetime.now(UTC)
            result = decide_webhook_claim(
                existing,
                provider=provider_enum,
                provider_event_id=provider_event_id,
                event_type=event_type,
                now=stamp,
                lease_seconds=lease_seconds,
            )
            if result.status == WebhookClaimStatus.WON:
                if snap.exists:
                    txn.set(ref, model_to_document(result.event))
                else:
                    txn.create(ref, model_to_document(result.event))
            return result

        return _claim(transaction)

    def mark_webhook_event_processed(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        result: str | None = None,
    ) -> ProcessedWebhookEvent:
        ref = self._webhook_ref(provider, provider_event_id)
        snap = ref.get()
        if not snap.exists:
            raise WebhookAlreadyProcessedError("Webhook event was not claimed.")
        existing = document_to_model(ProcessedWebhookEvent, snap.to_dict())
        if existing.status == WebhookEventStatus.PROCESSED:
            return existing
        updated = existing.model_copy(
            update={
                "status": WebhookEventStatus.PROCESSED,
                "processed_at": datetime.now(UTC),
                "result": result,
            }
        )
        ref.set(model_to_document(updated))
        return updated

    def mark_webhook_event_failed(
        self,
        *,
        provider: WebhookProvider | str,
        provider_event_id: str,
        result: str | None = None,
    ) -> ProcessedWebhookEvent:
        ref = self._webhook_ref(provider, provider_event_id)
        snap = ref.get()
        if not snap.exists:
            raise WebhookAlreadyProcessedError("Webhook event was not claimed.")
        existing = document_to_model(ProcessedWebhookEvent, snap.to_dict())
        updated = existing.model_copy(
            update={
                "status": WebhookEventStatus.FAILED,
                "processed_at": datetime.now(UTC),
                "result": result,
            }
        )
        ref.set(model_to_document(updated))
        return updated

    def get_webhook_event(
        self, *, provider: WebhookProvider | str, provider_event_id: str
    ) -> ProcessedWebhookEvent | None:
        snap = self._webhook_ref(provider, provider_event_id).get()
        if not snap.exists:
            return None
        return document_to_model(ProcessedWebhookEvent, snap.to_dict())

    def create_upload(self, upload: DatasetUpload) -> DatasetUpload:
        dataset = self.get_dataset_for_workspace(
            tenant_id=upload.tenant_id,
            workspace_id=upload.workspace_id,
            dataset_id=upload.dataset_id,
        )
        if dataset is None:
            raise DatasetNotFoundError("Dataset does not exist for upload.")
        ref = self._upload_ref(
            upload.tenant_id, upload.workspace_id, upload.dataset_id, upload.upload_id
        )
        if ref.get().exists:
            raise ProviderMappingConflictError("Upload already exists.")
        ref.set(model_to_document(upload))
        return upload

    def get_upload(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        upload_id: str,
    ) -> DatasetUpload | None:
        snap = self._upload_ref(tenant_id, workspace_id, dataset_id, upload_id).get()
        if not snap.exists:
            return None
        upload = document_to_model(DatasetUpload, snap.to_dict())
        if (
            upload.tenant_id != tenant_id
            or upload.workspace_id != workspace_id
            or upload.dataset_id != dataset_id
        ):
            return None
        return upload

    def update_upload(self, upload: DatasetUpload) -> DatasetUpload:
        ref = self._upload_ref(
            upload.tenant_id, upload.workspace_id, upload.dataset_id, upload.upload_id
        )
        snap = ref.get()
        if not snap.exists:
            raise DatasetNotFoundError("Upload does not exist.")
        existing = document_to_model(DatasetUpload, snap.to_dict())
        if (
            existing.tenant_id != upload.tenant_id
            or existing.workspace_id != upload.workspace_id
            or existing.dataset_id != upload.dataset_id
        ):
            raise ProviderMappingConflictError("Upload cannot be re-parented.")
        ref.set(model_to_document(upload))
        return upload

    def put_evaluation_ref(self, ref: DatasetEvaluationRef) -> DatasetEvaluationRef:
        dataset = self.get_dataset_for_workspace(
            tenant_id=ref.tenant_id,
            workspace_id=ref.workspace_id,
            dataset_id=ref.dataset_id,
        )
        if dataset is None:
            raise DatasetNotFoundError("Dataset does not exist for evaluation linkage.")
        existing_snap = self._evaluation_ref_doc(ref.tenant_id, ref.run_id).get()
        if existing_snap.exists:
            existing = document_to_model(DatasetEvaluationRef, existing_snap.to_dict())
            if (
                existing.workspace_id != ref.workspace_id
                or existing.dataset_id != ref.dataset_id
                or existing.upload_id != ref.upload_id
            ):
                raise ProviderMappingConflictError("Evaluation linkage is immutable.")
        payload = model_to_document(ref)
        self._evaluation_ref_doc(ref.tenant_id, ref.run_id).set(payload)
        self._dataset_evaluation_doc(
            ref.tenant_id, ref.workspace_id, ref.dataset_id, ref.run_id
        ).set(payload)
        return ref

    def get_evaluation_ref(
        self, *, tenant_id: str, run_id: str
    ) -> DatasetEvaluationRef | None:
        snap = self._evaluation_ref_doc(tenant_id, run_id).get()
        if not snap.exists:
            return None
        ref = document_to_model(DatasetEvaluationRef, snap.to_dict())
        if ref.tenant_id != tenant_id:
            return None
        return ref

    def list_evaluations_for_dataset(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
    ) -> list[DatasetEvaluationRef]:
        rows: list[DatasetEvaluationRef] = []
        for snap in (
            self._dataset_ref(tenant_id, workspace_id, dataset_id)
            .collection(COLLECTION_EVALUATIONS)
            .stream()
        ):
            ref = document_to_model(DatasetEvaluationRef, snap.to_dict())
            if (
                ref.tenant_id == tenant_id
                and ref.workspace_id == workspace_id
                and ref.dataset_id == dataset_id
            ):
                rows.append(ref)
        rows.sort(key=lambda item: item.run_id)
        return rows

    def get_idempotent_result(
        self, *, tenant_id: str, operation: str, key: str
    ) -> dict[str, Any] | None:
        snap = self._idempotency_ref(tenant_id, operation, key).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        result = data.get("result")
        return dict(result) if isinstance(result, dict) else None

    def put_idempotent_result(
        self,
        *,
        tenant_id: str,
        operation: str,
        key: str,
        result: dict[str, Any],
    ) -> None:
        if self.get_tenant(tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._idempotency_ref(tenant_id, operation, key).set(
            {
                "schema_version": 1,
                "tenant_id": tenant_id,
                "operation": operation,
                "key": key,
                "result": result,
                "created_at": datetime.now(UTC),
            }
        )

    def put_oauth_transaction(self, txn: GoogleOAuthTransaction) -> GoogleOAuthTransaction:
        if self.get_tenant(txn.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._db.collection(COLLECTION_OAUTH_TXNS).document(txn.state_hash).set(
            model_to_document(txn)
        )
        return txn

    def get_oauth_transaction_by_state_hash(
        self, state_hash: str
    ) -> GoogleOAuthTransaction | None:
        snap = self._db.collection(COLLECTION_OAUTH_TXNS).document(state_hash).get()
        if not snap.exists:
            return None
        return document_to_model(GoogleOAuthTransaction, snap.to_dict())

    def consume_oauth_transaction(
        self, *, state_hash: str, consumed_at: datetime
    ) -> GoogleOAuthTransaction | None:
        ref = self._db.collection(COLLECTION_OAUTH_TXNS).document(state_hash)
        snap = ref.get()
        if not snap.exists:
            return None
        txn = document_to_model(GoogleOAuthTransaction, snap.to_dict())
        if txn.consumed_at is not None:
            return None
        updated = txn.model_copy(update={"consumed_at": consumed_at})
        ref.set(model_to_document(updated))
        return updated

    def put_google_connection(self, connection: GoogleConnection) -> GoogleConnection:
        if self.get_tenant(connection.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._tenant_ref(connection.tenant_id).collection(COLLECTION_GOOGLE_CONNECTIONS).document(
            connection.connection_id
        ).set(model_to_document(connection))
        return connection

    def get_google_connection(
        self, *, tenant_id: str, connection_id: str
    ) -> GoogleConnection | None:
        snap = (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_GOOGLE_CONNECTIONS)
            .document(connection_id)
            .get()
        )
        if not snap.exists:
            return None
        conn = document_to_model(GoogleConnection, snap.to_dict())
        if conn.tenant_id != tenant_id:
            return None
        return conn

    def list_google_connections(self, *, tenant_id: str) -> list[GoogleConnection]:
        rows: list[GoogleConnection] = []
        for snap in self._tenant_ref(tenant_id).collection(COLLECTION_GOOGLE_CONNECTIONS).stream():
            conn = document_to_model(GoogleConnection, snap.to_dict())
            if conn.tenant_id == tenant_id:
                rows.append(conn)
        rows.sort(key=lambda item: item.connection_id)
        return rows

    def put_credential_envelope(self, envelope: CredentialEnvelope) -> CredentialEnvelope:
        if self.get_tenant(envelope.tenant_id) is None:
            raise TenantNotFoundError("Tenant does not exist.")
        self._tenant_ref(envelope.tenant_id).collection(COLLECTION_CREDENTIAL_ENVELOPES).document(
            envelope.credential_ref
        ).set(model_to_document(envelope))
        return envelope

    def get_credential_envelope(
        self, *, tenant_id: str, credential_ref: str
    ) -> CredentialEnvelope | None:
        snap = (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_CREDENTIAL_ENVELOPES)
            .document(credential_ref)
            .get()
        )
        if not snap.exists:
            return None
        envelope = document_to_model(CredentialEnvelope, snap.to_dict())
        if envelope.tenant_id != tenant_id:
            return None
        return envelope

    def delete_credential_envelope(self, *, tenant_id: str, credential_ref: str) -> None:
        (
            self._tenant_ref(tenant_id)
            .collection(COLLECTION_CREDENTIAL_ENVELOPES)
            .document(credential_ref)
            .delete()
        )

    def put_drive_binding(self, binding: DriveWorkspaceBinding) -> DriveWorkspaceBinding:
        self._workspace_ref(binding.tenant_id, binding.workspace_id).collection(
            COLLECTION_DRIVE_BINDINGS
        ).document("current").set(model_to_document(binding))
        return binding

    def get_drive_binding(
        self, *, tenant_id: str, workspace_id: str
    ) -> DriveWorkspaceBinding | None:
        snap = (
            self._workspace_ref(tenant_id, workspace_id)
            .collection(COLLECTION_DRIVE_BINDINGS)
            .document("current")
            .get()
        )
        if not snap.exists:
            return None
        binding = document_to_model(DriveWorkspaceBinding, snap.to_dict())
        if binding.tenant_id != tenant_id:
            return None
        return binding

    def put_bigquery_binding(
        self, binding: BigQueryWorkspaceBinding
    ) -> BigQueryWorkspaceBinding:
        self._workspace_ref(binding.tenant_id, binding.workspace_id).collection(
            COLLECTION_BQ_BINDINGS
        ).document("current").set(model_to_document(binding))
        return binding

    def get_bigquery_binding(
        self, *, tenant_id: str, workspace_id: str
    ) -> BigQueryWorkspaceBinding | None:
        snap = (
            self._workspace_ref(tenant_id, workspace_id)
            .collection(COLLECTION_BQ_BINDINGS)
            .document("current")
            .get()
        )
        if not snap.exists:
            return None
        binding = document_to_model(BigQueryWorkspaceBinding, snap.to_dict())
        if binding.tenant_id != tenant_id:
            return None
        return binding

    def put_import_selection(
        self, selection: DatasetImportSelection
    ) -> DatasetImportSelection:
        self._dataset_ref(
            selection.tenant_id, selection.workspace_id, selection.dataset_id
        ).collection(COLLECTION_IMPORT_SELECTIONS).document("current").set(
            model_to_document(selection)
        )
        return selection

    def get_import_selection(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> DatasetImportSelection | None:
        snap = (
            self._dataset_ref(tenant_id, workspace_id, dataset_id)
            .collection(COLLECTION_IMPORT_SELECTIONS)
            .document("current")
            .get()
        )
        if not snap.exists:
            return None
        selection = document_to_model(DatasetImportSelection, snap.to_dict())
        if selection.tenant_id != tenant_id:
            return None
        return selection

    def put_import_receipt(self, receipt: ImportReadinessReceipt) -> ImportReadinessReceipt:
        col = (
            self._dataset_ref(receipt.tenant_id, receipt.workspace_id, receipt.dataset_id)
            .collection(COLLECTION_IMPORT_RECEIPTS)
        )
        current = col.document("current").get()
        if current.exists:
            previous = document_to_model(ImportReadinessReceipt, current.to_dict())
            if previous.receipt_id != receipt.receipt_id:
                superseded = previous.model_copy(update={"superseded": True})
                col.document(previous.receipt_id).set(model_to_document(superseded))
        col.document(receipt.receipt_id).set(model_to_document(receipt))
        col.document("current").set(model_to_document(receipt))
        return receipt

    def get_import_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str, receipt_id: str
    ) -> ImportReadinessReceipt | None:
        snap = (
            self._dataset_ref(tenant_id, workspace_id, dataset_id)
            .collection(COLLECTION_IMPORT_RECEIPTS)
            .document(receipt_id)
            .get()
        )
        if not snap.exists:
            return None
        receipt = document_to_model(ImportReadinessReceipt, snap.to_dict())
        if receipt.tenant_id != tenant_id:
            return None
        return receipt

    def get_current_import_receipt(
        self, *, tenant_id: str, workspace_id: str, dataset_id: str
    ) -> ImportReadinessReceipt | None:
        snap = (
            self._dataset_ref(tenant_id, workspace_id, dataset_id)
            .collection(COLLECTION_IMPORT_RECEIPTS)
            .document("current")
            .get()
        )
        if not snap.exists:
            return None
        receipt = document_to_model(ImportReadinessReceipt, snap.to_dict())
        if receipt.tenant_id != tenant_id:
            return None
        return receipt

    def delete_document_tree_for_qualification(self, tenant_id: str) -> list[str]:
        """Delete a synthetic qualification tenant subtree. Not a product API."""
        deleted: list[str] = []
        tenant_ref = self._tenant_ref(tenant_id)
        for collection in (
            COLLECTION_MEMBERSHIPS,
            COLLECTION_ENTITLEMENTS,
            COLLECTION_BILLING_CUSTOMERS,
            COLLECTION_BILLING_SUBSCRIPTIONS,
            COLLECTION_EVALUATION_REFS,
            COLLECTION_IDEMPOTENCY,
            COLLECTION_GOOGLE_CONNECTIONS,
            COLLECTION_CREDENTIAL_ENVELOPES,
        ):
            for snap in tenant_ref.collection(collection).stream():
                snap.reference.delete()
                deleted.append(snap.reference.path)
        for ws in tenant_ref.collection(COLLECTION_WORKSPACES).stream():
            for binding_col in (COLLECTION_DRIVE_BINDINGS, COLLECTION_BQ_BINDINGS):
                for snap in ws.reference.collection(binding_col).stream():
                    snap.reference.delete()
                    deleted.append(snap.reference.path)
            for ds in ws.reference.collection(COLLECTION_DATASETS).stream():
                for upload in ds.reference.collection(COLLECTION_UPLOADS).stream():
                    upload.reference.delete()
                    deleted.append(upload.reference.path)
                for evaluation in ds.reference.collection(COLLECTION_EVALUATIONS).stream():
                    evaluation.reference.delete()
                    deleted.append(evaluation.reference.path)
                for selection in ds.reference.collection(COLLECTION_IMPORT_SELECTIONS).stream():
                    selection.reference.delete()
                    deleted.append(selection.reference.path)
                for receipt in ds.reference.collection(COLLECTION_IMPORT_RECEIPTS).stream():
                    receipt.reference.delete()
                    deleted.append(receipt.reference.path)
                ds.reference.delete()
                deleted.append(ds.reference.path)
            ws.reference.delete()
            deleted.append(ws.reference.path)
        tenant_ref.delete()
        deleted.append(tenant_ref.path)
        return deleted


def _safe_firestore_segment(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("document key segment must not be empty")
    return (
        text.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )

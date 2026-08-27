"""Frozen Mission 2 control-plane persistence models.

These are server-internal. Do not export them through REQ-001 schema families.
Future FastAPI presentation contracts (MeResponse, WorkspaceResponse, …) are
separate and presentation-safe.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.identifiers import validate_resource_identifier


class TenantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class WorkspaceStatus(StrEnum):
    """Customer-facing Project status. ACTIVE counts toward capacity."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ProjectScopeType(StrEnum):
    COMPANY = "COMPANY"
    BRAND = "BRAND"
    BUSINESS_UNIT = "BUSINESS_UNIT"
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    PRODUCT_PORTFOLIO = "PRODUCT_PORTFOLIO"
    CUSTOM = "CUSTOM"


class MeasurementTrackType(StrEnum):
    MMM = "MMM"
    MTA = "MTA"
    FORECAST = "FORECAST"


class MeasurementTrackStatus(StrEnum):
    """Shared track envelope. Methodology workflow state stays domain-owned."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    AVAILABLE_TO_CONFIGURE = "AVAILABLE_TO_CONFIGURE"
    CONFIGURING = "CONFIGURING"
    READY_TO_RUN = "READY_TO_RUN"
    RUNNING = "RUNNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class DatasetStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class EntitlementStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    TRIALING = "TRIALING"
    INCOMPLETE = "INCOMPLETE"


class EntitlementSource(StrEnum):
    DEFAULT = "DEFAULT"
    BILLING_PROVIDER = "BILLING_PROVIDER"
    MANUAL_GRANT = "MANUAL_GRANT"


class Feature(StrEnum):
    PROJECT_CREATE = "project_create"
    PLANNING_RUN = "planning_run"
    PLAN_COMPILE = "plan_compile"
    PLAN_EXPORT = "plan_export"
    DATASET_CREATE = "dataset_create"
    DATA_UPLOAD = "data_upload"
    DATASET_ASSESSMENT = "dataset_assessment"
    SAFE_REMEDIATION = "safe_remediation"
    BIGQUERY_PUBLISH = "bigquery_publish"
    OFFICIAL_MERIDIAN_EDA = "official_meridian_eda"
    MERIDIAN_INTEGRATION = "meridian_integration"
    REGISTRY_RESEARCH = "registry_research"
    TEAM_SEATS = "team_seats"
    FOUNDATION = "foundation"
    MMM = "mmm"
    MTA = "mta"
    FORECASTING = "forecasting"
    SCENARIO_SIMULATION = "scenario_simulation"
    BUDGET_OPTIMIZATION = "budget_optimization"
    DECISION_INTELLIGENCE = "decision_intelligence"
    PORTFOLIO_VIEW = "portfolio_view"
    API_ACCESS = "api_access"


class IdentityProvider(StrEnum):
    CLERK = "clerk"


class BillingProvider(StrEnum):
    STRIPE = "stripe"


class WebhookProvider(StrEnum):
    STRIPE = "stripe"
    CLERK = "clerk"


class WebhookEventStatus(StrEnum):
    """Minimal claim state machine.

    CLAIMED: a worker owns processing until ``claim_expires_at``. A stale CLAIMED
    event may be reclaimed after the lease. FAILED may be reclaimed immediately.
    PROCESSED is terminal success.
    """

    CLAIMED = "CLAIMED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class WebhookClaimStatus(StrEnum):
    WON = "WON"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    ALREADY_PROCESSED = "ALREADY_PROCESSED"


class Tenant(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    display_name: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime
    current_entitlement_snapshot_id: str | None = None
    active_workspace_count: int = 0

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class IdentityProviderOrganizationMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: IdentityProvider
    provider_organization_id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("provider_organization_id")
    @classmethod
    def _provider_org(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("provider_organization_id must not be empty.")
        return text


class MembershipProjection(BaseModel):
    """Operational projection of identity-provider membership. Not request-time proof."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    provider: IdentityProvider
    provider_user_id: str
    provider_organization_id: str | None = None
    role: str | None = None
    status: MembershipStatus
    updated_at: datetime

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class Workspace(BaseModel):
    """Canonical Project store. Storage key remains workspace_id; product name is Project."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    name: str
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    scope_type: ProjectScopeType = ProjectScopeType.CUSTOM
    brand_name: str | None = None
    business_unit: str | None = None
    primary_market: str | None = None
    markets: tuple[str, ...] = ()
    default_currency: str | None = None
    default_timezone: str | None = None
    logo_ref: str | None = None
    archived_at: datetime | None = None

    @property
    def project_id(self) -> str:
        return self.workspace_id

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")


class Dataset(BaseModel):
    """Durable Dataset permanently owned by one workspace. Not re-parentable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    dataset_id: str
    name: str
    status: DatasetStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="dataset_id")


class EntitlementSnapshot(BaseModel):
    """Immutable commercial entitlement evidence. New state => new snapshot_id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str
    tenant_id: str
    plan_id: str
    features: frozenset[Feature]
    limits: dict[str, int]
    status: EntitlementStatus
    valid_until: datetime | None
    source: EntitlementSource
    created_at: datetime

    @field_validator("snapshot_id")
    @classmethod
    def _snapshot_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="snapshot_id")

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @property
    def max_active_projects(self) -> int:
        return int(self.limits.get("max_active_projects", 0))


class StripeCustomerMapping(BaseModel):
    """Billing provider customer mapping. Provider customer ID is never storage authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    billing_provider: BillingProvider
    provider_customer_id: str
    created_at: datetime
    updated_at: datetime

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class SubscriptionProjection(BaseModel):
    """Operational Stripe subscription projection. Not product authorization by itself."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    billing_provider: BillingProvider
    provider_customer_id: str
    provider_subscription_id: str
    plan_id: str
    status: str
    provider_updated_at: datetime
    projected_at: datetime
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class ProcessedWebhookEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: WebhookProvider
    provider_event_id: str
    event_type: str
    status: WebhookEventStatus
    processed_at: datetime | None = None
    claimed_at: datetime
    claim_expires_at: datetime | None = None
    result: str | None = None


class WebhookClaimResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: WebhookClaimStatus
    event: ProcessedWebhookEvent


class UploadStatus(StrEnum):
    PENDING = "PENDING"
    UPLOADED = "UPLOADED"
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"


class EvaluationStatus(StrEnum):
    """Pre-execution Evaluation lifecycle. DurableRunState owns execution stages."""

    ACCEPTED = "ACCEPTED"


class DatasetUploadFile(BaseModel):
    """One server-owned object within a DatasetUpload. Filename is presentation only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_file_id: str
    original_filename: str
    object_name: str
    content_type: str
    declared_size_bytes: int
    actual_size_bytes: int | None = None
    generation: str | None = None
    etag: str | None = None
    crc32c: str | None = None
    md5_hash: str | None = None
    created_at: datetime
    verified_at: datetime | None = None

    @field_validator("upload_file_id")
    @classmethod
    def _upload_file_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="upload_file_id")


class DatasetUpload(BaseModel):
    """Server-owned multi-file Dataset package upload. Not re-parentable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    dataset_id: str
    upload_id: str
    status: UploadStatus
    object_prefix: str
    files: list[DatasetUploadFile]
    package_uri: str | None = None
    package_fingerprint: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="dataset_id")

    @field_validator("upload_id")
    @classmethod
    def _upload_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="upload_id")


class DatasetEvaluationRef(BaseModel):
    """First-class Evaluation resource. Not DurableRunState. Not MODEL_READY authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    dataset_id: str
    upload_id: str
    run_id: str
    entitlement_snapshot_id: str
    status: EvaluationStatus = EvaluationStatus.ACCEPTED
    package_uri: str
    package_fingerprint: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="dataset_id")

    @field_validator("upload_id")
    @classmethod
    def _upload_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="upload_id")

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="run_id")

    @field_validator("entitlement_snapshot_id")
    @classmethod
    def _entitlement_snapshot_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="entitlement_snapshot_id")


# Canonical product name for DatasetEvaluationRef.
Evaluation = DatasetEvaluationRef


class DispatchStatus(StrEnum):
    """Durable launch/execution transport. Not MODEL_READY and not EvaluationStatus."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    LAUNCHING = "LAUNCHING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class EvaluationDispatch(BaseModel):
    """Server-owned Evaluation launch record. dispatch_id is never customer authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatch_id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    run_id: str
    evaluation_created_at: datetime
    status: DispatchStatus
    attempt_count: int = 0
    cloud_task_name: str | None = None
    cloud_run_job_name: str
    cloud_run_execution_name: str | None = None
    claim_owner: str | None = None
    claim_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    launched_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    last_error_code: str | None = None
    last_error_detail: str | None = None

    @field_validator("dispatch_id")
    @classmethod
    def _dispatch_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="dispatch_id")

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="dataset_id")

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="run_id")


class RegistryOverlayMetadata(BaseModel):
    """Storage seam only. Does not load overlays into the bundled registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    overlay_version: str
    provider_key: str
    provenance_pointer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class GoogleOAuthTransaction(BaseModel):
    """Short-lived, single-use OAuth state. Callback cannot override tenant/workspace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    state_hash: str
    tenant_id: str
    initiating_user_id: str
    workspace_id: str | None = None
    dataset_id: str | None = None
    requested_capabilities: tuple[str, ...]
    requested_scopes: tuple[str, ...]
    return_path: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None

    @field_validator("transaction_id")
    @classmethod
    def _transaction_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="transaction_id")

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class GoogleConnection(BaseModel):
    """Tenant-scoped Google authorization. connection_id is not global authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connection_id: str
    tenant_id: str
    authorized_by_user_id: str
    google_subject: str
    display_email: str | None = None
    status: str
    granted_scopes: tuple[str, ...]
    capabilities: tuple[str, ...]
    credential_ref: str
    created_at: datetime
    updated_at: datetime
    last_verified_at: datetime | None = None
    revoked_at: datetime | None = None

    @field_validator("connection_id")
    @classmethod
    def _connection_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="connection_id")

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class CredentialEnvelope(BaseModel):
    """Encrypted vault metadata. Never contains a plaintext refresh token."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    credential_ref: str
    algorithm: str
    ciphertext: str
    nonce: str = ""
    wrapped_dek: str
    kms_key: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("credential_ref")
    @classmethod
    def _credential_ref(cls, value: str) -> str:
        return validate_resource_identifier(value, field="credential_ref")


class DriveWorkspaceBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    connection_id: str
    root_folder_id: str
    root_folder_name: str = "prem3-modeling"
    imports_folder_id: str
    exports_folder_id: str
    reports_folder_id: str
    budgets_folder_id: str | None = None
    budget_templates_folder_id: str | None = None
    budget_plans_folder_id: str | None = None
    budget_scenarios_folder_id: str | None = None
    budget_proposals_folder_id: str | None = None
    status: str
    import_enabled: bool
    export_enabled: bool
    created_at: datetime
    updated_at: datetime
    last_verified_at: datetime | None = None

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")


class BigQueryWorkspaceBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    connection_id: str
    source_project_ids: tuple[str, ...]
    source_dataset_ids: tuple[str, ...]
    destination_project_id: str
    destination_dataset_id: str = "prem3_modeling"
    destination_friendly_name: str = "prem3-modeling"
    location: str
    read_verified: bool
    write_verified: bool
    status: str
    created_at: datetime
    updated_at: datetime
    last_verified_at: datetime | None = None

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")


class DatasetImportSelection(BaseModel):
    """Server-owned Dataset import selection. No tokens or GCS authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    dataset_id: str
    source_type: str
    connection_id: str | None = None
    binding_id: str | None = None
    upload_id: str | None = None
    selected_object_ids: tuple[str, ...]
    role_assignments: tuple[dict[str, str], ...]
    current_receipt_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class TrackConfigRevision(BaseModel):
    """Immutable analytical configuration snapshot for a consumed Track version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    configuration_version: int
    config: dict[str, Any] = Field(default_factory=dict)
    consumed_by_run_id: str | None = None
    created_at: datetime


class MeasurementTrack(BaseModel):
    """Methodology-specific track under a Project MeasurementCycle. Not an MMM run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    track_id: str
    tenant_id: str
    workspace_id: str
    cycle_id: str
    track_type: MeasurementTrackType
    status: MeasurementTrackStatus
    configuration_version: int = 1
    config: dict[str, Any] = Field(default_factory=dict)
    config_revisions: tuple[TrackConfigRevision, ...] = ()
    consumed_run_versions: dict[str, int] = Field(default_factory=dict)
    input_readiness_state: str | None = None
    readiness_receipt_ref: str | None = None
    latest_run_id: str | None = None
    accepted_artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime

    def is_consumed(self) -> bool:
        return bool(
            self.latest_run_id
            or self.accepted_artifact_id
            or self.readiness_receipt_ref
            or self.consumed_run_versions
        )

    @property
    def project_id(self) -> str:
        return self.workspace_id

    @field_validator("track_id")
    @classmethod
    def _track_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="track_id")

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="workspace_id")

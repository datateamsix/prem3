"""Frozen M2-12 materialization receipts. Distinct from DriveImportReceipt."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.identifiers import validate_resource_identifier
from app.governance.codes import SourceType
from app.governance.fingerprint import sha256_canonical


class MaterializationStatus(StrEnum):
    REVALIDATING = "REVALIDATING"
    COPYING = "COPYING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class MaterializationResultKind(StrEnum):
    CREATED_NEW_UPLOAD = "CREATED_NEW_UPLOAD"
    REUSED_EXISTING_UPLOAD = "REUSED_EXISTING_UPLOAD"


class SourceObjectLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    object_id: str
    provider: str
    role: str
    logical_name: str
    source_identity: str
    version_identity: str
    object_type: str
    format: str | None = None
    schema_fingerprint: str | None = None
    upload_file_id: str | None = None
    target_generation: str | None = None
    target_checksum: str | None = None


class SourceMaterializationReceipt(BaseModel):
    """Immutable proof that a governed source was copied or reused as DatasetUpload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    materialization_id: str
    source_type: SourceType
    source_binding_id: str | None = None
    import_receipt_id: str
    import_manifest_fingerprint: str
    foundation_source_receipt_id: str | None = None
    foundation_status: str | None = None
    business_profile_snapshot_id: str | None = None
    evidence_requirement_ids: list[str] = Field(default_factory=list)
    source_objects: list[SourceObjectLineage] = Field(default_factory=list)
    source_version_identities: list[str] = Field(default_factory=list)
    status: MaterializationStatus
    result_kind: MaterializationResultKind | None = None
    upload_id: str | None = None
    upload_package_fingerprint: str | None = None
    upload_status: str | None = None
    authority_fingerprint: str
    materialization_fingerprint: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    premodel_review_remaining: bool = False
    premodel_review_findings: list[str] = Field(default_factory=list)
    failure_code: str | None = None
    failure_detail: str | None = None
    provider: str | None = None
    business_role: str | None = None
    history: str | None = None
    refresh_cadence: str | None = None
    freshness: str | None = None
    grain: str | None = None
    geography: str | None = None
    metrics: list[str] = Field(default_factory=list)

    @field_validator("receipt_id")
    @classmethod
    def _receipt_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="receipt_id")

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

    @field_validator("materialization_id")
    @classmethod
    def _materialization_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="materialization_id")


def authority_fingerprint(
    *,
    tenant_id: str,
    workspace_id: str,
    dataset_id: str,
    import_receipt_id: str,
    import_status: str,
    import_manifest_fingerprint: str,
    source_version_identities: list[str],
    foundation_source_receipt_id: str | None,
    foundation_status: str | None,
) -> str:
    return sha256_canonical(
        {
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "import_receipt_id": import_receipt_id,
            "import_status": import_status,
            "import_manifest_fingerprint": import_manifest_fingerprint,
            "source_version_identities": list(source_version_identities),
            "foundation_source_receipt_id": foundation_source_receipt_id,
            "foundation_status": foundation_status,
        }
    )


def materialization_result_fingerprint(
    *,
    authority: str,
    upload_id: str | None,
    upload_package_fingerprint: str | None,
) -> str:
    return sha256_canonical(
        {
            "authority_fingerprint": authority,
            "upload_id": upload_id,
            "upload_package_fingerprint": upload_package_fingerprint,
        }
    )

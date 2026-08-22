"""Publish execution receipts. Do not mutate PublishReadinessReceipt in place."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.identifiers import validate_resource_identifier
from app.governance.fingerprint import sha256_canonical


class PublishExecutionStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DestinationResultKind(StrEnum):
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    BIGQUERY = "BIGQUERY"


class DestinationWriteStatus(StrEnum):
    VERIFIED = "VERIFIED"
    VERIFIED_EXISTING = "VERIFIED_EXISTING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PublishedArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    identity: str
    size_bytes: int | None = None
    checksum: str | None = None
    verified: bool = False


class DestinationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: DestinationResultKind
    binding_id: str
    target_presentation_identity: str
    versioned_resource_identity: str | None = None
    stable_pointer_identity: str | None = None
    artifacts_written: list[PublishedArtifact] = Field(default_factory=list)
    artifacts_verified: list[PublishedArtifact] = Field(default_factory=list)
    row_count: int | None = None
    schema_fingerprint: str | None = None
    content_fingerprint: str | None = None
    write_completed: bool = False
    readback_verified: bool = False
    status: DestinationWriteStatus
    failure_code: str | None = None
    failure_detail: str | None = None


class PublishExecutionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_id: str
    publish_id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    run_id: str
    publish_contract_fingerprint: str
    publish_readiness_receipt_id: str
    model_ready_fingerprint: str
    status: PublishExecutionStatus
    destination_results: list[DestinationResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
    failure_code: str | None = None
    failure_detail: str | None = None

    @field_validator("receipt_id")
    @classmethod
    def _receipt_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="receipt_id")

    @field_validator("publish_id")
    @classmethod
    def _publish_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="publish_id")

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, value: str) -> str:
        return validate_resource_identifier(value, field="tenant_id")


class ModelReadyEvidence(BaseModel):
    """Server-owned MODEL_READY proof. Resolver reads; it never emits MODEL_READY."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    workspace_id: str
    dataset_id: str
    run_id: str
    fingerprint: str
    artifacts: dict[str, bytes] = Field(default_factory=dict)
    artifact_checksums: dict[str, str] = Field(default_factory=dict)
    row_count: int | None = None
    schema_fingerprint: str | None = None


def publish_authority_fingerprint(
    *,
    tenant_id: str,
    workspace_id: str,
    dataset_id: str,
    run_id: str,
    model_ready_fingerprint: str,
    publish_contract_fingerprint: str,
    destination_bindings: list[str],
) -> str:
    return sha256_canonical(
        {
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "run_id": run_id,
            "model_ready_fingerprint": model_ready_fingerprint,
            "publish_contract_fingerprint": publish_contract_fingerprint,
            "destination_bindings": list(destination_bindings),
        }
    )

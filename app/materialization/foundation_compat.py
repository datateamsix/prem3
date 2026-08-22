"""Smallest Data Foundation compatibility seam until PR #15 merges.

Default implementation returns None: the import is not known to be
Data Foundation-managed, so only IMPORT_READY is required.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


FOUNDATION_SOURCE_READY = "FOUNDATION_SOURCE_READY"
FOUNDATION_SOURCE_NOT_READY = "FOUNDATION_SOURCE_NOT_READY"


class FoundationSourceEvidence(BaseModel):
    """Compatibility fields only. Not a second Data Foundation domain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_binding_id: str
    source_foundation_receipt_id: str
    status_code: str
    governance_import_ready: bool
    premodel_review_remaining: bool = False
    premodel_review_findings: list[str] = Field(default_factory=list)
    resource_identity: str | None = None
    source_version_ref: str | None = None
    tenant_id: str | None = None
    workspace_id: str | None = None
    business_profile_snapshot_id: str | None = None
    evidence_requirement_ids: list[str] = Field(default_factory=list)
    provider: str | None = None
    business_role: str | None = None
    history: str | None = None
    refresh_cadence: str | None = None
    freshness: str | None = None
    grain: str | None = None
    geography: str | None = None
    metrics: list[str] = Field(default_factory=list)


class FoundationSourceGate(Protocol):
    def get_source_materialization_evidence(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
    ) -> FoundationSourceEvidence | None: ...


class NullFoundationSourceGate:
    """Current-main default: source is not Data Foundation-managed."""

    def get_source_materialization_evidence(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
    ) -> FoundationSourceEvidence | None:
        del tenant_id, workspace_id, source_binding_id
        return None


class InMemoryFoundationSourceGate:
    """Test double. Inject canonical DF evidence without importing PR #15."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], FoundationSourceEvidence] = {}

    def put(self, evidence: FoundationSourceEvidence) -> None:
        tenant_id = evidence.tenant_id or ""
        workspace_id = evidence.workspace_id or ""
        self._items[(tenant_id, workspace_id, evidence.source_binding_id)] = evidence

    def get_source_materialization_evidence(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
    ) -> FoundationSourceEvidence | None:
        return self._items.get((tenant_id, workspace_id, source_binding_id))

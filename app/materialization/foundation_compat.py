"""Compatibility seam for non-canonical unit fixtures.

Production runtime uses CanonicalFoundationSourceGate.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

FOUNDATION_SOURCE_READY = "FOUNDATION_SOURCE_READY"
FOUNDATION_SOURCE_NOT_READY = "FOUNDATION_SOURCE_NOT_READY"


class FoundationSourceAuthorityDenied(Exception):
    """Foreign or mismatched DF identity. Must be indistinguishable from not found."""


class FoundationLineageError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


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
    business_profile_snapshot_fingerprint: str | None = None
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
        source_identities: tuple[str, ...] = (),
        import_roles: tuple[str, ...] = (),
    ) -> FoundationSourceEvidence | None: ...


class NullFoundationSourceGate:
    """Explicit non-DF fixture. Not the production default."""

    def get_source_materialization_evidence(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
        source_identities: tuple[str, ...] = (),
        import_roles: tuple[str, ...] = (),
    ) -> FoundationSourceEvidence | None:
        del tenant_id, workspace_id, source_binding_id, source_identities, import_roles
        return None


class InMemoryFoundationSourceGate:
    """Test double for fixtures that inject FoundationSourceEvidence directly."""

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
        source_identities: tuple[str, ...] = (),
        import_roles: tuple[str, ...] = (),
    ) -> FoundationSourceEvidence | None:
        del source_identities, import_roles
        return self._items.get((tenant_id, workspace_id, source_binding_id))

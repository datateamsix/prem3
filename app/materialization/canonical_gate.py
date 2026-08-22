"""Canonical Data Foundation source gate. Tenant-qualifies source-ID lookups."""

from __future__ import annotations

from app.data_foundation.contracts import EvidenceRequirement, ResourceIdentity, SourceBinding
from app.data_foundation.enums import SourceFoundationStatus
from app.data_foundation.store import DataFoundationStore
from app.materialization.foundation_compat import (
    FOUNDATION_SOURCE_NOT_READY,
    FoundationLineageError,
    FoundationSourceAuthorityDenied,
    FoundationSourceEvidence,
)


class CanonicalFoundationSourceGate:
    """Production gate backed by the shared DataFoundationStore."""

    def __init__(self, store: DataFoundationStore) -> None:
        self._store = store

    def get_source_materialization_evidence(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
        source_identities: tuple[str, ...] = (),
        import_roles: tuple[str, ...] = (),
    ) -> FoundationSourceEvidence | None:
        binding = self._resolve_binding(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_binding_id=source_binding_id,
            source_identities=source_identities,
        )
        if binding is None:
            return None
        self._assert_binding_authority(
            binding, tenant_id=tenant_id, workspace_id=workspace_id
        )
        known = _resource_identities(binding.resource)
        if source_identities and known and not known.intersection(source_identities):
            raise FoundationLineageError(
                "Import Contract source identity does not match SourceBinding.resource."
            )
        requirement = self._requirement_for(binding)
        if requirement is not None and import_roles:
            self._assert_role_lineage(requirement, import_roles)
        receipt = self._store.get_current_source_receipt(binding.source_id)
        if receipt is None:
            return self._evidence(
                binding=binding,
                requirement=requirement,
                receipt_id="",
                status_code=FOUNDATION_SOURCE_NOT_READY,
                governance_import_ready=False,
                premodel_review_remaining=False,
                premodel_review_findings=(),
            )
        if receipt.tenant_id != tenant_id or receipt.workspace_id != workspace_id:
            raise FoundationSourceAuthorityDenied()
        if binding.source_id not in receipt.source_ids:
            raise FoundationSourceAuthorityDenied()
        status = (
            receipt.status_code.value
            if isinstance(receipt.status_code, SourceFoundationStatus)
            else str(receipt.status_code)
        )
        return self._evidence(
            binding=binding,
            requirement=requirement,
            receipt_id=receipt.receipt_id,
            status_code=status,
            governance_import_ready=receipt.governance_import_ready,
            premodel_review_remaining=receipt.premodel_review_remaining,
            premodel_review_findings=receipt.premodel_review_findings,
        )

    def _resolve_binding(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_binding_id: str,
        source_identities: tuple[str, ...],
    ) -> SourceBinding | None:
        if source_binding_id:
            found = self._store.get_binding(source_binding_id)
            if found is not None:
                return found
        if not source_identities:
            return None
        matches = [
            item
            for item in self._store.list_bindings(
                tenant_id=tenant_id, workspace_id=workspace_id
            )
            if _resource_matches(item.resource, source_identities)
        ]
        if len(matches) > 1:
            raise FoundationLineageError(
                "Multiple Data Foundation bindings match the Import Contract source."
            )
        return matches[0] if matches else None

    def _assert_binding_authority(
        self, binding: SourceBinding, *, tenant_id: str, workspace_id: str
    ) -> None:
        if binding.tenant_id != tenant_id or binding.workspace_id != workspace_id:
            raise FoundationSourceAuthorityDenied()

    def _requirement_for(self, binding: SourceBinding) -> EvidenceRequirement | None:
        if not binding.requirement_id:
            return None
        requirements = self._store.get_requirements(
            tenant_id=binding.tenant_id, workspace_id=binding.workspace_id
        )
        if requirements is None:
            raise FoundationLineageError(
                "SourceBinding.requirement_id has no EvidenceRequirementSet in scope."
            )
        for item in requirements.requirements:
            if item.requirement_id == binding.requirement_id:
                return item
        raise FoundationLineageError(
            "SourceBinding.requirement_id is not present in the scoped EvidenceRequirementSet."
        )

    def _assert_role_lineage(
        self, requirement: EvidenceRequirement, import_roles: tuple[str, ...]
    ) -> None:
        expected = {
            _normalize_role(requirement.business_role),
            _normalize_role(str(requirement.requirement_type)),
        }
        claimed = {_normalize_role(role) for role in import_roles if role}
        if not claimed:
            return
        if not any(role in expected for role in claimed):
            raise FoundationLineageError(
                "Import Contract role is incompatible with EvidenceRequirement.business_role."
            )

    def _evidence(
        self,
        *,
        binding: SourceBinding,
        requirement: EvidenceRequirement | None,
        receipt_id: str,
        status_code: str,
        governance_import_ready: bool,
        premodel_review_remaining: bool,
        premodel_review_findings: tuple[str, ...],
    ) -> FoundationSourceEvidence:
        requirements = self._store.get_requirements(
            tenant_id=binding.tenant_id, workspace_id=binding.workspace_id
        )
        snapshot_id = None if requirements is None else requirements.snapshot_id
        snapshot_fingerprint = (
            None if requirements is None else requirements.snapshot_fingerprint
        )
        requirement_ids = []
        if binding.requirement_id:
            requirement_ids.append(binding.requirement_id)
        return FoundationSourceEvidence(
            source_binding_id=binding.source_id,
            source_foundation_receipt_id=receipt_id or "missing",
            status_code=status_code or FOUNDATION_SOURCE_NOT_READY,
            governance_import_ready=governance_import_ready,
            premodel_review_remaining=premodel_review_remaining,
            premodel_review_findings=list(premodel_review_findings),
            resource_identity=_resource_key(binding.resource),
            tenant_id=binding.tenant_id,
            workspace_id=binding.workspace_id,
            business_profile_snapshot_id=snapshot_id,
            business_profile_snapshot_fingerprint=snapshot_fingerprint,
            evidence_requirement_ids=requirement_ids,
            provider=binding.provider_id,
            business_role=None if requirement is None else requirement.business_role,
            history=binding.historical_role,
            grain=binding.contract.grain,
        )


def _resource_key(resource: ResourceIdentity) -> str | None:
    identities = _resource_identities(resource)
    return next(iter(identities), None)


def _resource_identities(resource: ResourceIdentity) -> set[str]:
    identities: set[str] = set()
    if resource.drive_file_id:
        identities.add(resource.drive_file_id)
    if resource.logical_path:
        identities.add(resource.logical_path)
    if resource.project_id and resource.dataset_id and resource.table_id:
        identities.add(f"{resource.project_id}.{resource.dataset_id}.{resource.table_id}")
    return identities


def _resource_matches(resource: ResourceIdentity, source_identities: tuple[str, ...]) -> bool:
    known = _resource_identities(resource)
    return bool(known.intersection(source_identities))


def _normalize_role(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")

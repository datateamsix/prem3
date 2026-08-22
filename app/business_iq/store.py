"""Business IQ persistence port. Uses the existing control plane, not a second one."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.business_iq.contracts import (
    BusinessClarificationRequest,
    BusinessContextReadyReceipt,
    BusinessIntelligenceBrief,
    BusinessProfile,
    BusinessProfileSnapshot,
    BusinessProfileUpdateProposal,
    BusinessProfileVersion,
)


@runtime_checkable
class BusinessIqStore(Protocol):
    def put_profile(self, value: BusinessProfile) -> BusinessProfile: ...

    def get_profile(self, *, tenant_id: str, workspace_id: str) -> BusinessProfile | None: ...

    def put_version(self, value: BusinessProfileVersion) -> BusinessProfileVersion: ...

    def list_versions(self, *, profile_id: str) -> list[BusinessProfileVersion]: ...

    def put_snapshot(self, value: BusinessProfileSnapshot) -> BusinessProfileSnapshot: ...

    def get_snapshot(self, snapshot_id: str) -> BusinessProfileSnapshot | None: ...

    def put_brief(self, value: BusinessIntelligenceBrief) -> BusinessIntelligenceBrief: ...

    def get_brief(self, *, workspace_id: str) -> BusinessIntelligenceBrief | None: ...

    def put_proposal(self, value: BusinessProfileUpdateProposal) -> BusinessProfileUpdateProposal: ...

    def get_proposal(self, proposal_id: str) -> BusinessProfileUpdateProposal | None: ...

    def list_proposals(self, *, workspace_id: str) -> list[BusinessProfileUpdateProposal]: ...

    def put_clarification(
        self, value: BusinessClarificationRequest
    ) -> BusinessClarificationRequest: ...

    def get_clarification(self, clarification_id: str) -> BusinessClarificationRequest | None: ...

    def put_ready_receipt(
        self, value: BusinessContextReadyReceipt
    ) -> BusinessContextReadyReceipt: ...

    def get_ready_receipt(
        self, *, tenant_id: str, workspace_id: str
    ) -> BusinessContextReadyReceipt | None: ...


class InMemoryBusinessIqStore:
    """Test/local store. Cloud persistence uses the same port on the control plane."""

    def __init__(self) -> None:
        self.profiles: dict[tuple[str, str], BusinessProfile] = {}
        self.versions: dict[str, list[BusinessProfileVersion]] = {}
        self.snapshots: dict[str, BusinessProfileSnapshot] = {}
        self.briefs: dict[str, BusinessIntelligenceBrief] = {}
        self.proposals: dict[str, BusinessProfileUpdateProposal] = {}
        self.clarifications: dict[str, BusinessClarificationRequest] = {}
        self.ready: dict[tuple[str, str], BusinessContextReadyReceipt] = {}

    def put_profile(self, value: BusinessProfile) -> BusinessProfile:
        self.profiles[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_profile(self, *, tenant_id: str, workspace_id: str) -> BusinessProfile | None:
        return self.profiles.get((tenant_id, workspace_id))

    def put_version(self, value: BusinessProfileVersion) -> BusinessProfileVersion:
        self.versions.setdefault(value.profile_id, []).append(value)
        return value

    def list_versions(self, *, profile_id: str) -> list[BusinessProfileVersion]:
        return list(self.versions.get(profile_id, []))

    def put_snapshot(self, value: BusinessProfileSnapshot) -> BusinessProfileSnapshot:
        self.snapshots[value.snapshot_id] = value
        return value

    def get_snapshot(self, snapshot_id: str) -> BusinessProfileSnapshot | None:
        return self.snapshots.get(snapshot_id)

    def put_brief(self, value: BusinessIntelligenceBrief) -> BusinessIntelligenceBrief:
        self.briefs[value.workspace_id] = value
        return value

    def get_brief(self, *, workspace_id: str) -> BusinessIntelligenceBrief | None:
        return self.briefs.get(workspace_id)

    def put_proposal(self, value: BusinessProfileUpdateProposal) -> BusinessProfileUpdateProposal:
        self.proposals[value.proposal_id] = value
        return value

    def get_proposal(self, proposal_id: str) -> BusinessProfileUpdateProposal | None:
        return self.proposals.get(proposal_id)

    def list_proposals(self, *, workspace_id: str) -> list[BusinessProfileUpdateProposal]:
        return [item for item in self.proposals.values() if item.workspace_id == workspace_id]

    def put_clarification(
        self, value: BusinessClarificationRequest
    ) -> BusinessClarificationRequest:
        self.clarifications[value.clarification_id] = value
        return value

    def get_clarification(self, clarification_id: str) -> BusinessClarificationRequest | None:
        return self.clarifications.get(clarification_id)

    def put_ready_receipt(self, value: BusinessContextReadyReceipt) -> BusinessContextReadyReceipt:
        self.ready[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_ready_receipt(
        self, *, tenant_id: str, workspace_id: str
    ) -> BusinessContextReadyReceipt | None:
        return self.ready.get((tenant_id, workspace_id))

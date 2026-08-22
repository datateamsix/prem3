"""Production Firestore backing for Business IQ. InMemory remains CI/local."""

from __future__ import annotations

from typing import Any

from app.business_iq.contracts import (
    BusinessClarificationRequest,
    BusinessContextReadyReceipt,
    BusinessIntelligenceBrief,
    BusinessProfile,
    BusinessProfileSnapshot,
    BusinessProfileUpdateProposal,
    BusinessProfileVersion,
)
from app.control_plane.serialization import document_to_model, model_to_document

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_PROFILE = "business_profiles"
COL_VERSIONS = "business_profile_versions"
COL_SNAPSHOTS = "business_profile_snapshots"
COL_BRIEFS = "business_briefs"
COL_PROPOSALS = "business_proposals"
COL_CLARIFICATIONS = "business_clarifications"
COL_READY = "business_ready"
COL_INDEX = "business_iq_index"


class FirestoreBusinessIqStore:
    def __init__(self, client: Any) -> None:
        self._db = client

    def _workspace(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COLLECTION_TENANTS)
            .document(tenant_id)
            .collection(COLLECTION_WORKSPACES)
            .document(workspace_id)
        )

    def _index(self, kind: str, key: str, tenant_id: str, workspace_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"{kind}__{key}").set(
            {"tenant_id": tenant_id, "workspace_id": workspace_id}
        )

    def _lookup(self, kind: str, key: str) -> tuple[str, str] | None:
        snap = self._db.collection(COL_INDEX).document(f"{kind}__{key}").get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return str(data["tenant_id"]), str(data["workspace_id"])

    def _put(self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model: Any) -> None:
        self._workspace(tenant_id, workspace_id).collection(collection).document(doc_id).set(
            model_to_document(model)
        )

    def _get(self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model_type: Any):
        snap = self._workspace(tenant_id, workspace_id).collection(collection).document(doc_id).get()
        if not snap.exists:
            return None
        return document_to_model(model_type, snap.to_dict())

    def put_profile(self, value: BusinessProfile) -> BusinessProfile:
        self._put(value.tenant_id, value.workspace_id, COL_PROFILE, "current", value)
        self._index("profile", value.profile_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_profile(self, *, tenant_id: str, workspace_id: str) -> BusinessProfile | None:
        return self._get(tenant_id, workspace_id, COL_PROFILE, "current", BusinessProfile)

    def put_version(self, value: BusinessProfileVersion) -> BusinessProfileVersion:
        loc = self._lookup("profile", value.profile_id)
        if loc is None:
            raise KeyError("Business profile index is missing.")
        self._put(loc[0], loc[1], COL_VERSIONS, str(value.version), value)
        return value

    def list_versions(self, *, profile_id: str) -> list[BusinessProfileVersion]:
        loc = self._lookup("profile", profile_id)
        if loc is None:
            return []
        rows = []
        for snap in self._workspace(loc[0], loc[1]).collection(COL_VERSIONS).stream():
            rows.append(document_to_model(BusinessProfileVersion, snap.to_dict()))
        return sorted(rows, key=lambda item: item.version)

    def put_snapshot(self, value: BusinessProfileSnapshot) -> BusinessProfileSnapshot:
        self._put(value.tenant_id, value.workspace_id, COL_SNAPSHOTS, value.snapshot_id, value)
        self._index("snapshot", value.snapshot_id, value.tenant_id, value.workspace_id)
        self._index("profile", value.profile_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_snapshot(self, snapshot_id: str) -> BusinessProfileSnapshot | None:
        loc = self._lookup("snapshot", snapshot_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], COL_SNAPSHOTS, snapshot_id, BusinessProfileSnapshot)

    def put_brief(self, value: BusinessIntelligenceBrief) -> BusinessIntelligenceBrief:
        self._put(value.tenant_id, value.workspace_id, COL_BRIEFS, "current", value)
        return value

    def get_brief(self, *, workspace_id: str) -> BusinessIntelligenceBrief | None:
        snap = self._db.collection(COL_INDEX).document(f"workspace__{workspace_id}").get()
        if snap.exists:
            data = snap.to_dict() or {}
            return self._get(
                str(data["tenant_id"]), workspace_id, COL_BRIEFS, "current", BusinessIntelligenceBrief
            )
        profile_hits = []
        for item in self._db.collection(COL_INDEX).stream():
            payload = item.to_dict() or {}
            if payload.get("workspace_id") == workspace_id and str(item.id).startswith("profile__"):
                profile_hits.append(payload)
        if not profile_hits:
            return None
        return self._get(
            str(profile_hits[0]["tenant_id"]),
            workspace_id,
            COL_BRIEFS,
            "current",
            BusinessIntelligenceBrief,
        )

    def put_proposal(self, value: BusinessProfileUpdateProposal) -> BusinessProfileUpdateProposal:
        self._put(value.tenant_id, value.workspace_id, COL_PROPOSALS, value.proposal_id, value)
        self._index("proposal", value.proposal_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_proposal(self, proposal_id: str) -> BusinessProfileUpdateProposal | None:
        loc = self._lookup("proposal", proposal_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], COL_PROPOSALS, proposal_id, BusinessProfileUpdateProposal)

    def list_proposals(self, *, workspace_id: str) -> list[BusinessProfileUpdateProposal]:
        loc = self._lookup("workspace", workspace_id)
        if loc is None:
            return []
        rows = []
        for snap in self._workspace(loc[0], loc[1]).collection(COL_PROPOSALS).stream():
            rows.append(document_to_model(BusinessProfileUpdateProposal, snap.to_dict()))
        return rows

    def put_clarification(self, value: BusinessClarificationRequest) -> BusinessClarificationRequest:
        self._put(value.tenant_id, value.workspace_id, COL_CLARIFICATIONS, value.clarification_id, value)
        self._index("clarification", value.clarification_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_clarification(self, clarification_id: str) -> BusinessClarificationRequest | None:
        loc = self._lookup("clarification", clarification_id)
        if loc is None:
            return None
        return self._get(
            loc[0], loc[1], COL_CLARIFICATIONS, clarification_id, BusinessClarificationRequest
        )

    def put_ready_receipt(self, value: BusinessContextReadyReceipt) -> BusinessContextReadyReceipt:
        self._put(value.tenant_id, value.workspace_id, COL_READY, "current", value)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_ready_receipt(
        self, *, tenant_id: str, workspace_id: str
    ) -> BusinessContextReadyReceipt | None:
        return self._get(tenant_id, workspace_id, COL_READY, "current", BusinessContextReadyReceipt)

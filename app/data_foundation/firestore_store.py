"""Production Firestore backing for Data Foundation. InMemory remains CI/local."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
from app.data_foundation.contracts import (
    CanonicalPreview,
    CoverageAssessment,
    DataIntelligenceBrief,
    CrossSourceAlignmentAssessment,
    DataFoundationReadyReceipt,
    DataPreview,
    DiscoveryHints,
    DriveFileRecord,
    DriveFoundationLayout,
    DriveImportReceipt,
    EvidenceRequirementSet,
    FoundationApproval,
    FoundationPlan,
    FoundationProvisioningReceipt,
    MeasurementCycle,
    PhysicalMetadata,
    ProvisioningRun,
    SourceAssessment,
    SourceAssessmentReceipt,
    SourceBinding,
    SourceCandidate,
    SourceContinuityPlan,
    SourceCoverageInventory,
    SourceFoundationReceipt,
    SourceScope,
    TransformationPlan,
    TransformationPreview,
    TransformationReceipt,
    UserDecision,
)

COL_TENANTS = "tenants"
COL_WORKSPACES = "workspaces"
COL_INDEX = "data_foundation_index"


class FirestoreDataFoundationStore:
    """Durable production store for cycles, bindings, plans, findings, and receipts."""

    def __init__(self, client: Any) -> None:
        self._db = client

    def _ws(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COL_TENANTS)
            .document(tenant_id)
            .collection(COL_WORKSPACES)
            .document(workspace_id)
        )

    def _index(self, kind: str, key: str, tenant_id: str, workspace_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"{kind}__{key}").set(
            {"tenant_id": tenant_id, "workspace_id": workspace_id, "kind": kind}
        )

    def _lookup(self, kind: str, key: str) -> tuple[str, str] | None:
        snap = self._db.collection(COL_INDEX).document(f"{kind}__{key}").get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return str(data["tenant_id"]), str(data["workspace_id"])

    def _put(self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model: Any) -> None:
        self._ws(tenant_id, workspace_id).collection(collection).document(doc_id).set(
            model_to_document(model)
        )

    def _get(self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model_type: Any):
        snap = self._ws(tenant_id, workspace_id).collection(collection).document(doc_id).get()
        if not snap.exists:
            return None
        return document_to_model(model_type, snap.to_dict())

    def _stream(self, tenant_id: str, workspace_id: str, collection: str, model_type: Any) -> list:
        return [
            document_to_model(model_type, snap.to_dict())
            for snap in self._ws(tenant_id, workspace_id).collection(collection).stream()
        ]

    def _get_indexed(self, kind: str, key: str, collection: str, model_type: Any):
        loc = self._lookup(kind, key)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], collection, key, model_type)

    def put_requirements(self, value: EvidenceRequirementSet) -> EvidenceRequirementSet:
        self._put(value.tenant_id, value.workspace_id, "df_requirements", "current", value)
        return value

    def get_requirements(self, *, tenant_id: str, workspace_id: str) -> EvidenceRequirementSet | None:
        return self._get(tenant_id, workspace_id, "df_requirements", "current", EvidenceRequirementSet)

    def put_layout(self, value: DriveFoundationLayout) -> DriveFoundationLayout:
        self._put(value.tenant_id, value.workspace_id, "df_layouts", "current", value)
        return value

    def get_layout(self, *, tenant_id: str, workspace_id: str) -> DriveFoundationLayout | None:
        return self._get(tenant_id, workspace_id, "df_layouts", "current", DriveFoundationLayout)

    def put_inventory(self, value: SourceCoverageInventory) -> SourceCoverageInventory:
        self._put(value.tenant_id, value.workspace_id, "df_inventories", "current", value)
        return value

    def get_inventory(self, *, tenant_id: str, workspace_id: str) -> SourceCoverageInventory | None:
        return self._get(tenant_id, workspace_id, "df_inventories", "current", SourceCoverageInventory)

    def put_candidate(self, value: SourceCandidate) -> SourceCandidate:
        self._put(value.tenant_id, value.workspace_id, "df_candidates", value.candidate_id, value)
        self._index("candidate", value.candidate_id, value.tenant_id, value.workspace_id)
        return value

    def get_candidate(self, candidate_id: str) -> SourceCandidate | None:
        return self._get_indexed("candidate", candidate_id, "df_candidates", SourceCandidate)

    def put_binding(self, value: SourceBinding) -> SourceBinding:
        self._put(value.tenant_id, value.workspace_id, "df_bindings", value.source_id, value)
        self._index("binding", value.source_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_binding(self, source_id: str) -> SourceBinding | None:
        return self._get_indexed("binding", source_id, "df_bindings", SourceBinding)

    def list_bindings(self, *, tenant_id: str, workspace_id: str) -> list[SourceBinding]:
        return self._stream(tenant_id, workspace_id, "df_bindings", SourceBinding)

    def put_assessment(self, value: SourceAssessment) -> SourceAssessment:
        binding = self.get_binding(value.source_id)
        if binding is None:
            raise KeyError("Assessment requires a bound source.")
        self._put(binding.tenant_id, binding.workspace_id, "df_assessments", value.source_id, value)
        self._index("assessment", value.source_id, binding.tenant_id, binding.workspace_id)
        return value

    def get_assessment(self, source_id: str) -> SourceAssessment | None:
        return self._get_indexed("assessment", source_id, "df_assessments", SourceAssessment)

    def put_alignment(self, value: CrossSourceAlignmentAssessment) -> CrossSourceAlignmentAssessment:
        loc = self._lookup("workspace", value.workspace_id)
        if loc is None:
            raise KeyError("Workspace index is missing for alignment.")
        self._put(loc[0], value.workspace_id, "df_alignments", "current", value)
        return value

    def get_alignment(self, workspace_id: str) -> CrossSourceAlignmentAssessment | None:
        loc = self._lookup("workspace", workspace_id)
        if loc is None:
            return None
        return self._get(loc[0], workspace_id, "df_alignments", "current", CrossSourceAlignmentAssessment)

    def put_transformation_plan(self, value: TransformationPlan) -> TransformationPlan:
        binding = self.get_binding(value.source_id)
        if binding is None:
            raise KeyError("Transform plan requires a bound source.")
        self._put(binding.tenant_id, binding.workspace_id, "df_transform_plans", value.plan_id, value)
        self._index("tplan", value.plan_id, binding.tenant_id, binding.workspace_id)
        return value

    def get_transformation_plan(self, plan_id: str) -> TransformationPlan | None:
        return self._get_indexed("tplan", plan_id, "df_transform_plans", TransformationPlan)

    def put_preview(self, value: TransformationPreview) -> TransformationPreview:
        plan = self.get_transformation_plan(value.plan_id)
        if plan is None:
            raise KeyError("Preview requires a transformation plan.")
        loc = self._lookup("tplan", value.plan_id)
        if loc is None:
            raise KeyError("Preview plan index is missing.")
        self._put(loc[0], loc[1], "df_previews", value.preview_id, value)
        self._index("preview", value.preview_id, loc[0], loc[1])
        return value

    def get_preview(self, preview_id: str) -> TransformationPreview | None:
        return self._get_indexed("preview", preview_id, "df_previews", TransformationPreview)

    def put_foundation_plan(self, value: FoundationPlan) -> FoundationPlan:
        self._put(value.tenant_id, value.workspace_id, "df_foundation_plans", value.plan_id, value)
        self._index("fplan", value.plan_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_foundation_plan(self, plan_id: str) -> FoundationPlan | None:
        return self._get_indexed("fplan", plan_id, "df_foundation_plans", FoundationPlan)

    def put_approval(self, value: FoundationApproval) -> FoundationApproval:
        self._put(value.tenant_id, value.workspace_id, "df_approvals", value.plan_id, value)
        self._index("approval", value.plan_id, value.tenant_id, value.workspace_id)
        return value

    def get_approval_for_plan(self, plan_id: str) -> FoundationApproval | None:
        return self._get_indexed("approval", plan_id, "df_approvals", FoundationApproval)

    def put_decision(self, value: UserDecision) -> UserDecision:
        binding = self.get_binding(value.source_id)
        if binding is None:
            raise KeyError("Decision requires a bound source.")
        self._put(
            binding.tenant_id,
            binding.workspace_id,
            "df_decisions",
            f"{value.source_id}__{value.decision_id}",
            value,
        )
        return value

    def list_decisions(self, source_id: str) -> list[UserDecision]:
        loc = self._lookup("binding", source_id)
        if loc is None:
            return []
        return [
            item
            for item in self._stream(loc[0], loc[1], "df_decisions", UserDecision)
            if item.source_id == source_id
        ]

    def put_file(self, value: DriveFileRecord) -> DriveFileRecord:
        self._db.collection("df_drive_files").document(value.drive_file_id).set(model_to_document(value))
        return value

    def get_file(self, drive_file_id: str) -> DriveFileRecord | None:
        snap = self._db.collection("df_drive_files").document(drive_file_id).get()
        if not snap.exists:
            return None
        return document_to_model(DriveFileRecord, snap.to_dict())

    def list_files(self, *, tenant_id: str, workspace_id: str) -> list[DriveFileRecord]:
        del tenant_id, workspace_id
        return [
            document_to_model(DriveFileRecord, snap.to_dict())
            for snap in self._db.collection("df_drive_files").stream()
        ]

    def put_source_receipt(self, value: SourceFoundationReceipt) -> SourceFoundationReceipt:
        key = value.source_ids[0] if value.source_ids else value.receipt_id
        self._put(value.tenant_id, value.workspace_id, "df_source_receipts", key, value)
        self._put(value.tenant_id, value.workspace_id, "df_receipts", value.receipt_id, value)
        self._index("source_receipt", key, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_current_source_receipt(self, source_id: str) -> SourceFoundationReceipt | None:
        return self._get_indexed("source_receipt", source_id, "df_source_receipts", SourceFoundationReceipt)

    def put_foundation_receipt(self, value: DataFoundationReadyReceipt) -> DataFoundationReadyReceipt:
        self._put(value.tenant_id, value.workspace_id, "df_foundation_receipts", "current", value)
        self._put(value.tenant_id, value.workspace_id, "df_receipts", value.receipt_id, value)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_current_foundation_receipt(
        self, *, tenant_id: str, workspace_id: str
    ) -> DataFoundationReadyReceipt | None:
        return self._get(tenant_id, workspace_id, "df_foundation_receipts", "current", DataFoundationReadyReceipt)

    def put_assessment_receipt(self, value: SourceAssessmentReceipt) -> SourceAssessmentReceipt:
        self._put(value.tenant_id, value.workspace_id, "df_receipts", value.receipt_id, value)
        return value

    def put_transform_receipt(self, value: TransformationReceipt) -> TransformationReceipt:
        self._put(value.tenant_id, value.workspace_id, "df_receipts", value.receipt_id, value)
        self._index(
            "transform",
            f"{value.source_ids[0]}__{value.plan_id}__{value.input_fingerprints.get('source', '')}",
            value.tenant_id,
            value.workspace_id,
        )
        self._put(
            value.tenant_id,
            value.workspace_id,
            "df_transform_receipts",
            f"{value.source_ids[0]}__{value.plan_id}",
            value,
        )
        return value

    def get_transform_receipt(
        self, *, source_id: str, plan_id: str, source_fingerprint: str
    ) -> TransformationReceipt | None:
        loc = self._lookup("binding", source_id) or self._lookup("workspace", source_id)
        if loc is None:
            # Try transform index created at put time.
            loc = self._lookup("transform", f"{source_id}__{plan_id}__{source_fingerprint}")
        if loc is None:
            return None
        found = self._get(
            loc[0], loc[1], "df_transform_receipts", f"{source_id}__{plan_id}", TransformationReceipt
        )
        if (
            found is None
            or found.input_fingerprints.get("source") != source_fingerprint
            or found.status != "APPLIED"
        ):
            return None
        return found

    def put_drive_import_receipt(self, value: DriveImportReceipt) -> DriveImportReceipt:
        self._put(value.tenant_id, value.workspace_id, "df_receipts", value.receipt_id, value)
        return value

    def put_provisioning_receipt(
        self, value: FoundationProvisioningReceipt
    ) -> FoundationProvisioningReceipt:
        self._put(value.tenant_id, value.workspace_id, "df_receipts", value.receipt_id, value)
        return value

    def put_provisioning_run(self, value: ProvisioningRun) -> ProvisioningRun:
        loc = self._lookup("fplan", value.plan_id)
        if loc is None:
            raise KeyError("Provisioning run requires a foundation plan.")
        self._put(loc[0], loc[1], "df_provisioning_runs", value.run_id, value)
        return value

    def list_receipts(self, *, tenant_id: str, workspace_id: str) -> list[object]:
        rows = []
        for snap in self._ws(tenant_id, workspace_id).collection("df_receipts").stream():
            data = snap.to_dict() or {}
            for model_type in (
                SourceAssessmentReceipt,
                TransformationReceipt,
                DriveImportReceipt,
                FoundationProvisioningReceipt,
                SourceFoundationReceipt,
                DataFoundationReadyReceipt,
            ):
                try:
                    rows.append(document_to_model(model_type, data))
                    break
                except Exception:
                    continue
        return rows

    def put_cycle(self, value: MeasurementCycle) -> MeasurementCycle:
        self._put(value.tenant_id, value.workspace_id, "df_cycles", value.cycle_id, value)
        self._index("cycle", value.cycle_id, value.tenant_id, value.workspace_id)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_cycle(self, cycle_id: str) -> MeasurementCycle | None:
        return self._get_indexed("cycle", cycle_id, "df_cycles", MeasurementCycle)

    def list_cycles(self, *, tenant_id: str, workspace_id: str) -> list[MeasurementCycle]:
        return self._stream(tenant_id, workspace_id, "df_cycles", MeasurementCycle)

    def put_coverage(self, value: CoverageAssessment) -> CoverageAssessment:
        self._put(value.tenant_id, value.workspace_id, "df_coverage", value.cycle_id, value)
        return value

    def get_coverage(self, cycle_id: str) -> CoverageAssessment | None:
        loc = self._lookup("cycle", cycle_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "df_coverage", cycle_id, CoverageAssessment)

    def put_hints(self, value: DiscoveryHints) -> DiscoveryHints:
        self._put(value.tenant_id, value.workspace_id, "df_hints", "current", value)
        return value

    def get_hints(self, *, tenant_id: str, workspace_id: str) -> DiscoveryHints | None:
        return self._get(tenant_id, workspace_id, "df_hints", "current", DiscoveryHints)

    def put_data_preview(self, value: DataPreview) -> DataPreview:
        loc = self._lookup("binding", value.source_id or "") if value.source_id else None
        if loc is None:
            raise KeyError("Data preview requires a bound source.")
        self._put(loc[0], loc[1], "df_data_previews", value.preview_id, value)
        return value

    def put_canonical_preview(self, value: CanonicalPreview) -> CanonicalPreview:
        self._db.collection("df_canonical_previews").document(value.output_resource).set(
            model_to_document(value)
        )
        return value

    def get_canonical_preview(self, *, workspace_id: str) -> CanonicalPreview | None:
        del workspace_id
        last = None
        for snap in self._db.collection("df_canonical_previews").stream():
            last = document_to_model(CanonicalPreview, snap.to_dict())
        return last

    def put_intelligence_brief(self, value: DataIntelligenceBrief) -> DataIntelligenceBrief:
        self._put(value.tenant_id, value.workspace_id, "df_intelligence_briefs", "current", value)
        self._index("workspace", value.workspace_id, value.tenant_id, value.workspace_id)
        return value

    def get_intelligence_brief(
        self, *, tenant_id: str, workspace_id: str
    ) -> DataIntelligenceBrief | None:
        return self._get(tenant_id, workspace_id, "df_intelligence_briefs", "current", DataIntelligenceBrief)

    def put_scope(self, source_id: str, value: SourceScope) -> SourceScope:
        loc = self._lookup("binding", source_id)
        if loc is None:
            raise KeyError("Scope requires a bound source.")
        self._put(loc[0], loc[1], "df_scopes", source_id, value)
        self._index("scope", source_id, loc[0], loc[1])
        return value

    def get_scope(self, source_id: str) -> SourceScope | None:
        return self._get_indexed("scope", source_id, "df_scopes", SourceScope)

    def put_physical(self, source_id: str, value: PhysicalMetadata) -> PhysicalMetadata:
        loc = self._lookup("binding", source_id)
        if loc is None:
            raise KeyError("Physical metadata requires a bound source.")
        self._put(loc[0], loc[1], "df_physical", source_id, value)
        self._index("physical", source_id, loc[0], loc[1])
        return value

    def get_physical(self, source_id: str) -> PhysicalMetadata | None:
        return self._get_indexed("physical", source_id, "df_physical", PhysicalMetadata)

    def put_transition(self, value: SourceContinuityPlan) -> SourceContinuityPlan:
        workspace_id = value.workspace_id or "unknown"
        loc = self._lookup("workspace", workspace_id)
        if loc is None:
            raise KeyError("Transition requires a workspace index.")
        doc_id = f"{value.historical_source_id}__{value.ongoing_source_id}__{value.cutoff}"
        self._put(loc[0], workspace_id, "df_transitions", doc_id, value)
        return value

    def list_transitions(self, *, workspace_id: str) -> list[SourceContinuityPlan]:
        loc = self._lookup("workspace", workspace_id)
        if loc is None:
            return []
        return self._stream(loc[0], workspace_id, "df_transitions", SourceContinuityPlan)

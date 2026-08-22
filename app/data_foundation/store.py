"""Durable Data Foundation store. Process memory is not a production truth."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


@runtime_checkable
class DataFoundationStore(Protocol):
    def put_requirements(self, value: EvidenceRequirementSet) -> EvidenceRequirementSet: ...

    def get_requirements(
        self, *, tenant_id: str, workspace_id: str
    ) -> EvidenceRequirementSet | None: ...

    def put_layout(self, value: DriveFoundationLayout) -> DriveFoundationLayout: ...

    def get_layout(self, *, tenant_id: str, workspace_id: str) -> DriveFoundationLayout | None: ...

    def put_inventory(self, value: SourceCoverageInventory) -> SourceCoverageInventory: ...

    def get_inventory(
        self, *, tenant_id: str, workspace_id: str
    ) -> SourceCoverageInventory | None: ...

    def put_candidate(self, value: SourceCandidate) -> SourceCandidate: ...

    def get_candidate(self, candidate_id: str) -> SourceCandidate | None: ...

    def put_binding(self, value: SourceBinding) -> SourceBinding: ...

    def get_binding(self, source_id: str) -> SourceBinding | None: ...

    def list_bindings(self, *, tenant_id: str, workspace_id: str) -> list[SourceBinding]: ...

    def put_assessment(self, value: SourceAssessment) -> SourceAssessment: ...

    def get_assessment(self, source_id: str) -> SourceAssessment | None: ...

    def put_alignment(
        self, value: CrossSourceAlignmentAssessment
    ) -> CrossSourceAlignmentAssessment: ...

    def get_alignment(self, workspace_id: str) -> CrossSourceAlignmentAssessment | None: ...

    def put_transformation_plan(self, value: TransformationPlan) -> TransformationPlan: ...

    def get_transformation_plan(self, plan_id: str) -> TransformationPlan | None: ...

    def put_preview(self, value: TransformationPreview) -> TransformationPreview: ...

    def get_preview(self, preview_id: str) -> TransformationPreview | None: ...

    def put_foundation_plan(self, value: FoundationPlan) -> FoundationPlan: ...

    def get_foundation_plan(self, plan_id: str) -> FoundationPlan | None: ...

    def put_approval(self, value: FoundationApproval) -> FoundationApproval: ...

    def get_approval_for_plan(self, plan_id: str) -> FoundationApproval | None: ...

    def put_decision(self, value: UserDecision) -> UserDecision: ...

    def list_decisions(self, source_id: str) -> list[UserDecision]: ...

    def put_file(self, value: DriveFileRecord) -> DriveFileRecord: ...

    def get_file(self, drive_file_id: str) -> DriveFileRecord | None: ...

    def list_files(self, *, tenant_id: str, workspace_id: str) -> list[DriveFileRecord]: ...

    def put_source_receipt(self, value: SourceFoundationReceipt) -> SourceFoundationReceipt: ...

    def get_current_source_receipt(self, source_id: str) -> SourceFoundationReceipt | None: ...

    def put_foundation_receipt(
        self, value: DataFoundationReadyReceipt
    ) -> DataFoundationReadyReceipt: ...

    def get_current_foundation_receipt(
        self, *, tenant_id: str, workspace_id: str
    ) -> DataFoundationReadyReceipt | None: ...

    def put_assessment_receipt(self, value: SourceAssessmentReceipt) -> SourceAssessmentReceipt: ...

    def put_transform_receipt(self, value: TransformationReceipt) -> TransformationReceipt: ...

    def get_transform_receipt(
        self, *, source_id: str, plan_id: str, source_fingerprint: str
    ) -> TransformationReceipt | None: ...

    def put_drive_import_receipt(self, value: DriveImportReceipt) -> DriveImportReceipt: ...

    def put_provisioning_receipt(
        self, value: FoundationProvisioningReceipt
    ) -> FoundationProvisioningReceipt: ...

    def put_provisioning_run(self, value: ProvisioningRun) -> ProvisioningRun: ...

    def list_receipts(self, *, tenant_id: str, workspace_id: str) -> list[object]: ...

    def put_cycle(self, value: MeasurementCycle) -> MeasurementCycle: ...

    def get_cycle(self, cycle_id: str) -> MeasurementCycle | None: ...

    def list_cycles(self, *, tenant_id: str, workspace_id: str) -> list[MeasurementCycle]: ...

    def put_coverage(self, value: CoverageAssessment) -> CoverageAssessment: ...

    def get_coverage(self, cycle_id: str) -> CoverageAssessment | None: ...

    def put_hints(self, value: DiscoveryHints) -> DiscoveryHints: ...

    def get_hints(self, *, tenant_id: str, workspace_id: str) -> DiscoveryHints | None: ...

    def put_data_preview(self, value: DataPreview) -> DataPreview: ...

    def put_canonical_preview(self, value: CanonicalPreview) -> CanonicalPreview: ...

    def get_canonical_preview(self, *, workspace_id: str) -> CanonicalPreview | None: ...

    def put_scope(self, source_id: str, value: SourceScope) -> SourceScope: ...

    def get_scope(self, source_id: str) -> SourceScope | None: ...

    def put_physical(self, source_id: str, value: PhysicalMetadata) -> PhysicalMetadata: ...

    def get_physical(self, source_id: str) -> PhysicalMetadata | None: ...

    def put_transition(self, value: SourceContinuityPlan) -> SourceContinuityPlan: ...

    def list_transitions(self, *, workspace_id: str) -> list[SourceContinuityPlan]: ...

    def put_intelligence_brief(self, value: DataIntelligenceBrief) -> DataIntelligenceBrief: ...

    def get_intelligence_brief(
        self, *, tenant_id: str, workspace_id: str
    ) -> DataIntelligenceBrief | None: ...


class InMemoryDataFoundationStore:
    """Test/local store. Cloud persistence uses the same port."""

    def __init__(self) -> None:
        self.requirements: dict[tuple[str, str], EvidenceRequirementSet] = {}
        self.layouts: dict[tuple[str, str], DriveFoundationLayout] = {}
        self.inventories: dict[tuple[str, str], SourceCoverageInventory] = {}
        self.candidates: dict[str, SourceCandidate] = {}
        self.bindings: dict[str, SourceBinding] = {}
        self.assessments: dict[str, SourceAssessment] = {}
        self.alignments: dict[str, CrossSourceAlignmentAssessment] = {}
        self.transform_plans: dict[str, TransformationPlan] = {}
        self.previews: dict[str, TransformationPreview] = {}
        self.foundation_plans: dict[str, FoundationPlan] = {}
        self.approvals: dict[str, FoundationApproval] = {}
        self.decisions: dict[str, list[UserDecision]] = {}
        self.files: dict[str, DriveFileRecord] = {}
        self.source_receipts: dict[str, list[SourceFoundationReceipt]] = {}
        self.foundation_receipts: dict[tuple[str, str], list[DataFoundationReadyReceipt]] = {}
        self.assessment_receipts: list[SourceAssessmentReceipt] = []
        self.transform_receipts: list[TransformationReceipt] = []
        self.drive_import_receipts: list[DriveImportReceipt] = []
        self.provisioning_receipts: list[FoundationProvisioningReceipt] = []
        self.provisioning_runs: dict[str, ProvisioningRun] = {}
        self.cycles: dict[str, MeasurementCycle] = {}
        self.coverage: dict[str, CoverageAssessment] = {}
        self.hints: dict[tuple[str, str], DiscoveryHints] = {}
        self.data_previews: dict[str, DataPreview] = {}
        self.canonical_previews: dict[str, CanonicalPreview] = {}
        self.scopes: dict[str, SourceScope] = {}
        self.physical: dict[str, PhysicalMetadata] = {}
        self.transitions: list[SourceContinuityPlan] = []
        self.intelligence_briefs: dict[tuple[str, str], DataIntelligenceBrief] = {}

    def put_requirements(self, value: EvidenceRequirementSet) -> EvidenceRequirementSet:
        self.requirements[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_requirements(
        self, *, tenant_id: str, workspace_id: str
    ) -> EvidenceRequirementSet | None:
        return self.requirements.get((tenant_id, workspace_id))

    def put_layout(self, value: DriveFoundationLayout) -> DriveFoundationLayout:
        self.layouts[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_layout(self, *, tenant_id: str, workspace_id: str) -> DriveFoundationLayout | None:
        return self.layouts.get((tenant_id, workspace_id))

    def put_inventory(self, value: SourceCoverageInventory) -> SourceCoverageInventory:
        self.inventories[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_inventory(self, *, tenant_id: str, workspace_id: str) -> SourceCoverageInventory | None:
        return self.inventories.get((tenant_id, workspace_id))

    def put_candidate(self, value: SourceCandidate) -> SourceCandidate:
        self.candidates[value.candidate_id] = value
        return value

    def get_candidate(self, candidate_id: str) -> SourceCandidate | None:
        return self.candidates.get(candidate_id)

    def put_binding(self, value: SourceBinding) -> SourceBinding:
        self.bindings[value.source_id] = value
        return value

    def get_binding(self, source_id: str) -> SourceBinding | None:
        return self.bindings.get(source_id)

    def list_bindings(self, *, tenant_id: str, workspace_id: str) -> list[SourceBinding]:
        return [
            item
            for item in self.bindings.values()
            if item.tenant_id == tenant_id and item.workspace_id == workspace_id
        ]

    def put_assessment(self, value: SourceAssessment) -> SourceAssessment:
        self.assessments[value.source_id] = value
        return value

    def get_assessment(self, source_id: str) -> SourceAssessment | None:
        return self.assessments.get(source_id)

    def put_alignment(
        self, value: CrossSourceAlignmentAssessment
    ) -> CrossSourceAlignmentAssessment:
        self.alignments[value.workspace_id] = value
        return value

    def get_alignment(self, workspace_id: str) -> CrossSourceAlignmentAssessment | None:
        return self.alignments.get(workspace_id)

    def put_transformation_plan(self, value: TransformationPlan) -> TransformationPlan:
        self.transform_plans[value.plan_id] = value
        return value

    def get_transformation_plan(self, plan_id: str) -> TransformationPlan | None:
        return self.transform_plans.get(plan_id)

    def put_preview(self, value: TransformationPreview) -> TransformationPreview:
        self.previews[value.preview_id] = value
        return value

    def get_preview(self, preview_id: str) -> TransformationPreview | None:
        return self.previews.get(preview_id)

    def put_foundation_plan(self, value: FoundationPlan) -> FoundationPlan:
        self.foundation_plans[value.plan_id] = value
        return value

    def get_foundation_plan(self, plan_id: str) -> FoundationPlan | None:
        return self.foundation_plans.get(plan_id)

    def put_approval(self, value: FoundationApproval) -> FoundationApproval:
        self.approvals[value.plan_id] = value
        return value

    def get_approval_for_plan(self, plan_id: str) -> FoundationApproval | None:
        return self.approvals.get(plan_id)

    def put_decision(self, value: UserDecision) -> UserDecision:
        self.decisions.setdefault(value.source_id, []).append(value)
        return value

    def list_decisions(self, source_id: str) -> list[UserDecision]:
        return list(self.decisions.get(source_id, []))

    def put_file(self, value: DriveFileRecord) -> DriveFileRecord:
        self.files[value.drive_file_id] = value
        return value

    def get_file(self, drive_file_id: str) -> DriveFileRecord | None:
        return self.files.get(drive_file_id)

    def list_files(self, *, tenant_id: str, workspace_id: str) -> list[DriveFileRecord]:
        del tenant_id, workspace_id
        return list(self.files.values())

    def put_source_receipt(self, value: SourceFoundationReceipt) -> SourceFoundationReceipt:
        key = value.source_ids[0] if value.source_ids else value.receipt_id
        self.source_receipts.setdefault(key, []).append(value)
        return value

    def get_current_source_receipt(self, source_id: str) -> SourceFoundationReceipt | None:
        rows = self.source_receipts.get(source_id, [])
        return rows[-1] if rows else None

    def put_foundation_receipt(
        self, value: DataFoundationReadyReceipt
    ) -> DataFoundationReadyReceipt:
        self.foundation_receipts.setdefault((value.tenant_id, value.workspace_id), []).append(value)
        return value

    def get_current_foundation_receipt(
        self, *, tenant_id: str, workspace_id: str
    ) -> DataFoundationReadyReceipt | None:
        rows = self.foundation_receipts.get((tenant_id, workspace_id), [])
        return rows[-1] if rows else None

    def put_assessment_receipt(self, value: SourceAssessmentReceipt) -> SourceAssessmentReceipt:
        self.assessment_receipts.append(value)
        return value

    def put_transform_receipt(self, value: TransformationReceipt) -> TransformationReceipt:
        self.transform_receipts.append(value)
        return value

    def get_transform_receipt(
        self, *, source_id: str, plan_id: str, source_fingerprint: str
    ) -> TransformationReceipt | None:
        for item in reversed(self.transform_receipts):
            if (
                source_id in item.source_ids
                and item.plan_id == plan_id
                and item.input_fingerprints.get("source") == source_fingerprint
                and item.status == "APPLIED"
            ):
                return item
        return None

    def put_drive_import_receipt(self, value: DriveImportReceipt) -> DriveImportReceipt:
        self.drive_import_receipts.append(value)
        return value

    def put_provisioning_receipt(
        self, value: FoundationProvisioningReceipt
    ) -> FoundationProvisioningReceipt:
        self.provisioning_receipts.append(value)
        return value

    def put_provisioning_run(self, value: ProvisioningRun) -> ProvisioningRun:
        self.provisioning_runs[value.run_id] = value
        return value

    def list_receipts(self, *, tenant_id: str, workspace_id: str) -> list[object]:
        rows: list[object] = []
        for collection in (
            self.assessment_receipts,
            self.transform_receipts,
            self.drive_import_receipts,
            self.provisioning_receipts,
        ):
            rows.extend(
                item
                for item in collection
                if item.tenant_id == tenant_id and item.workspace_id == workspace_id
            )
        for recs in self.source_receipts.values():
            rows.extend(
                item
                for item in recs
                if item.tenant_id == tenant_id and item.workspace_id == workspace_id
            )
        rows.extend(self.foundation_receipts.get((tenant_id, workspace_id), []))
        return rows

    def put_cycle(self, value: MeasurementCycle) -> MeasurementCycle:
        self.cycles[value.cycle_id] = value
        return value

    def get_cycle(self, cycle_id: str) -> MeasurementCycle | None:
        return self.cycles.get(cycle_id)

    def list_cycles(self, *, tenant_id: str, workspace_id: str) -> list[MeasurementCycle]:
        return [
            item
            for item in self.cycles.values()
            if item.tenant_id == tenant_id and item.workspace_id == workspace_id
        ]

    def put_coverage(self, value: CoverageAssessment) -> CoverageAssessment:
        self.coverage[value.cycle_id] = value
        return value

    def get_coverage(self, cycle_id: str) -> CoverageAssessment | None:
        return self.coverage.get(cycle_id)

    def put_hints(self, value: DiscoveryHints) -> DiscoveryHints:
        self.hints[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_hints(self, *, tenant_id: str, workspace_id: str) -> DiscoveryHints | None:
        return self.hints.get((tenant_id, workspace_id))

    def put_data_preview(self, value: DataPreview) -> DataPreview:
        self.data_previews[value.preview_id] = value
        return value

    def put_canonical_preview(self, value: CanonicalPreview) -> CanonicalPreview:
        self.canonical_previews[value.output_resource] = value
        return value

    def get_canonical_preview(self, *, workspace_id: str) -> CanonicalPreview | None:
        del workspace_id
        if not self.canonical_previews:
            return None
        return next(reversed(self.canonical_previews.values()))

    def put_scope(self, source_id: str, value: SourceScope) -> SourceScope:
        self.scopes[source_id] = value
        return value

    def get_scope(self, source_id: str) -> SourceScope | None:
        return self.scopes.get(source_id)

    def put_physical(self, source_id: str, value: PhysicalMetadata) -> PhysicalMetadata:
        self.physical[source_id] = value
        return value

    def get_physical(self, source_id: str) -> PhysicalMetadata | None:
        return self.physical.get(source_id)

    def put_transition(self, value: SourceContinuityPlan) -> SourceContinuityPlan:
        self.transitions.append(value)
        return value

    def list_transitions(self, *, workspace_id: str) -> list[SourceContinuityPlan]:
        return [
            item
            for item in self.transitions
            if item.workspace_id in {None, workspace_id}
        ]

    def put_intelligence_brief(self, value: DataIntelligenceBrief) -> DataIntelligenceBrief:
        self.intelligence_briefs[(value.tenant_id, value.workspace_id)] = value
        return value

    def get_intelligence_brief(
        self, *, tenant_id: str, workspace_id: str
    ) -> DataIntelligenceBrief | None:
        return self.intelligence_briefs.get((tenant_id, workspace_id))

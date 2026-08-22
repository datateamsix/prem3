"""Build source candidates from metadata + registry evidence."""

from __future__ import annotations

from app.data_foundation.contracts import (
    EvidenceRequirement,
    ResourceIdentity,
    SourceCandidate,
    SourceCoverageInventory,
)
from app.data_foundation.discovery.provider_matching import match_provider
from app.data_foundation.enums import (
    CandidateGroup,
    ConfirmationClass,
    CoverageState,
    LocationType,
    ProvenanceClass,
)
from app.data_foundation.ids import new_candidate_id


def candidate_from_table(
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    dataset_id: str,
    table_id: str,
    field_names: tuple[str, ...],
    requirement: EvidenceRequirement | None,
    row_count: int | None = None,
) -> SourceCandidate:
    match = match_provider(
        table_or_file_name=table_id,
        field_names=field_names,
        requirement_concept=requirement.concept if requirement else None,
    )
    if match.provenance is ProvenanceClass.VERIFIED:
        group = CandidateGroup.VERIFIED
    elif match.provider_id:
        group = CandidateGroup.LIKELY
    else:
        group = CandidateGroup.NEEDS_DECISION
    return SourceCandidate(
        candidate_id=new_candidate_id(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        evidence_requirement_id=requirement.requirement_id if requirement else None,
        location_type=LocationType.BIGQUERY,
        resource=ResourceIdentity(
            location_type=LocationType.BIGQUERY,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            logical_path=f"{project_id}.{dataset_id}.{table_id}",
        ),
        group=group,
        provider_candidate=match.provider_id,
        provider_match=match,
        history_summary=None if row_count is None else f"{row_count} rows",
        metric_summary=",".join(field_names[:8]),
        authority=match.provenance,
    )


def candidate_from_drive_file(
    *,
    tenant_id: str,
    workspace_id: str,
    file_id: str,
    name: str,
    parent_folder_id: str,
    field_names: tuple[str, ...] = (),
    requirement: EvidenceRequirement | None = None,
) -> SourceCandidate:
    match = match_provider(
        table_or_file_name=name,
        field_names=field_names,
        filename_hint=name,
        requirement_concept=requirement.concept if requirement else None,
    )
    group = CandidateGroup.LIKELY if match.provider_id else CandidateGroup.NEEDS_DECISION
    return SourceCandidate(
        candidate_id=new_candidate_id(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        evidence_requirement_id=requirement.requirement_id if requirement else None,
        location_type=LocationType.GOOGLE_DRIVE,
        resource=ResourceIdentity(
            location_type=LocationType.GOOGLE_DRIVE,
            drive_file_id=file_id,
            drive_folder_id=parent_folder_id,
            logical_path=name,
        ),
        group=group,
        provider_candidate=match.provider_id,
        provider_match=match,
        authority=match.provenance,
    )


def build_inventory(
    *,
    tenant_id: str,
    workspace_id: str,
    requirements: tuple[EvidenceRequirement, ...],
    candidates: tuple[SourceCandidate, ...],
) -> SourceCoverageInventory:
    updated: list[EvidenceRequirement] = []
    by_req = {
        item.requirement_id: [
            cand for cand in candidates if cand.evidence_requirement_id == item.requirement_id
        ]
        for item in requirements
    }
    for item in requirements:
        matches = by_req.get(item.requirement_id, [])
        if item.coverage_state is CoverageState.PREM3_PROVIDED:
            updated.append(item)
            continue
        if any(cand.group is CandidateGroup.VERIFIED for cand in matches):
            updated.append(
                item.model_copy(
                    update={
                        "coverage_state": CoverageState.SOURCE_FOUND,
                        "confirmation": ConfirmationClass.LIKELY,
                    }
                )
            )
        elif matches:
            updated.append(
                item.model_copy(
                    update={
                        "coverage_state": CoverageState.SOURCE_PARTIAL,
                        "confirmation": ConfirmationClass.NEEDS,
                    }
                )
            )
        else:
            updated.append(item)
    return SourceCoverageInventory(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        requirements=tuple(updated),
        candidates=candidates,
        verified=tuple(c.candidate_id for c in candidates if c.group is CandidateGroup.VERIFIED),
        likely=tuple(c.candidate_id for c in candidates if c.group is CandidateGroup.LIKELY),
        needs_decision=tuple(
            c.candidate_id for c in candidates if c.group is CandidateGroup.NEEDS_DECISION
        ),
        excluded=tuple(c.candidate_id for c in candidates if c.group is CandidateGroup.EXCLUDED),
    )

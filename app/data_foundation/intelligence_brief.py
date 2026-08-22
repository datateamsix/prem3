"""Grounded Data Intelligence Brief. Advisory; cites structured finding IDs."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.contracts import (
    CoverageAssessment,
    DataIntelligenceBrief,
    IntelligenceBriefSection,
    SourceAssessment,
)
from app.data_foundation.enums import QualityStatus
from app.data_foundation.ids import new_intelligence_brief_id

BRIEF_MODEL_VERSION = "data-foundation/intelligence-brief/deterministic/v1"


def compile_data_intelligence_brief(
    *,
    tenant_id: str,
    workspace_id: str,
    assessments: list[SourceAssessment],
    coverage: CoverageAssessment | None,
) -> DataIntelligenceBrief:
    finding_ids = [
        item.check_id
        for assessment in assessments
        for item in assessment.quality.checks
        if item.status in {QualityStatus.BLOCKER, QualityStatus.REVIEW}
    ]
    if coverage is not None:
        finding_ids.extend(item.gap_id for item in coverage.gaps)
    refs = tuple(finding_ids)
    found = IntelligenceBriefSection(
        heading="What PreM3 found",
        body=f"{len(assessments)} assessed sources. Coverage gaps: {len(coverage.gaps) if coverage else 0}.",
        evidence_refs=refs,
    )
    quality = IntelligenceBriefSection(
        heading="Data-quality findings",
        body="; ".join(finding_ids[:12]) or "No blocking or review findings.",
        evidence_refs=refs,
    )
    mend = IntelligenceBriefSection(
        heading="PreM3 can mend",
        body="Deterministic type/format normalization and AUTO_SAFE transforms only. Missing is not zero.",
        evidence_refs=refs,
    )
    decisions = IntelligenceBriefSection(
        heading="Needs your decision",
        body="; ".join(item.recommended_next_action for item in coverage.gaps) if coverage else "No coverage decisions.",
        evidence_refs=refs,
    )
    premodel = IntelligenceBriefSection(
        heading="Carries into Pre-Modeling",
        body="premodel_review_findings remain typed findings, not a second readiness string.",
        evidence_refs=refs,
    )
    return DataIntelligenceBrief(
        brief_id=new_intelligence_brief_id(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        generated_at=datetime.now(UTC),
        model_version=BRIEF_MODEL_VERSION,
        what_prem3_found=found,
        data_quality_findings=quality,
        prem3_can_mend=mend,
        needs_your_decision=decisions,
        carries_into_premodeling=premodel,
        evidence_refs=refs,
        advisory=True,
    )

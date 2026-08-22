"""Grounded Business Intelligence Brief. Advisory; cites BusinessFact IDs only."""

from __future__ import annotations

from datetime import UTC, datetime

from app.business_iq.contracts import (
    BriefSection,
    BusinessIntelligenceBrief,
    BusinessProfile,
)
from app.business_iq.ids import new_brief_id

BRIEF_MODEL_VERSION = "business-iq/brief/deterministic/v1"


def compile_grounded_brief(*, profile: BusinessProfile) -> BusinessIntelligenceBrief:
    fact_ids = tuple(item.fact_id for item in profile.facts)
    channel_names = ", ".join(item.custom_name or item.canonical_name for item in profile.marketing_portfolio)
    markets = ", ".join(item.name for item in profile.markets) or "unspecified markets"
    kpi = profile.kpi or "an unspecified KPI"
    identity = profile.business_identity.brand_name or profile.business_identity.legal_name or "This business"
    gaps = [item.question for item in profile.knowledge_gaps if not item.acknowledged]
    events = [item.name for item in profile.events]
    priors = [item.description for item in profile.prior_evidence]

    summary = BriefSection(
        heading="plain_language_summary",
        body=(
            f"{identity} is measuring {kpi} across {markets}. "
            f"Material channels: {channel_names or 'none declared'}."
        ),
        evidence_refs=fact_ids,
    )
    matters = BriefSection(
        heading="what_matters_most",
        body=(
            f"Portfolio lifecycle and effective dates drive expected coverage. "
            f"Events on record: {', '.join(events) or 'none'}."
        ),
        evidence_refs=fact_ids,
    )
    modeling = BriefSection(
        heading="modeling_considerations",
        body=(
            "Use the pinned BusinessProfile snapshot. Do not treat UNKNOWN as zero. "
            "Channel pause/retire dates must compile to NOT_EXPECTED, not MISSING."
        ),
        evidence_refs=fact_ids,
    )
    forecasting = BriefSection(
        heading="forecasting_considerations",
        body="Forecasting remains downstream of DATA_FOUNDATION_READY and MODEL_READY.",
        evidence_refs=fact_ids,
    )
    questions = BriefSection(
        heading="open_questions",
        body="; ".join(gaps) or "No open knowledge gaps.",
        evidence_refs=fact_ids,
    )
    next_req = BriefSection(
        heading="next_evidence_requirements",
        body=(
            f"Compile EvidenceRequirementSet from this snapshot. "
            f"Prior evidence on file: {', '.join(priors) or 'none'}."
        ),
        evidence_refs=fact_ids,
    )
    return BusinessIntelligenceBrief(
        brief_id=new_brief_id(),
        tenant_id=profile.tenant_id,
        workspace_id=profile.workspace_id,
        profile_snapshot_id=profile.current_snapshot_id,
        fingerprint=profile.fingerprint,
        generated_at=datetime.now(UTC),
        model_version=BRIEF_MODEL_VERSION,
        plain_language_summary=summary,
        what_matters_most=matters,
        modeling_considerations=modeling,
        forecasting_considerations=forecasting,
        open_questions=questions,
        next_evidence_requirements=next_req,
        evidence_refs=fact_ids,
        advisory=True,
    )

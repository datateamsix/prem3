"""Deterministic BUSINESS_CONTEXT_READY. Gemini cannot emit this state."""

from __future__ import annotations

from datetime import UTC, datetime

from app.business_iq.contracts import BusinessContextReadyReceipt, BusinessProfile
from app.business_iq.enums import BusinessContextReadyStatus, KnowledgeState
from app.business_iq.ids import new_receipt_id


REQUIRED_CONCEPTS = (
    "business_identity",
    "measurement_objective",
    "kpi",
    "markets",
    "marketing_portfolio",
)


def _gap_acknowledged(profile: BusinessProfile, concept: str) -> bool:
    return any(
        item.concept == concept
        and (item.acknowledged or item.knowledge_state is KnowledgeState.UNKNOWN_ACKNOWLEDGED)
        for item in profile.knowledge_gaps
    )


def _addressed(profile: BusinessProfile) -> tuple[list[str], list[str], list[str]]:
    addressed: list[str] = []
    missing: list[str] = []
    unknown: list[str] = []

    identity_ok = bool(profile.business_identity.legal_name or profile.business_identity.brand_name)
    _record("business_identity", identity_ok, profile, addressed, missing, unknown)

    objective_ok = bool(profile.measurement_objectives)
    _record("measurement_objective", objective_ok, profile, addressed, missing, unknown)

    kpi_ok = bool(profile.kpi)
    _record("kpi", kpi_ok, profile, addressed, missing, unknown)

    markets_ok = bool(profile.markets)
    _record("markets", markets_ok, profile, addressed, missing, unknown)

    channels_ok = bool(profile.marketing_portfolio)
    _record("marketing_portfolio", channels_ok, profile, addressed, missing, unknown)

    return addressed, missing, unknown


def _record(
    concept: str,
    present: bool,
    profile: BusinessProfile,
    addressed: list[str],
    missing: list[str],
    unknown: list[str],
) -> None:
    if present:
        addressed.append(concept)
        return
    if _gap_acknowledged(profile, concept):
        unknown.append(concept)
        addressed.append(concept)
        return
    missing.append(concept)


def evaluate_business_context_ready(
    *,
    profile: BusinessProfile,
    snapshot_id: str,
    actor_id: str,
) -> BusinessContextReadyReceipt:
    addressed, missing, unknown = _addressed(profile)
    ready = not missing
    return BusinessContextReadyReceipt(
        receipt_id=new_receipt_id(),
        tenant_id=profile.tenant_id,
        workspace_id=profile.workspace_id,
        profile_id=profile.profile_id,
        snapshot_id=snapshot_id,
        fingerprint=profile.fingerprint,
        status=(
            BusinessContextReadyStatus.BUSINESS_CONTEXT_READY
            if ready
            else BusinessContextReadyStatus.NOT_READY
        ),
        addressed_concepts=tuple(addressed),
        missing_concepts=tuple(missing),
        unknown_acknowledged=tuple(unknown),
        executed_at=datetime.now(UTC),
        executed_by=actor_id,
    )

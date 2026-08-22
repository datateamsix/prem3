"""Compile a Data Foundation snapshot port from durable Business IQ state."""

from __future__ import annotations

from app.business_iq.contracts import BusinessProfile, BusinessProfileSnapshot as IqSnapshot
from app.business_iq.enums import BusinessContextReadyStatus, KnowledgeState
from app.data_foundation.contracts import (
    BusinessChannelFact,
    BusinessEventFact,
    BusinessProfileSnapshot,
    PriorEvidenceFact,
)


def snapshot_from_business_iq(
    snapshot: IqSnapshot,
    *,
    business_context_ready: bool,
) -> BusinessProfileSnapshot:
    profile = snapshot.profile
    return snapshot_from_profile(profile, snapshot_id=snapshot.snapshot_id, ready=business_context_ready)


def snapshot_from_profile(
    profile: BusinessProfile,
    *,
    snapshot_id: str,
    ready: bool,
) -> BusinessProfileSnapshot:
    unknowns = tuple(
        item.concept
        for item in profile.knowledge_gaps
        if item.acknowledged or item.knowledge_state is KnowledgeState.UNKNOWN_ACKNOWLEDGED
    )
    return BusinessProfileSnapshot(
        snapshot_id=snapshot_id,
        tenant_id=profile.tenant_id,
        workspace_id=profile.workspace_id,
        version=f"Business Profile v{profile.version}",
        fingerprint=profile.fingerprint,
        business_context_ready=ready,
        kpi=profile.kpi or "unspecified",
        kpi_definition=profile.kpi_definition or profile.kpi_custom_text,
        objective=profile.measurement_objectives[0].statement if profile.measurement_objectives else None,
        markets=tuple(item.name for item in profile.markets),
        channels=tuple(
            BusinessChannelFact(
                channel_name=item.custom_name or item.canonical_name,
                role=",".join(item.business_roles) or None,
                material=item.material,
            )
            for item in profile.marketing_portfolio
        ),
        promotions_relevant=any(item.event_type.value == "PROMOTION" for item in profile.events)
        or bool(profile.commercial_driver_notes),
        inventory_relevant="inventory" in (profile.commercial_driver_notes or "").lower(),
        competition_relevant=bool(profile.competition_notes),
        seasonality_relevant="season" in (profile.commercial_driver_notes or "").lower(),
        events=tuple(
            BusinessEventFact(
                event_type=item.event_type.value,
                name=item.name,
                start_date=item.start_date,
                end_date=item.end_date,
                note=item.custom_text or item.description,
            )
            for item in profile.events
        ),
        prior_evidence=tuple(
            PriorEvidenceFact(
                evidence_type=item.evidence_type,
                summary=item.description,
                artifact_hint=item.drive_file_id,
            )
            for item in profile.prior_evidence
        ),
        unknowns=unknowns,
    )


def channel_effective_dates(profile: BusinessProfile) -> dict[str, tuple[str | None, str | None]]:
    dates: dict[str, tuple[str | None, str | None]] = {}
    for channel in profile.marketing_portfolio:
        pair = (channel.active_from, channel.active_to)
        dates[channel.canonical_name] = pair
        if channel.custom_name:
            dates[channel.custom_name] = pair
        dates[channel.channel_id] = pair
    return dates


def is_context_ready(status: BusinessContextReadyStatus) -> bool:
    return status is BusinessContextReadyStatus.BUSINESS_CONTEXT_READY

"""Compile Business IQ snapshots into typed evidence requirements."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.contracts import (
    BusinessProfileSnapshot,
    EvidenceRequirement,
    EvidenceRequirementSet,
)
from app.data_foundation.enums import (
    ConfirmationClass,
    CoverageState,
    EvidenceRequirementType,
)
from app.data_foundation.ids import new_requirement_id


def _req(
    *,
    requirement_type: EvidenceRequirementType,
    concept: str,
    business_role: str,
    expected_category: str,
    downstream_use: tuple[str, ...],
    channel_id: str | None = None,
    market_scope: tuple[str, ...] = (),
    source_fact_ids: tuple[str, ...] = (),
    acknowledged_unknown: bool = False,
    coverage_state: CoverageState = CoverageState.SOURCE_NOT_COLLECTED,
) -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id=new_requirement_id(),
        requirement_type=requirement_type,
        concept=concept,
        business_role=business_role,
        channel_id=channel_id,
        market_scope=market_scope,
        expected_category=expected_category,
        downstream_use=downstream_use,
        source_fact_ids=source_fact_ids,
        acknowledged_unknown=acknowledged_unknown,
        coverage_state=coverage_state,
        confirmation=ConfirmationClass.NONE,
    )


def compile_evidence_requirements(snapshot: BusinessProfileSnapshot) -> EvidenceRequirementSet:
    if not snapshot.business_context_ready:
        raise ValueError("BUSINESS_CONTEXT_READY is required before Data Foundation discovery.")
    rows: list[EvidenceRequirement] = []
    rows.append(
        _req(
            requirement_type=EvidenceRequirementType.KPI,
            concept=snapshot.kpi,
            business_role="KPI",
            expected_category="outcome",
            downstream_use=("MMM", "forecasting"),
            market_scope=snapshot.markets,
            source_fact_ids=("kpi",),
        )
    )
    for channel in snapshot.channels:
        if not channel.material:
            continue
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.MEDIA,
                concept=channel.channel_name,
                business_role=channel.role or "Media",
                expected_category="media",
                downstream_use=("MMM", "attribution"),
                channel_id=channel.channel_name,
                market_scope=snapshot.markets,
                source_fact_ids=("channel",),
            )
        )
    if snapshot.promotions_relevant:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.PROMOTION,
                concept="Promotions",
                business_role="Treatment",
                expected_category="treatment",
                downstream_use=("MMM", "forecasting"),
                source_fact_ids=("promotions",),
            )
        )
    if snapshot.inventory_relevant:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.INVENTORY,
                concept="Inventory constraints",
                business_role="Control",
                expected_category="control",
                downstream_use=("MMM",),
                source_fact_ids=("inventory",),
            )
        )
    if snapshot.competition_relevant:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.COMPETITION,
                concept="Competitor activity",
                business_role="Control",
                expected_category="control",
                downstream_use=("MMM",),
                source_fact_ids=("competition",),
            )
        )
    if snapshot.seasonality_relevant:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.EXTERNAL_CONTROL,
                concept="Seasonality",
                business_role="Control",
                expected_category="control",
                downstream_use=("MMM", "forecasting"),
                source_fact_ids=("seasonality",),
                coverage_state=CoverageState.PREM3_PROVIDED,
            )
        )
    for event in snapshot.events:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.OTHER_CUSTOM,
                concept=event.name,
                business_role=event.event_type,
                expected_category="event",
                downstream_use=("MMM",),
                source_fact_ids=(event.event_type,),
            )
        )
    for prior in snapshot.prior_evidence:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.EXPERIMENT_EVIDENCE
                if "experiment" in prior.evidence_type.lower()
                or "holdout" in prior.evidence_type.lower()
                or "lift" in prior.evidence_type.lower()
                else EvidenceRequirementType.PRIOR_MMM,
                concept="Prior evidence",
                business_role="Prior",
                expected_category="prior",
                downstream_use=("MMM priors",),
                source_fact_ids=(prior.evidence_type,),
            )
        )
    for unknown in snapshot.unknowns:
        rows.append(
            _req(
                requirement_type=EvidenceRequirementType.OTHER_CUSTOM,
                concept=unknown,
                business_role="Unknown",
                expected_category="unknown",
                downstream_use=(),
                acknowledged_unknown=True,
            )
        )
    return EvidenceRequirementSet(
        tenant_id=snapshot.tenant_id,
        workspace_id=snapshot.workspace_id,
        snapshot_id=snapshot.snapshot_id,
        snapshot_fingerprint=snapshot.fingerprint,
        compiled_at=datetime.now(UTC),
        requirements=tuple(rows),
    )

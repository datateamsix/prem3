"""Typed Business IQ contracts. Persistent, versioned, provenance-aware."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.business_iq.enums import (
    BusinessContextReadyStatus,
    ChannelLifecycle,
    ClarificationAnswer,
    ConfirmationState,
    EventType,
    FactProvenance,
    FactSourceType,
    HypothesisStatus,
    KnowledgeState,
    ProposalDecision,
)

SCHEMA_VERSION = "business-iq/profile/v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BusinessIdentity(FrozenModel):
    legal_name: str | None = None
    brand_name: str | None = None
    industry: str | None = None
    industry_custom: str | None = None
    website: str | None = None
    description: str | None = None


class MeasurementObjective(FrozenModel):
    objective_id: str
    statement: str
    custom_text: str | None = None
    knowledge_state: KnowledgeState = KnowledgeState.USER_REPORTED


class Market(FrozenModel):
    market_id: str
    name: str
    custom_text: str | None = None
    geo_level: str | None = None


class MarketingChannel(FrozenModel):
    channel_id: str
    canonical_name: str
    custom_name: str | None = None
    business_roles: tuple[str, ...] = ()
    markets: tuple[str, ...] = ()
    active_from: str | None = None
    active_to: str | None = None
    lifecycle_status: ChannelLifecycle = ChannelLifecycle.DECLARED
    material: bool = True


class BusinessFact(FrozenModel):
    fact_id: str
    concept: str
    value: Any = None
    value_type: str = "string"
    unit: str | None = None
    scope: str | None = None
    knowledge_state: KnowledgeState = KnowledgeState.USER_REPORTED
    source_type: FactSourceType = FactSourceType.USER
    source_ref: str | None = None
    provenance: FactProvenance = FactProvenance.PROVIDED_BY_USER
    question_id: str | None = None
    confidence: str | None = None
    confirmation_state: ConfirmationState = ConfirmationState.UNCONFIRMED
    effective_from: str | None = None
    effective_to: str | None = None
    custom_text: str | None = None


class BusinessEvent(FrozenModel):
    event_id: str
    event_type: EventType
    name: str
    description: str | None = None
    custom_text: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    markets: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    source_type: FactSourceType = FactSourceType.USER
    confirmation_state: ConfirmationState = ConfirmationState.UNCONFIRMED


class BusinessRelationship(FrozenModel):
    relationship_id: str
    subject_ref: str
    predicate: str
    object_ref: str
    custom_text: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    source_type: FactSourceType = FactSourceType.USER
    confirmation_state: ConfirmationState = ConfirmationState.UNCONFIRMED


class BusinessHypothesis(FrozenModel):
    hypothesis_id: str
    statement: str
    entities: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    status: HypothesisStatus = HypothesisStatus.OPEN
    modeler_review_required: bool = True


class KnowledgeGap(FrozenModel):
    gap_id: str
    concept: str
    question: str
    acknowledged: bool = False
    knowledge_state: KnowledgeState = KnowledgeState.UNKNOWN


class PriorEvidenceReference(FrozenModel):
    evidence_id: str
    evidence_type: str
    description: str
    channel: str | None = None
    market: str | None = None
    period: str | None = None
    kpi: str | None = None
    drive_file_id: str | None = None
    provenance: FactProvenance = FactProvenance.PROVIDED_BY_USER
    availability_state: str = "DECLARED"


class ProfileMetadata(FrozenModel):
    organization_display_name: str | None = None
    logo_asset_ref: str | None = None
    schema_version: str = SCHEMA_VERSION


class BusinessProfile(FrozenModel):
    profile_id: str
    tenant_id: str
    workspace_id: str
    version: int
    fingerprint: str
    current_snapshot_id: str
    business_identity: BusinessIdentity = BusinessIdentity()
    measurement_objectives: tuple[MeasurementObjective, ...] = ()
    kpi: str | None = None
    kpi_definition: str | None = None
    kpi_custom_text: str | None = None
    economics_notes: str | None = None
    markets: tuple[Market, ...] = ()
    marketing_portfolio: tuple[MarketingChannel, ...] = ()
    customer_journey_notes: str | None = None
    decision_process_notes: str | None = None
    commercial_driver_notes: str | None = None
    competition_notes: str | None = None
    facts: tuple[BusinessFact, ...] = ()
    events: tuple[BusinessEvent, ...] = ()
    relationships: tuple[BusinessRelationship, ...] = ()
    hypotheses: tuple[BusinessHypothesis, ...] = ()
    knowledge_gaps: tuple[KnowledgeGap, ...] = ()
    prior_evidence: tuple[PriorEvidenceReference, ...] = ()
    metadata: ProfileMetadata = ProfileMetadata()
    created_at: datetime
    updated_at: datetime
    updated_by: str
    created_by: str


class BusinessProfileVersion(FrozenModel):
    profile_id: str
    version: int
    snapshot_id: str
    fingerprint: str
    created_at: datetime
    created_by: str
    change_summary: str


class BusinessProfileSnapshot(FrozenModel):
    snapshot_id: str
    profile_id: str
    tenant_id: str
    workspace_id: str
    version: int
    fingerprint: str
    profile: BusinessProfile
    created_at: datetime
    created_by: str
    immutable: bool = True


class BusinessContextReadyReceipt(FrozenModel):
    receipt_id: str
    tenant_id: str
    workspace_id: str
    profile_id: str
    snapshot_id: str
    fingerprint: str
    status: BusinessContextReadyStatus
    addressed_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    unknown_acknowledged: tuple[str, ...]
    executed_at: datetime
    executed_by: str


class BriefSection(FrozenModel):
    heading: str
    body: str
    evidence_refs: tuple[str, ...] = ()


class BusinessIntelligenceBrief(FrozenModel):
    brief_id: str
    tenant_id: str
    workspace_id: str
    profile_snapshot_id: str
    fingerprint: str
    generated_at: datetime
    model_version: str
    plain_language_summary: BriefSection
    what_matters_most: BriefSection
    modeling_considerations: BriefSection
    forecasting_considerations: BriefSection
    open_questions: BriefSection
    next_evidence_requirements: BriefSection
    evidence_refs: tuple[str, ...]
    advisory: bool = True


class BusinessProfileUpdateProposal(FrozenModel):
    proposal_id: str
    tenant_id: str
    workspace_id: str
    profile_id: str
    previous_fact: dict[str, Any] | None = None
    observed_evidence: dict[str, Any] = Field(default_factory=dict)
    proposed_fact: dict[str, Any] = Field(default_factory=dict)
    decision: ProposalDecision = ProposalDecision.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    receipt_id: str | None = None
    created_at: datetime
    created_by: str


class BusinessClarificationRequest(FrozenModel):
    clarification_id: str
    tenant_id: str
    workspace_id: str
    profile_id: str
    coverage_gap_id: str | None = None
    fact_id: str | None = None
    question: str
    answer: ClarificationAnswer | None = None
    proposal_id: str | None = None
    created_at: datetime
    answered_at: datetime | None = None
    answered_by: str | None = None

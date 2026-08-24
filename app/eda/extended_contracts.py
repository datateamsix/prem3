"""Typed PreM3 extended EDA contracts. Official Meridian severity is immutable."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.contracts import utc_now

INTERPRETATION_POLICY_VERSION = "extended-eda/v1"
TRUSTED_GENERATED_MERIDIAN_HTML = "TRUSTED_GENERATED_MERIDIAN_HTML"
CUSTOMER_UPLOAD_HTML = "CUSTOMER_UPLOAD_HTML"
CONTEXT_LABEL_BUSINESS_IQ = "BUSINESS_IQ_CONTEXT"
CONTEXT_LABEL_DATA_FOUNDATION = "DATA_FOUNDATION_CONTEXT"
CONTEXT_LABEL_MODEL_READY = "MODEL_READY_CONTEXT"
KNOT_FALLBACK_STATEMENT = (
    "This enabled official EDA only. It does not establish the final knot strategy."
)
KNOTS_NORMATIVE_REF = (
    "https://developers.google.com/meridian/docs/advanced-modeling/setting-knots"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StatementAuthority(StrEnum):
    OFFICIAL_MERIDIAN = "OFFICIAL_MERIDIAN"
    PREM3_INTERPRETATION = "PREM3_INTERPRETATION"
    PREM3_RECOMMENDATION = "PREM3_RECOMMENDATION"
    HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"


class ExtendedEDAReportStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED_INTERPRETATION = "FAILED_INTERPRETATION"


class EDAImplicationType(StrEnum):
    CONTROL_SELECTION = "CONTROL_SELECTION"
    TREATMENT_CLASSIFICATION = "TREATMENT_CLASSIFICATION"
    PRIOR_REVIEW = "PRIOR_REVIEW"
    KNOT_STRATEGY = "KNOT_STRATEGY"
    TIME_EFFECT_REVIEW = "TIME_EFFECT_REVIEW"
    MODEL_WINDOW_REVIEW = "MODEL_WINDOW_REVIEW"
    GEO_SCOPE_REVIEW = "GEO_SCOPE_REVIEW"
    RF_SPECIFICATION = "RF_SPECIFICATION"
    ADSTOCK_REVIEW = "ADSTOCK_REVIEW"
    SATURATION_REVIEW = "SATURATION_REVIEW"
    COLLINEARITY_REVIEW = "COLLINEARITY_REVIEW"
    DATA_ADEQUACY = "DATA_ADEQUACY"
    HOLDOUT_REVIEW = "HOLDOUT_REVIEW"
    MCMC_PREPARATION = "MCMC_PREPARATION"
    OTHER = "OTHER"


class EDAActionType(StrEnum):
    REVIEW_MODEL_SPEC = "REVIEW_MODEL_SPEC"
    REVIEW_CONTROL_ROLE = "REVIEW_CONTROL_ROLE"
    REVIEW_TREATMENT_ROLE = "REVIEW_TREATMENT_ROLE"
    REVIEW_PRIOR = "REVIEW_PRIOR"
    REVIEW_WINDOW = "REVIEW_WINDOW"
    REVIEW_GEO_SCOPE = "REVIEW_GEO_SCOPE"
    COLLECT_MORE_DATA = "COLLECT_MORE_DATA"
    CORRECT_SOURCE_DATA = "CORRECT_SOURCE_DATA"
    RETURN_TO_FOUNDATION = "RETURN_TO_FOUNDATION"
    RERUN_PREMODELING = "RERUN_PREMODELING"
    PROCEED_TO_MODEL_DESIGN = "PROCEED_TO_MODEL_DESIGN"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    REVIEW_ATTENTION_FINDING = "REVIEW_ATTENTION_FINDING"
    RESOLVE_EDA_ERROR = "RESOLVE_EDA_ERROR"


class EDAActionOwner(StrEnum):
    SYSTEM = "SYSTEM"
    ANALYST = "ANALYST"
    MODELER = "MODELER"
    BUSINESS_OWNER = "BUSINESS_OWNER"
    DATA_OWNER = "DATA_OWNER"


class LabeledContextFact(FrozenModel):
    label: str
    statement: str
    source_ref: str | None = None
    authority: StatementAuthority = StatementAuthority.PREM3_INTERPRETATION

    @field_validator("label")
    @classmethod
    def _context_label(cls, value: str) -> str:
        allowed = {
            CONTEXT_LABEL_BUSINESS_IQ,
            CONTEXT_LABEL_DATA_FOUNDATION,
            CONTEXT_LABEL_MODEL_READY,
        }
        if value not in allowed:
            raise ValueError(f"context fact label must be one of {sorted(allowed)}")
        return value


class OfficialEDAFindingView(FrozenModel):
    check_type: str
    severity: str
    title: str | None = None
    explanation: str
    affected_variables: tuple[str, ...] = ()
    evidence_ref: str
    finding_cause: str | None = None
    analysis_level: str | None = None


class Prem3FindingInterpretation(FrozenModel):
    interpretation: str
    why_it_matters: str
    business_context_relevance: tuple[str, ...] = ()
    modeling_implication: str
    recommended_action: str
    alternatives: tuple[str, ...] = ()
    uncertainty: str
    decision_required: bool = False
    decision_type: str | None = None
    authority: StatementAuthority
    evidence_refs: tuple[str, ...] = ()

    @field_validator("authority")
    @classmethod
    def _not_official(cls, value: StatementAuthority) -> StatementAuthority:
        if value is StatementAuthority.OFFICIAL_MERIDIAN:
            raise ValueError("PreM3 interpretation cannot claim OFFICIAL_MERIDIAN authority.")
        return value

    @model_validator(mode="after")
    def _evidence_required(self) -> Prem3FindingInterpretation:
        if not self.evidence_refs:
            raise ValueError("PreM3 interpretation requires evidence_refs.")
        return self


class ExtendedEDAFinding(FrozenModel):
    finding_id: str
    official: OfficialEDAFindingView
    prem3: Prem3FindingInterpretation | None = None
    material: bool = True


class ExtendedEDAReadinessSummary(FrozenModel):
    official_gate_status: str
    official_gate_outcome: str
    max_official_severity: str
    error_count: int
    attention_count: int
    info_count: int
    review_recommended: bool
    safe_to_model: bool
    data_adequacy_summary: dict[str, Any] = Field(default_factory=dict)
    unresolved_user_required_count: int = 0


class ExtendedEDAExecutiveSummary(FrozenModel):
    status_statement: str
    key_strengths: tuple[str, ...] = ()
    key_risks: tuple[str, ...] = ()
    modeling_implications: tuple[str, ...] = ()
    user_actions: tuple[str, ...] = ()


class EDAModelingImplication(FrozenModel):
    implication_id: str
    implication_type: EDAImplicationType
    statement: str
    finding_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    approved_model_change: bool = False
    authority: StatementAuthority = StatementAuthority.PREM3_RECOMMENDATION

    @model_validator(mode="after")
    def _advisory(self) -> EDAModelingImplication:
        if self.approved_model_change:
            raise ValueError("EDA implications cannot approve a ModelSpec change.")
        return self


class EDARecommendedAction(FrozenModel):
    action_id: str
    finding_id: str | None = None
    action_type: EDAActionType
    statement: str
    owner: EDAActionOwner
    urgency: str
    blocking: bool = False
    evidence_required: tuple[str, ...] = ()
    target_capability: str
    route_hint: str | None = None
    authority: StatementAuthority = StatementAuthority.PREM3_RECOMMENDATION


class EDAOpenModelingDecision(FrozenModel):
    decision_type: str
    question: str
    why_required: str
    finding_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    recommended_option: str | None = None
    alternatives: tuple[str, ...] = ()
    authority: StatementAuthority = StatementAuthority.HUMAN_DECISION_REQUIRED
    status: str = "PENDING"


class EDAModelDesignHandoff(FrozenModel):
    report_id: str
    modeling_implications: tuple[EDAModelingImplication, ...] = ()
    open_modeling_decisions: tuple[EDAOpenModelingDecision, ...] = ()
    known_limitations: tuple[str, ...] = ()
    relevant_finding_refs: tuple[str, ...] = ()
    recommended_starting_actions: tuple[str, ...] = ()


class ExtendedEDASource(FrozenModel):
    meridian_version: str
    official_html_ref: str
    official_html_sha256: str
    eda_receipt_ref: str
    eda_receipt_fingerprint: str
    model_ready_manifest_ref: str | None = None
    model_ready_fingerprint: str | None = None


class ExtendedEDABusinessContext(FrozenModel):
    business_profile_snapshot_id: str | None = None
    primary_business_outcome: str | None = None
    markets: tuple[str, ...] = ()
    material_channels: tuple[str, ...] = ()
    material_drivers: tuple[str, ...] = ()
    labeled_facts: tuple[LabeledContextFact, ...] = ()


class ExtendedEDAEvidenceItem(FrozenModel):
    evidence_id: str
    kind: str
    ref: str
    sha256: str | None = None
    authority: StatementAuthority


class OfficialReportView(FrozenModel):
    official_report_available: bool
    content_type: str = "text/html"
    authorized_view_url: str | None = None
    sha256: str | None = None
    artifact_class: str | None = None


class EDAInterpretationContext(FrozenModel):
    finding_id: str
    official_severity: str
    official_explanation: str
    check_type: str
    affected_variables: tuple[str, ...] = ()
    data_adequacy_summary: dict[str, Any] = Field(default_factory=dict)
    business_iq_facts: tuple[LabeledContextFact, ...] = ()
    data_foundation_facts: tuple[LabeledContextFact, ...] = ()
    model_ready_semantics: tuple[str, ...] = ()
    meridian_normative_refs: tuple[str, ...] = ()
    unresolved_decisions: tuple[str, ...] = ()


class PreM3ExtendedEDAReport(FrozenModel):
    report_id: str
    tenant_id: str
    project_id: str
    cycle_id: str
    track_id: str
    premodel_run_id: str
    source: ExtendedEDASource
    business_context: ExtendedEDABusinessContext = Field(
        default_factory=ExtendedEDABusinessContext
    )
    readiness_summary: ExtendedEDAReadinessSummary
    executive_summary: ExtendedEDAExecutiveSummary
    findings: tuple[ExtendedEDAFinding, ...] = ()
    model_design_implications: tuple[EDAModelingImplication, ...] = ()
    open_modeling_decisions: tuple[EDAOpenModelingDecision, ...] = ()
    recommended_next_steps: tuple[EDARecommendedAction, ...] = ()
    evidence_index: tuple[ExtendedEDAEvidenceItem, ...] = ()
    model_design_handoff: EDAModelDesignHandoff
    status: ExtendedEDAReportStatus = ExtendedEDAReportStatus.COMPLETE
    version: int
    fingerprint: str
    generated_at: datetime = Field(default_factory=utc_now)
    interpretation_policy_version: str = INTERPRETATION_POLICY_VERSION
    knowledge_version: str
    data_foundation_fingerprint: str | None = None
    official_html_artifact_class: str = TRUSTED_GENERATED_MERIDIAN_HTML
    resolution_feedback_status: str | None = None
    mel_evidence_emitted: bool = False

    @model_validator(mode="after")
    def _official_severity_untouched(self) -> PreM3ExtendedEDAReport:
        ready = self.readiness_summary
        if ready.error_count > 0 and ready.official_gate_outcome != "EDA_BLOCKED":
            raise ValueError("Official ERROR cannot change EDA_BLOCKED.")
        if ready.max_official_severity == "ERROR" and ready.official_gate_status != "FAIL":
            raise ValueError("Official ERROR cannot be downgraded from FAIL.")
        return self

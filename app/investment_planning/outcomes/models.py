"""P6-10 outcome contracts. Amount arrays stay off Firestore."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import model_validator

from app.investment_optimization.contracts import FrozenModel, _reject_amount_keys
from app.investment_optimization.enums import (
    OUTCOME_POLICY_VERSION,
    AdherenceClass,
    ErrorContributorClass,
    ExecutionAdherenceStatus,
    ExperienceBoundary,
    InvestmentDecisionKind,
    LearningCandidateType,
    OutcomeLifecycleStatus,
    OutcomeSemanticType,
    OutcomeSourceAuthority,
    PredictionErrorClass,
)
from app.investment_planning.enums import SensitiveDataClass

_META = SensitiveDataClass.CONTROL_PLANE_METADATA
_AMOUNT = SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT


class InvestmentDecisionRecord(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    investment_decision_id: str
    tenant_id: str
    project_id: str
    proposal_ref: str
    proposal_decision_receipt_id: str
    planning_decision_record_id: str
    frontier_selection_ref: str | None = None
    candidate_portfolio_ref: str | None = None
    recommended_portfolio_ref: str | None = None
    decided_portfolio_ref: str | None = None
    decision: InvestmentDecisionKind
    decision_reason_code: str | None = None
    decision_reason_text_ref: str | None = None
    decided_by_user_id: str
    decided_at: datetime
    decision_context_fingerprint: str
    decision_fingerprint: str
    schema_version: str = OUTCOME_POLICY_VERSION
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> InvestmentDecisionRecord:
        _reject_amount_keys(self.model_dump(), owner="InvestmentDecisionRecord")
        return self


class RecommendationAdherence(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    recommendation_adherence_id: str
    tenant_id: str
    project_id: str
    investment_decision_ref: str
    recommended_portfolio_ref: str
    decided_portfolio_ref: str
    l1_distance: float
    max_absolute_line_deviation: float
    max_percentage_deviation: float | None = None
    channels_added: tuple[str, ...] = ()
    channels_removed: tuple[str, ...] = ()
    markets_changed: tuple[str, ...] = ()
    adherence_class: AdherenceClass
    limitations: tuple[str, ...] = ()
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> RecommendationAdherence:
        _reject_amount_keys(self.model_dump(), owner="RecommendationAdherence")
        return self


class ExecutionAdherence(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    execution_adherence_id: str
    tenant_id: str
    project_id: str
    approved_plan_ref: str
    actual_spend_source_ref: str | None = None
    exposure_handoff_ref: str | None = None
    status: ExecutionAdherenceStatus
    adherence_class: AdherenceClass
    comparable_line_count: int
    incomplete_line_count: int
    limitations: tuple[str, ...] = ()
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> ExecutionAdherence:
        _reject_amount_keys(self.model_dump(), owner="ExecutionAdherence")
        return self


class DecisionOutcomeObservation(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    decision_outcome_observation_id: str
    project_id: str
    investment_decision_ref: str
    approved_plan_ref: str | None = None
    measurement_cycle_ref: str | None = None
    outcome_metric_id: str
    outcome_unit: str
    semantic_type: OutcomeSemanticType
    observation_window_start: datetime
    observation_window_end: datetime
    as_of_time: datetime
    source_authority: OutcomeSourceAuthority
    source_refs: tuple[str, ...]
    outcome_artifact_ref: str | None = None
    observed_value: float | None = None
    supersedes_observation_id: str | None = None
    observation_fingerprint: str
    limitations: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> DecisionOutcomeObservation:
        _reject_amount_keys(self.model_dump(), owner="DecisionOutcomeObservation")
        return self


class PredictionEvidenceSet(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    prediction_evidence_id: str
    project_id: str
    frontier_selection_ref: str | None = None
    portfolio_risk_evaluation_ref: str | None = None
    parity_receipt_id: str | None = None
    exposure_risk_handoff_ref: str | None = None
    native_optimization_result_ref: str | None = None
    simulation_evidence_handoff_ref: str | None = None
    predicted_value: float | None = None
    predicted_unit: str
    recommendation_as_of_time: datetime
    decision_as_of_time: datetime
    prediction_evidence_as_of_time: datetime
    fingerprint: str
    limitations: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> PredictionEvidenceSet:
        _reject_amount_keys(self.model_dump(), owner="PredictionEvidenceSet")
        return self


class PredictionErrorSummary(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    prediction_error_id: str
    project_id: str
    prediction_evidence_ref: str
    outcome_observation_ref: str | None = None
    predicted_value: float | None = None
    realized_value: float | None = None
    signed_error: float | None = None
    absolute_error: float | None = None
    percentage_error: float | None = None
    directional_correct: bool | None = None
    realized_percentile: float | None = None
    inside_expected_interval: bool | None = None
    error_class: PredictionErrorClass
    contributor_classes: tuple[ErrorContributorClass, ...] = ()
    fingerprint: str
    limitations: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> PredictionErrorSummary:
        _reject_amount_keys(self.model_dump(), owner="PredictionErrorSummary")
        return self


class RecommendationOutcomeReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    recommendation_outcome_receipt_id: str
    tenant_id: str
    project_id: str
    recommendation_ref: str | None = None
    decision_ref: str
    approved_plan_ref: str | None = None
    recommendation_adherence_ref: str | None = None
    execution_adherence_ref: str | None = None
    actual_spend_refs: tuple[str, ...] = ()
    exposure_realization_refs: tuple[str, ...] = ()
    realized_outcome_ref: str | None = None
    prediction_evidence_ref: str | None = None
    prediction_error_ref: str | None = None
    simulation_evidence_handoff_ref: str | None = None
    learning_receipt_ref: str | None = None
    status: OutcomeLifecycleStatus
    limitations: tuple[str, ...] = ()
    receipt_fingerprint: str
    closed_at: datetime | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> RecommendationOutcomeReceipt:
        _reject_amount_keys(self.model_dump(), owner="RecommendationOutcomeReceipt")
        return self


class DecisionOutcomeLearningReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    learning_receipt_id: str
    project_id: str
    recommendation_outcome_receipt_ref: str
    issue_type: str
    evidence_refs: tuple[str, ...]
    prediction_error_class: PredictionErrorClass | None = None
    adherence_class: AdherenceClass | None = None
    learning_candidate_type: LearningCandidateType
    policy_version: str = OUTCOME_POLICY_VERSION
    experience_boundary: ExperienceBoundary = ExperienceBoundary.LOCAL_ONLY
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> DecisionOutcomeLearningReceipt:
        _reject_amount_keys(self.model_dump(), owner="DecisionOutcomeLearningReceipt")
        return self


class ExecutionAdherenceArtifact(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    execution_adherence_id: str
    planned_vs_actual: tuple[tuple[str, float | None, float | None], ...]
    fingerprint: str


OUTCOME_METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    InvestmentDecisionRecord,
    RecommendationAdherence,
    ExecutionAdherence,
    DecisionOutcomeObservation,
    PredictionEvidenceSet,
    PredictionErrorSummary,
    RecommendationOutcomeReceipt,
    DecisionOutcomeLearningReceipt,
)

OUTCOME_AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (ExecutionAdherenceArtifact,)

"""P6-09 risk-frontier contracts. Amount arrays stay off Firestore."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import field_validator, model_validator

from app.investment_optimization.contracts import FrozenModel, _reject_amount_keys
from app.investment_optimization.enums import (
    RISK_ARTIFACT_SCHEMA_VERSION,
    RISK_POLICY_VERSION,
    CandidateGenerationPolicy,
    ConcentrationDimension,
    DominanceMetric,
    DominanceSense,
    FrontierSelectionState,
    LossDefinition,
    RiskBaselineKind,
    RiskFrontierReadinessStatus,
    RiskPosture,
    RiskTaxonomyClass,
)
from app.investment_planning.enums import SensitiveDataClass

_META = SensitiveDataClass.CONTROL_PLANE_METADATA
_AMOUNT = SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT


class DominanceDimension(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    metric: DominanceMetric
    sense: DominanceSense


class RiskEvaluationPolicy(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    risk_evaluation_policy_id: str
    project_id: str
    tenant_id: str
    policy_version: str = RISK_POLICY_VERSION
    objective: str
    model_version_ref: str
    optimization_readiness_ref: str
    future_assumption_set_ref: str | None = None
    constraint_set_ref: str | None = None
    exposure_risk_handoff_ref: str | None = None
    evaluation_dimensions: tuple[RiskTaxonomyClass, ...]
    tail_probability: float
    loss_definition: LossDefinition = LossDefinition.BASELINE_MINUS_CANDIDATE_OUTCOME
    candidate_generation_policy: CandidateGenerationPolicy = (
        CandidateGenerationPolicy.NATIVE_OPTIMUM_PLUS_FEASIBLE_NEIGHBORS
    )
    minimum_candidate_count: int = 3
    neighbor_share_delta: float = 0.05
    dominance_policy: tuple[DominanceDimension, ...]
    risk_penalties_enabled: bool = True
    conservative_expected_floor_ratio: float = 0.9
    balanced_keys: tuple[DominanceMetric, ...] = (
        DominanceMetric.EXPECTED_OUTCOME,
        DominanceMetric.DOWNSIDE_TAIL,
        DominanceMetric.CONCENTRATION_HHI,
        DominanceMetric.STABILITY_L1,
    )
    baseline_kind: RiskBaselineKind = RiskBaselineKind.APPROVED_PLAN
    policy_fingerprint: str
    created_at: datetime

    @field_validator("tail_probability")
    @classmethod
    def _tail_in_unit(cls, value: float) -> float:
        if not 0.0 < value < 1.0:
            raise ValueError("tail_probability must be in (0, 1).")
        return value

    @model_validator(mode="after")
    def _metadata_only(self) -> RiskEvaluationPolicy:
        _reject_amount_keys(self.model_dump(), owner="RiskEvaluationPolicy")
        return self


class CandidateShare(FrozenModel):
    """Share-only line. Recommended currency amounts live on the GCS artifact."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    channel_id: str
    share: float


class CandidateAllocationArtifact(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    candidate_portfolio_id: str
    schema_version: str = RISK_ARTIFACT_SCHEMA_VERSION
    shares: tuple[CandidateShare, ...]
    recommended_total: str
    fingerprint: str


class FeasibilityReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    receipt_id: str
    candidate_portfolio_id: str
    feasible: bool
    conflicting_constraint_ids: tuple[str, ...] = ()
    fingerprint: str


class CandidatePortfolio(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    candidate_portfolio_id: str
    tenant_id: str
    project_id: str
    base_approved_plan_ref: str
    optimization_run_id: str
    generation_authority: str
    assumption_set_ref: str | None = None
    constraint_set_ref: str | None = None
    model_version_ref: str
    feasibility_receipt_id: str
    allocation_fingerprint: str
    input_fingerprint: str
    candidate_fingerprint: str
    native_optimum: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> CandidatePortfolio:
        _reject_amount_keys(self.model_dump(), owner="CandidatePortfolio")
        return self


class ConcentrationMetric(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    dimension: ConcentrationDimension
    hhi: float
    top_1_share: float
    top_3_share: float


class StabilityMetric(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    baseline_kind: RiskBaselineKind
    l1_share_distance: float
    max_absolute_line_movement: float
    max_percent_line_movement: float | None = None


class PortfolioRiskEvaluation(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    portfolio_risk_evaluation_id: str
    candidate_portfolio_id: str
    baseline_portfolio_ref: str
    risk_evaluation_policy_ref: str
    expected_outcome: float | None = None
    median_outcome: float | None = None
    probability_improvement: float | None = None
    lower_tail_metric: float | None = None
    posterior_risk_refs: tuple[str, ...] = ()
    scenario_risk_refs: tuple[str, ...] = ()
    exposure_delivery_risk_refs: tuple[str, ...] = ()
    model_risk_refs: tuple[str, ...] = ()
    data_risk_refs: tuple[str, ...] = ()
    concentration_metrics: tuple[ConcentrationMetric, ...] = ()
    stability_metrics: tuple[StabilityMetric, ...] = ()
    execution_risk_refs: tuple[str, ...] = ()
    optimization_risk_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evaluation_fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> PortfolioRiskEvaluation:
        _reject_amount_keys(self.model_dump(), owner="PortfolioRiskEvaluation")
        return self


class DominatedRecord(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    candidate_portfolio_id: str
    dominated_by: tuple[str, ...]
    dominance_dimensions: tuple[DominanceMetric, ...]


class MarketingInvestmentFrontier(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    frontier_id: str
    tenant_id: str
    project_id: str
    risk_evaluation_policy_id: str
    policy_fingerprint: str
    evaluated_candidate_ids: tuple[str, ...]
    non_dominated_candidate_ids: tuple[str, ...]
    dominated: tuple[DominatedRecord, ...]
    readiness: RiskFrontierReadinessStatus
    parity_receipt_id: str | None = None
    schema_version: str = RISK_ARTIFACT_SCHEMA_VERSION
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> MarketingInvestmentFrontier:
        _reject_amount_keys(self.model_dump(), owner="MarketingInvestmentFrontier")
        return self


class FrontierSelection(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    selection_id: str
    frontier_id: str
    selected_candidate_ref: str
    risk_posture: RiskPosture
    selection_policy: str
    selection_rationale_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    state: FrontierSelectionState = FrontierSelectionState.MODEL_RECOMMENDED
    selection_fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> FrontierSelection:
        _reject_amount_keys(self.model_dump(), owner="FrontierSelection")
        return self


class RiskNeutralParityReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    parity_receipt_id: str
    project_id: str
    tenant_id: str
    native_optimization_run_id: str
    native_allocation_fingerprint: str
    selected_allocation_fingerprint: str
    approved_plan_ref: str
    objective: str
    model_version_ref: str
    assumption_set_ref: str | None = None
    constraint_set_ref: str | None = None
    optimization_readiness_ref: str
    matched: bool
    limitations: tuple[str, ...] = ()
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> RiskNeutralParityReceipt:
        _reject_amount_keys(self.model_dump(), owner="RiskNeutralParityReceipt")
        return self


RISK_METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    RiskEvaluationPolicy,
    CandidateShare,
    FeasibilityReceipt,
    CandidatePortfolio,
    ConcentrationMetric,
    StabilityMetric,
    DominanceDimension,
    DominatedRecord,
    PortfolioRiskEvaluation,
    MarketingInvestmentFrontier,
    FrontierSelection,
    RiskNeutralParityReceipt,
)

RISK_AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (CandidateAllocationArtifact,)

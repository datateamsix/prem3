"""P6-09A simulation contracts. Draw arrays stay off Firestore."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import field_validator, model_validator

from app.investment_optimization.contracts import FrozenModel, _reject_amount_keys
from app.investment_optimization.enums import (
    SIMULATION_ARTIFACT_SCHEMA_VERSION,
    SIMULATION_ENGINE_VERSION,
    SIMULATION_POLICY_VERSION,
    CorrelationAuthority,
    DistributionAuthority,
    DistributionFamily,
    OutcomeEvaluatorKind,
    OutcomeUnit,
    SimulationRunStatus,
    SimulationSemanticType,
)
from app.investment_planning.enums import SensitiveDataClass

_META = SensitiveDataClass.CONTROL_PLANE_METADATA
_AMOUNT = SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT


class ScenarioVariableDistribution(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    variable_id: str
    semantic_type: SimulationSemanticType
    scope: str
    unit: str
    time_scope: str
    market_id: str | None = None
    channel_id: str | None = None
    provider_id: str | None = None
    family: DistributionFamily
    parameters: dict[str, float | tuple[float, ...]]
    empirical_samples: tuple[float, ...] = ()
    source_authority: DistributionAuthority
    source_refs: tuple[str, ...]
    approval_state: str
    lower_bound: float | None = None
    upper_bound: float | None = None
    truncate: bool = False
    fingerprint: str

    @model_validator(mode="after")
    def _metadata_only(self) -> ScenarioVariableDistribution:
        _reject_amount_keys(self.model_dump(), owner="ScenarioVariableDistribution")
        return self


class ScenarioDistributionSet(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    scenario_distribution_set_id: str
    tenant_id: str
    project_id: str
    effective_period: str
    as_of_time: datetime
    variables: tuple[ScenarioVariableDistribution, ...]
    source_refs: tuple[str, ...] = ()
    approval_state: str
    schema_version: str = SIMULATION_POLICY_VERSION
    distribution_set_fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> ScenarioDistributionSet:
        _reject_amount_keys(self.model_dump(), owner="ScenarioDistributionSet")
        return self


class ScenarioCorrelationSpec(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    correlation_spec_id: str
    tenant_id: str
    project_id: str
    authority: CorrelationAuthority
    variable_ids: tuple[str, ...]
    matrix: tuple[tuple[float, ...], ...] = ()
    source_refs: tuple[str, ...] = ()
    model_derived_artifact_ref: str | None = None
    schema_version: str = SIMULATION_POLICY_VERSION
    fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> ScenarioCorrelationSpec:
        _reject_amount_keys(self.model_dump(), owner="ScenarioCorrelationSpec")
        return self


class MonteCarloSimulationPolicy(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    policy_id: str
    tenant_id: str
    project_id: str
    policy_version: str = SIMULATION_POLICY_VERSION
    engine_version: str = SIMULATION_ENGINE_VERSION
    number_of_draws: int
    random_seed: int
    batch_size: int
    distribution_set_ref: str
    correlation_spec_ref: str
    candidate_set_ref: tuple[str, ...]
    posterior_sampling_policy: str = "NONE"
    outcome_evaluator: OutcomeEvaluatorKind = OutcomeEvaluatorKind.GOVERNED_PLANNING_ECONOMICS
    outcome_unit: OutcomeUnit = OutcomeUnit.KPI
    tail_probability: float = 0.05
    as_of_time: datetime
    fingerprint: str
    created_at: datetime

    @field_validator("tail_probability")
    @classmethod
    def _tail_in_unit(cls, value: float) -> float:
        if not 0.0 < value < 1.0:
            raise ValueError("tail_probability must be in (0, 1).")
        return value

    @model_validator(mode="after")
    def _metadata_only(self) -> MonteCarloSimulationPolicy:
        _reject_amount_keys(self.model_dump(), owner="MonteCarloSimulationPolicy")
        return self


class SimulationRunSpec(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    simulation_run_spec_id: str
    tenant_id: str
    project_id: str
    baseline_ref: str
    candidate_set_ref: tuple[str, ...]
    model_version_ref: str
    posterior_artifact_ref: str | None = None
    future_assumption_set_ref: str | None = None
    scenario_distribution_set_ref: str
    scenario_correlation_spec_ref: str
    exposure_risk_handoff_ref: str | None = None
    simulation_policy_ref: str
    as_of_time: datetime
    schema_version: str = SIMULATION_POLICY_VERSION
    input_fingerprint: str
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> SimulationRunSpec:
        _reject_amount_keys(self.model_dump(), owner="SimulationRunSpec")
        return self


class SimulationRun(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    simulation_run_id: str
    tenant_id: str
    project_id: str
    run_spec_id: str
    policy_id: str
    status: SimulationRunStatus
    failure_code: str | None = None
    engine_version: str = SIMULATION_ENGINE_VERSION
    number_of_draws: int
    random_seed: int
    as_of_time: datetime
    input_fingerprint: str
    simulation_fingerprint: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> SimulationRun:
        _reject_amount_keys(self.model_dump(), owner="SimulationRun")
        return self


class SimulationBatchRef(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    simulation_run_id: str
    batch_index: int
    draw_start: int
    draw_end: int
    batch_seed: int
    batch_fingerprint: str
    complete: bool = False


class PortfolioOutcomeDistribution(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    portfolio_outcome_distribution_id: str
    simulation_run_id: str
    candidate_portfolio_id: str
    outcome_unit: OutcomeUnit
    draw_count: int
    mean: float
    median: float
    quantiles: dict[str, float]
    probability_vs_baseline: float | None = None
    tail_metric_refs: tuple[str, ...] = ()
    lower_tail_metric: float | None = None
    distribution_artifact_ref: str
    distribution_fingerprint: str
    limitations: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> PortfolioOutcomeDistribution:
        _reject_amount_keys(self.model_dump(), owner="PortfolioOutcomeDistribution")
        return self


class SimulationDrawArtifact(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _AMOUNT
    simulation_run_id: str
    schema_version: str = SIMULATION_ARTIFACT_SCHEMA_VERSION
    candidate_portfolio_id: str
    draw_count: int
    candidate_outcomes: tuple[float, ...]
    baseline_outcomes: tuple[float, ...]
    losses: tuple[float, ...]
    fingerprint: str


class MonteCarloSimulationReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    receipt_id: str
    simulation_run_id: str
    tenant_id: str
    project_id: str
    status: SimulationRunStatus
    draw_count: int
    effective_draw_count: int
    batch_count: int
    engine_version: str
    input_fingerprint: str
    simulation_fingerprint: str
    outcome_distribution_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> MonteCarloSimulationReceipt:
        _reject_amount_keys(self.model_dump(), owner="MonteCarloSimulationReceipt")
        return self


class SimulationEvidenceHandoff(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = _META
    simulation_evidence_handoff_id: str
    simulation_run_id: str
    portfolio_outcome_distribution_refs: tuple[str, ...]
    baseline_distribution_ref: str | None = None
    scenario_distribution_set_ref: str
    correlation_spec_ref: str
    model_version_ref: str
    candidate_set_ref: tuple[str, ...]
    engine_version: str
    input_fingerprint: str
    simulation_fingerprint: str
    as_of_time: datetime
    limitations: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> SimulationEvidenceHandoff:
        _reject_amount_keys(self.model_dump(), owner="SimulationEvidenceHandoff")
        return self


SIMULATION_METADATA_MODELS: tuple[type[FrozenModel], ...] = (
    ScenarioVariableDistribution,
    ScenarioDistributionSet,
    ScenarioCorrelationSpec,
    MonteCarloSimulationPolicy,
    SimulationRunSpec,
    SimulationRun,
    SimulationBatchRef,
    PortfolioOutcomeDistribution,
    MonteCarloSimulationReceipt,
    SimulationEvidenceHandoff,
)

SIMULATION_AMOUNT_BEARING_MODELS: tuple[type[FrozenModel], ...] = (SimulationDrawArtifact,)

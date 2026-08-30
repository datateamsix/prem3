"""Pin and fingerprint a RiskEvaluationPolicy."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    RISK_POLICY_VERSION,
    CandidateGenerationPolicy,
    DominanceMetric,
    DominanceSense,
    LossDefinition,
    RiskBaselineKind,
    RiskTaxonomyClass,
)
from app.investment_optimization.errors import RiskPolicyInvalidError
from app.investment_optimization.ids import new_risk_policy_id
from app.investment_optimization.risk.models import DominanceDimension, RiskEvaluationPolicy
from app.investment_planning.fingerprint import metadata_fingerprint

DEFAULT_DOMINANCE: tuple[DominanceDimension, ...] = (
    DominanceDimension(metric=DominanceMetric.EXPECTED_OUTCOME, sense=DominanceSense.MAXIMIZE),
    DominanceDimension(metric=DominanceMetric.DOWNSIDE_TAIL, sense=DominanceSense.MINIMIZE),
    DominanceDimension(metric=DominanceMetric.CONCENTRATION_HHI, sense=DominanceSense.MINIMIZE),
    DominanceDimension(metric=DominanceMetric.STABILITY_L1, sense=DominanceSense.MINIMIZE),
)

RISK_NEUTRAL_DOMINANCE: tuple[DominanceDimension, ...] = (
    DominanceDimension(metric=DominanceMetric.EXPECTED_OUTCOME, sense=DominanceSense.MAXIMIZE),
)


def pin_risk_policy(
    *,
    tenant_id: str,
    project_id: str,
    objective: str,
    model_version_ref: str,
    optimization_readiness_ref: str,
    future_assumption_set_ref: str | None = None,
    constraint_set_ref: str | None = None,
    exposure_risk_handoff_ref: str | None = None,
    evaluation_dimensions: tuple[RiskTaxonomyClass, ...] | None = None,
    tail_probability: float = 0.05,
    candidate_generation_policy: CandidateGenerationPolicy = (
        CandidateGenerationPolicy.NATIVE_OPTIMUM_PLUS_FEASIBLE_NEIGHBORS
    ),
    minimum_candidate_count: int = 3,
    neighbor_share_delta: float = 0.05,
    dominance_policy: tuple[DominanceDimension, ...] | None = None,
    risk_penalties_enabled: bool = True,
    conservative_expected_floor_ratio: float = 0.9,
    baseline_kind: RiskBaselineKind = RiskBaselineKind.APPROVED_PLAN,
) -> RiskEvaluationPolicy:
    if candidate_generation_policy is not (
        CandidateGenerationPolicy.NATIVE_OPTIMUM_PLUS_FEASIBLE_NEIGHBORS
    ):
        raise RiskPolicyInvalidError("Unsupported candidate_generation_policy.")
    if minimum_candidate_count < 1:
        raise RiskPolicyInvalidError("minimum_candidate_count must be at least 1.")
    if not 0.0 < neighbor_share_delta < 0.5:
        raise RiskPolicyInvalidError("neighbor_share_delta must be in (0, 0.5).")
    if baseline_kind is RiskBaselineKind.ACTUAL_YTD:
        raise RiskPolicyInvalidError("Actual spend is not approved budget.")
    dims = evaluation_dimensions or (
        RiskTaxonomyClass.POSTERIOR,
        RiskTaxonomyClass.CONCENTRATION,
        RiskTaxonomyClass.OPTIMIZATION,
        RiskTaxonomyClass.EXPOSURE_DELIVERY,
    )
    dominance = dominance_policy or (
        RISK_NEUTRAL_DOMINANCE if not risk_penalties_enabled else DEFAULT_DOMINANCE
    )
    if not dominance:
        raise RiskPolicyInvalidError("dominance_policy must declare dimensions.")
    policy_id = new_risk_policy_id()
    created_at = datetime.now(UTC)
    payload = {
        "project_id": project_id,
        "policy_version": RISK_POLICY_VERSION,
        "objective": objective,
        "model_version_ref": model_version_ref,
        "optimization_readiness_ref": optimization_readiness_ref,
        "future_assumption_set_ref": future_assumption_set_ref or "",
        "constraint_set_ref": constraint_set_ref or "",
        "exposure_risk_handoff_ref": exposure_risk_handoff_ref or "",
        "evaluation_dimensions": [item.value for item in dims],
        "tail_probability": tail_probability,
        "loss_definition": LossDefinition.BASELINE_MINUS_CANDIDATE_OUTCOME.value,
        "candidate_generation_policy": candidate_generation_policy.value,
        "minimum_candidate_count": minimum_candidate_count,
        "neighbor_share_delta": neighbor_share_delta,
        "dominance_policy": [
            {"metric": item.metric.value, "sense": item.sense.value} for item in dominance
        ],
        "risk_penalties_enabled": risk_penalties_enabled,
        "conservative_expected_floor_ratio": conservative_expected_floor_ratio,
        "balanced_keys": [item.value for item in (
            DominanceMetric.EXPECTED_OUTCOME,
            DominanceMetric.DOWNSIDE_TAIL,
            DominanceMetric.CONCENTRATION_HHI,
            DominanceMetric.STABILITY_L1,
        )],
        "baseline_kind": baseline_kind.value,
    }
    return RiskEvaluationPolicy(
        risk_evaluation_policy_id=policy_id,
        project_id=project_id,
        tenant_id=tenant_id,
        objective=objective,
        model_version_ref=model_version_ref,
        optimization_readiness_ref=optimization_readiness_ref,
        future_assumption_set_ref=future_assumption_set_ref,
        constraint_set_ref=constraint_set_ref,
        exposure_risk_handoff_ref=exposure_risk_handoff_ref,
        evaluation_dimensions=dims,
        tail_probability=tail_probability,
        candidate_generation_policy=candidate_generation_policy,
        minimum_candidate_count=minimum_candidate_count,
        neighbor_share_delta=neighbor_share_delta,
        dominance_policy=dominance,
        risk_penalties_enabled=risk_penalties_enabled,
        conservative_expected_floor_ratio=conservative_expected_floor_ratio,
        baseline_kind=baseline_kind,
        policy_fingerprint=metadata_fingerprint(payload),
        created_at=created_at,
    )

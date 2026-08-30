"""Candidate generation, parity, postures, exposure Role C, missing posterior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.investment_optimization.enums import (
    ConcentrationDimension,
    FrontierSelectionState,
    RiskBaselineKind,
    RiskFrontierReadinessStatus,
    RiskPosture,
    RiskTaxonomyClass,
)
from app.investment_optimization.errors import (
    PosteriorRiskUnavailableError,
    RiskNeutralParityFailedError,
    RiskPolicyInvalidError,
)
from app.investment_optimization.risk.candidate_generation import allocation_fingerprint
from app.investment_optimization.risk.concentration import concentration_from_shares
from app.investment_optimization.risk.exposure import (
    exposure_limitations,
    role_c_is_hard_constraint,
)
from app.investment_optimization.risk.frontier import classify_frontier
from app.investment_optimization.risk.models import (
    MarketingInvestmentFrontier,
    PortfolioRiskEvaluation,
)
from app.investment_optimization.risk.policies import pin_risk_policy
from app.investment_optimization.risk.selection import select_candidate
from app.investment_optimization.risk.stability import stability_from_shares
from app.investment_planning.enums import ExposureOptimizationRole
from app.investment_planning.exposure_guardrails import ExposureGuardrailQualificationReceipt
from tests.unit.investment_optimization.p6_09_support import (
    BASELINE_SHARES,
    MODEL,
    NATIVE_SHARES,
    PLAN,
    PROJECT,
    READY,
    RUN,
    TENANT,
    draw_set,
    penalized_policy,
    risk_neutral_policy,
    risk_service,
)


def _synthetic_eval(
    candidate_id: str, *, expected: float, tail: float, created: datetime
) -> PortfolioRiskEvaluation:
    return PortfolioRiskEvaluation(
        portfolio_risk_evaluation_id=f"oreval_{candidate_id}",
        candidate_portfolio_id=candidate_id,
        baseline_portfolio_ref=PLAN,
        risk_evaluation_policy_ref="orpol_posture",
        expected_outcome=expected,
        lower_tail_metric=tail,
        concentration_metrics=(
            concentration_from_shares(NATIVE_SHARES, dimension=ConcentrationDimension.CHANNEL),
        ),
        stability_metrics=(
            stability_from_shares(
                candidate=NATIVE_SHARES,
                baseline=BASELINE_SHARES,
                baseline_kind=RiskBaselineKind.APPROVED_PLAN,
            ),
        ),
        evaluation_fingerprint=candidate_id,
        created_at=created,
    )


def test_candidates_are_feasible_and_fingerprinted() -> None:
    service = risk_service()
    policy = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    candidates = service.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    assert len(candidates) >= 3
    assert sum(1 for item in candidates if item.native_optimum) == 1
    native = next(item for item in candidates if item.native_optimum)
    assert native.allocation_fingerprint == allocation_fingerprint(NATIVE_SHARES)
    assert native.generation_authority.startswith("native_run:")
    assert native.feasibility_receipt_id
    assert native.candidate_fingerprint


def test_actuals_cannot_be_budget_baseline() -> None:
    with pytest.raises(RiskPolicyInvalidError):
        pin_risk_policy(
            tenant_id=TENANT,
            project_id=PROJECT,
            objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
            model_version_ref=MODEL,
            optimization_readiness_ref=READY,
            baseline_kind=RiskBaselineKind.ACTUAL_YTD,
        )


def test_risk_neutral_parity_matches_native() -> None:
    service = risk_service()
    policy = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    candidates = service.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    evaluations = []
    for item in candidates:
        draws = draw_set("high") if item.native_optimum else draw_set("safe")
        evaluations.append(
            service.evaluate(
                policy=policy,
                candidate=item,
                baseline_shares=BASELINE_SHARES,
                candidate_draws=draws,
                baseline_draws=draw_set("baseline"),
            )
        )
    frontier = service.build_frontier(policy=policy, evaluations=tuple(evaluations), parity=None)
    native = next(item for item in candidates if item.native_optimum)
    selection, parity = service.select(
        frontier=frontier,
        evaluations=tuple(evaluations),
        policy=policy,
        posture=RiskPosture.EXPECTED_OUTCOME,
        native_candidate=native,
        candidates=candidates,
    )
    assert selection.state is FrontierSelectionState.MODEL_RECOMMENDED
    assert selection.selected_candidate_ref == native.candidate_portfolio_id
    assert parity is not None and parity.matched


def test_parity_fails_closed_on_mismatch() -> None:
    from app.investment_optimization.risk.parity import build_parity_receipt

    policy = risk_neutral_policy()
    service = risk_service()
    candidates = service.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    native = next(item for item in candidates if item.native_optimum)
    other = next(item for item in candidates if not item.native_optimum)
    with pytest.raises(RiskNeutralParityFailedError):
        build_parity_receipt(
            tenant_id=TENANT,
            project_id=PROJECT,
            policy=policy,
            native_candidate=native,
            selected_candidate=other,
        )


def test_missing_posterior_is_not_zero() -> None:
    service = risk_service()
    policy = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        evaluation_dimensions=(RiskTaxonomyClass.POSTERIOR,),
    )
    candidates = service.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    with pytest.raises(PosteriorRiskUnavailableError):
        service.evaluate(
            policy=policy,
            candidate=candidates[0],
            baseline_shares=BASELINE_SHARES,
            candidate_draws=None,
            baseline_draws=None,
        )


def test_role_c_is_not_hard_constraint() -> None:
    from datetime import UTC, datetime

    receipt = ExposureGuardrailQualificationReceipt(
        qualification_id="xqrc_rolec",
        guardrail_id="xgrd_1",
        project_id=PROJECT,
        requested_role=ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY,
        assigned_role=ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL,
        metric_valid=True,
        source_current=True,
        entity_mapping_valid=True,
        coverage_sufficient=False,
        role_supported=False,
        spend_quality_relationship=False,
        model_input_supported=False,
        issues=("SPEND_QUALITY_RELATIONSHIP_REQUIRED",),
        created_at=datetime.now(UTC),
        fingerprint="fp",
    )
    assert role_c_is_hard_constraint((receipt,)) is False
    notes = exposure_limitations(None, qualifications=(receipt,))
    assert "EXPOSURE_RISK_NOT_QUALIFIED" in notes
    assert "MISSING_EXPOSURE_HANDOFF" in notes


def test_postures_select_different_non_dominated() -> None:
    policy = penalized_policy()
    created = datetime.now(UTC)
    high = _synthetic_eval("ocand_high", expected=12.0, tail=5.0, created=created)
    mid = _synthetic_eval("ocand_mid", expected=11.0, tail=2.0, created=created)
    safe = _synthetic_eval("ocand_safe", expected=10.0, tail=1.0, created=created)
    evaluations = (high, mid, safe)
    non_dominated, dominated = classify_frontier(evaluations, policy=policy.dominance_policy)
    frontier = MarketingInvestmentFrontier(
        frontier_id="ofrn_posture",
        tenant_id=TENANT,
        project_id=PROJECT,
        risk_evaluation_policy_id=policy.risk_evaluation_policy_id,
        policy_fingerprint=policy.policy_fingerprint,
        evaluated_candidate_ids=("ocand_high", "ocand_mid", "ocand_safe"),
        non_dominated_candidate_ids=non_dominated,
        dominated=dominated,
        readiness=RiskFrontierReadinessStatus.RISK_FRONTIER_READY,
        fingerprint="fp_posture",
        created_at=created,
    )
    expected = select_candidate(
        frontier=frontier,
        evaluations=evaluations,
        posture=RiskPosture.EXPECTED_OUTCOME,
        conservative_expected_floor_ratio=0.80,
        balanced_keys=policy.balanced_keys,
    )
    conservative = select_candidate(
        frontier=frontier,
        evaluations=evaluations,
        posture=RiskPosture.CONSERVATIVE,
        conservative_expected_floor_ratio=0.80,
        balanced_keys=policy.balanced_keys,
    )
    balanced = select_candidate(
        frontier=frontier,
        evaluations=evaluations,
        posture=RiskPosture.BALANCED,
        conservative_expected_floor_ratio=0.80,
        balanced_keys=policy.balanced_keys,
    )
    assert expected.candidate_portfolio_id == "ocand_high"
    assert conservative.candidate_portfolio_id == "ocand_safe"
    assert balanced.candidate_portfolio_id in {"ocand_high", "ocand_mid", "ocand_safe"}
    assert expected.candidate_portfolio_id != conservative.candidate_portfolio_id


def test_idempotent_policy_create() -> None:
    service = risk_service()
    first = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    second = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    assert first.risk_evaluation_policy_id == second.risk_evaluation_policy_id

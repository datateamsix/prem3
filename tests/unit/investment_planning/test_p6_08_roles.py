"""P6-08 role qualification. Does not mutate P6-07 constraint families."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.investment_optimization.comparison import build_change_summary, build_comparison
from app.investment_optimization.contracts import OptimizationResultPayload
from app.investment_optimization.enums import (
    OptimizationAmountKind,
    OptimizationRunKind,
    ProposalLimitationCode,
)
from app.investment_optimization.errors import ConstraintReferenceInvalidError
from app.investment_planning.enums import ExposureGuardrailRole, ExposureOptimizationRole
from app.investment_planning.errors import ExposureModelInputUnsupportedError
from app.investment_planning.exposure_evidence import (
    compile_delivery_health_evidence,
    default_exposure_risk_policy,
)
from app.investment_planning.exposure_guardrails import new_guardrail
from app.investment_planning.exposure_handoff import proposal_exposure_limitations
from app.investment_planning.exposure_integration import (
    attach_model_input_to_assumptions,
    attach_qualified_exposure_guardrails,
)
from app.investment_planning.exposure_profile import (
    assemble_exposure_profile,
    compute_exposure_coverage,
)
from app.investment_planning.exposure_qualify import (
    qualify_exposure_guardrail,
    scenario_guardrail_does_not_mutate_curve,
)
from tests.unit.investment_optimization.p6_07_support import constraint_set, pinned_assumptions
from tests.unit.investment_planning.p6_08_support import (
    CHANNEL,
    PROJECT,
    observation,
    rf_consumption,
)
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A


def test_model_input_requires_model_support() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    guardrail = new_guardrail(
        project_id=PROJECT,
        metric_id="UNIQUE_REACH",
        role=ExposureGuardrailRole.MODEL_INPUT,
        market_id=MARKET_A,
    )
    rows = (observation(metric_id="UNIQUE_REACH", value="5000"),)
    with pytest.raises(ExposureModelInputUnsupportedError):
        qualify_exposure_guardrail(
            guardrail,
            observations=rows,
            policy=policy,
            known_market_ids={MARKET_A},
            consumption=None,
            created_at=now,
        )
    receipt = qualify_exposure_guardrail(
        guardrail,
        observations=rows,
        policy=policy,
        known_market_ids={MARKET_A},
        consumption=rf_consumption(),
        created_at=now,
    )
    assert receipt.assigned_role is ExposureOptimizationRole.MODEL_INPUT
    assert receipt.model_input_supported is True


def test_hard_constraint_requires_spend_quality_relationship() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    guardrail = new_guardrail(
        project_id=PROJECT,
        metric_id="VIEWABILITY_RATE",
        role=ExposureGuardrailRole.CONSTRAINT,
    )
    receipt = qualify_exposure_guardrail(
        guardrail,
        observations=(observation(metric_id="VIEWABILITY_RATE", value="0.40"),),
        policy=policy,
        known_market_ids={MARKET_A},
        created_at=now,
    )
    assert receipt.spend_quality_relationship is False
    assert "SPEND_QUALITY_RELATIONSHIP_REQUIRED" in receipt.issues


def test_unsupported_hard_constraint_becomes_review_guardrail() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    guardrail = new_guardrail(
        project_id=PROJECT,
        metric_id="VIEWABILITY_RATE",
        role=ExposureGuardrailRole.CONSTRAINT,
    )
    receipt = qualify_exposure_guardrail(
        guardrail,
        observations=(observation(metric_id="VIEWABILITY_RATE", value="0.40"),),
        policy=policy,
        known_market_ids={MARKET_A},
        created_at=now,
    )
    assert receipt.requested_role is ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
    assert receipt.assigned_role is ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL
    assert "EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED" in receipt.issues
    with pytest.raises(ConstraintReferenceInvalidError):
        constraint_set(exposure_guardrails=(guardrail.guardrail_id,))


def test_scenario_guardrail_allowed_without_causal_curve_mutation() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    guardrail = new_guardrail(
        project_id=PROJECT,
        metric_id="IVT_RATE",
        role=ExposureGuardrailRole.SCENARIO_GUARDRAIL,
    )
    curve = {"response": (1, 2, 3)}
    receipt = qualify_exposure_guardrail(
        guardrail,
        observations=(observation(metric_id="IVT_RATE", value="0.08"),),
        policy=policy,
        known_market_ids={MARKET_A},
        created_at=now,
    )
    assert receipt.assigned_role is ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL
    assert scenario_guardrail_does_not_mutate_curve(curve) is curve


def test_model_input_writes_assumption_source_refs() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    guardrail = new_guardrail(
        project_id=PROJECT,
        metric_id="UNIQUE_REACH",
        role=ExposureGuardrailRole.MODEL_INPUT,
        market_id=MARKET_A,
    )
    receipt = qualify_exposure_guardrail(
        guardrail,
        observations=(observation(metric_id="UNIQUE_REACH", value="5000"),),
        policy=policy,
        known_market_ids={MARKET_A},
        consumption=rf_consumption(),
        created_at=now,
    )
    assumptions = attach_model_input_to_assumptions(
        pinned_assumptions(),
        (receipt,),
        created_at=now,
    )
    assert receipt.qualification_id in assumptions.source_refs
    assert "EXPOSURE_MODEL_INPUT_PINNED" in assumptions.limitations
    unsupported = qualify_exposure_guardrail(
        new_guardrail(
            project_id=PROJECT,
            metric_id="UNIQUE_REACH",
            role=ExposureGuardrailRole.SCENARIO_GUARDRAIL,
        ),
        observations=(observation(metric_id="UNIQUE_REACH", value="5000"),),
        policy=policy,
        known_market_ids={MARKET_A},
        created_at=now,
    )
    unchanged = attach_model_input_to_assumptions(
        pinned_assumptions(),
        (unsupported,),
        created_at=now,
    )
    assert unchanged.source_refs == ()


def test_qualified_role_b_attaches_to_constraint_set() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    guardrail = new_guardrail(
        project_id=PROJECT,
        metric_id="OVER_FREQUENCY_SHARE",
        role=ExposureGuardrailRole.CONSTRAINT,
    )
    receipt = qualify_exposure_guardrail(
        guardrail,
        observations=(observation(metric_id="OVER_FREQUENCY_SHARE", value="0.30"),),
        policy=policy,
        known_market_ids={MARKET_A},
        created_at=now,
    )
    assert receipt.assigned_role is ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
    assert receipt.role_supported is True
    attached = attach_qualified_exposure_guardrails(constraint_set(), (receipt,))
    assert attached.exposure_guardrails == (guardrail.guardrail_id,)
    with pytest.raises(ConstraintReferenceInvalidError):
        constraint_set(exposure_guardrails=(guardrail.guardrail_id,))


def test_change_summary_includes_exposure_risk_flags() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    rows = (observation(metric_id="VIEWABILITY_RATE", value="0.40"),)
    evidence = compile_delivery_health_evidence(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=rows,
        policy=policy,
        created_at=now,
    )
    coverage = compute_exposure_coverage(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=rows,
        known_market_ids={MARKET_A},
        known_channel_ids={CHANNEL},
    )
    profile = assemble_exposure_profile(
        project_id=PROJECT,
        period="FY2027Q1",
        evidence=evidence,
        coverage=coverage,
        created_at=now,
    )
    payload = OptimizationResultPayload.model_construct(
        optimization_run_id="orun_testaaaaaaaaaaaaaa",
        result_id="ores_testaaaaaaaaaaaaaa",
        run_kind=OptimizationRunKind.FIXED_BUDGET,
        amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
        currency="USD",
        fixed_budget=Decimal("100.00"),
        recommended_total=Decimal("100.00"),
        rows=(),
        fingerprint="fp_test",
        schema_version="p6-05/v1",
    )
    comparison = build_comparison(scenario_id="oscn_testaaaaaaaaaaaaaa", payload=payload)
    summary = build_change_summary(
        proposal_id="oprop_testaaaaaaaaaaaaa",
        payload=payload,
        comparison=comparison,
        exposure_limitation_codes=proposal_exposure_limitations(profile),
    )
    assert profile.risk_flags
    assert ProposalLimitationCode.EXPOSURE_RISK_FLAGS_PRESENT in summary.limitation_codes

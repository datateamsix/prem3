"""P6-10 closure receipts and LOCAL_ONLY learning non-mutation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.investment_optimization.enums import (
    ExperienceBoundary,
    LearningCandidateType,
    OutcomeLifecycleStatus,
    OutcomeSemanticType,
    OutcomeSourceAuthority,
)
from app.investment_optimization.errors import LearningReceiptNotReadyError
from app.investment_optimization.risk.policies import pin_risk_policy
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.outcomes.decision import bind_investment_decision
from app.investment_planning.outcomes.learning import emit_learning_receipt
from app.investment_planning.outcomes.observations import pin_outcome_observation
from app.investment_planning.outcomes.prediction import pin_prediction_evidence
from app.investment_planning.outcomes.receipts import close_outcome_receipt
from app.investment_planning.outcomes.service import OutcomeService
from tests.unit.investment_planning.p6_10_support import (
    PROJECT,
    RECOMMENDED_REF,
    RECOMMENDED_SHARES,
    TENANT,
    now,
    p6_06_ledger,
    p6_06_receipt,
)


def _decision():
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    return bind_investment_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )


def _prediction():
    decision = now()
    return pin_prediction_evidence(
        project_id=PROJECT,
        predicted_unit="revenue",
        recommendation_as_of_time=decision - timedelta(days=1),
        decision_as_of_time=decision,
        prediction_evidence_as_of_time=decision - timedelta(hours=1),
        predicted_value=100.0,
        frontier_selection_ref="osel_p610selection000001",
    )


def _observation():
    return pin_outcome_observation(
        project_id=PROJECT,
        investment_decision_ref="oidec_p610decision000020",
        outcome_metric_id="kpi_revenue",
        outcome_unit="revenue",
        semantic_type=OutcomeSemanticType.OBSERVED_REVENUE,
        observation_window_start=datetime(2026, 4, 1, tzinfo=UTC),
        observation_window_end=datetime(2026, 6, 30, tzinfo=UTC),
        as_of_time=datetime(2026, 7, 2, tzinfo=UTC),
        source_authority=OutcomeSourceAuthority.GOVERNED_BIGQUERY,
        source_refs=("bq_p610_kpi",),
        observed_value=100.0,
    )


def test_wall_clock_does_not_close_receipt() -> None:
    receipt = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=None,
    )
    assert receipt.status is OutcomeLifecycleStatus.PARTIAL
    assert receipt.closed_at is None
    assert "PREDICTION_EVIDENCE_INCOMPLETE" in receipt.limitations


def test_prediction_without_outcome_awaits_unless_explicitly_unobserved() -> None:
    awaiting = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=_prediction(),
    )
    assert awaiting.status is OutcomeLifecycleStatus.AWAITING_OUTCOME
    closed = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=_prediction(),
        outcome_not_observed=True,
    )
    assert closed.status is OutcomeLifecycleStatus.CLOSED
    assert "OUTCOME_NOT_OBSERVED" in closed.limitations


def test_closed_receipt_requires_prediction_and_outcome() -> None:
    receipt = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=_prediction(),
        observation=_observation(),
    )
    assert receipt.status is OutcomeLifecycleStatus.CLOSED
    assert receipt.closed_at is not None


def test_learning_requires_closed_receipt_and_local_only() -> None:
    open_receipt = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=_prediction(),
    )
    with pytest.raises(LearningReceiptNotReadyError):
        emit_learning_receipt(project_id=PROJECT, receipt=open_receipt)
    closed = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=_prediction(),
        observation=_observation(),
    )
    learning = emit_learning_receipt(project_id=PROJECT, receipt=closed)
    assert learning.experience_boundary is ExperienceBoundary.LOCAL_ONLY
    assert learning.learning_candidate_type is LearningCandidateType.NO_ACTION
    assert list(ExperienceBoundary) == [ExperienceBoundary.LOCAL_ONLY]


def test_unobserved_closed_receipt_is_insufficient_evidence() -> None:
    closed = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=_decision(),
        prediction=_prediction(),
        outcome_not_observed=True,
    )
    learning = emit_learning_receipt(project_id=PROJECT, receipt=closed)
    assert learning.learning_candidate_type is LearningCandidateType.INSUFFICIENT_EVIDENCE


def test_learning_create_does_not_mutate_store_held_policies() -> None:
    store = InMemoryOptimizationMetadataStore()
    service = OutcomeService(store)
    policy = pin_risk_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref="mmv_p610",
        optimization_readiness_ref="oready_p610",
        risk_penalties_enabled=False,
    )
    stored = store.put(policy)
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    decision = service.bind_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )
    prediction = service.create_prediction_evidence(
        project_id=PROJECT,
        predicted_unit="revenue",
        recommendation_as_of_time=now() - timedelta(days=1),
        decision_as_of_time=now(),
        prediction_evidence_as_of_time=now() - timedelta(hours=1),
        predicted_value=100.0,
        frontier_selection_ref="osel_p610selection000001",
    )
    observation = service.create_observation(
        project_id=PROJECT,
        investment_decision_ref=decision.investment_decision_id,
        outcome_metric_id="kpi_revenue",
        outcome_unit="revenue",
        semantic_type=OutcomeSemanticType.OBSERVED_REVENUE,
        observation_window_start=datetime(2026, 4, 1, tzinfo=UTC),
        observation_window_end=datetime(2026, 6, 30, tzinfo=UTC),
        as_of_time=datetime(2026, 7, 2, tzinfo=UTC),
        source_authority=OutcomeSourceAuthority.GOVERNED_BIGQUERY,
        source_refs=("bq_p610_kpi",),
        observed_value=100.0,
    )
    closed = service.create_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=decision,
        prediction=prediction,
        observation=observation,
    )
    service.create_learning_receipt(project_id=PROJECT, receipt=closed)
    reloaded = store.get_risk_policy(stored.risk_evaluation_policy_id)
    assert reloaded is not None
    assert reloaded.policy_fingerprint == stored.policy_fingerprint
    assert reloaded.model_dump() == stored.model_dump()


def test_learning_package_does_not_call_promote_or_plan_revise() -> None:
    text = Path("app/investment_planning/outcomes/learning.py").read_text(encoding="utf-8")
    package = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("app/investment_planning/outcomes").glob("*.py")
    )
    assert "promote" not in text
    assert "approve_plan" not in package
    assert "save_version" not in package
    assert "DOMAIN_VIEW" not in package

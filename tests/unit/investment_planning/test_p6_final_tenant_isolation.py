"""Class A tenant isolation proofs for the P6-10 outcomes surface.

Findings A1, A2 and A4 of docs/backend/P6_FINAL_CODE_REVIEW_GATE.md.

Four outcome records carry only a project_id and four carry a tenant_id as
well, so both scoping paths are exercised here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.investment_optimization.enums import (
    OutcomeSemanticType,
    OutcomeSourceAuthority,
)
from app.investment_optimization.errors import (
    DecisionLineageInvalidError,
    OutcomeRecordNotFoundError,
)
from app.investment_planning.outcomes.decision import bind_investment_decision
from app.investment_planning.outcomes.observations import pin_outcome_observation
from app.investment_planning.outcomes.prediction import pin_prediction_evidence
from app.investment_planning.outcomes.receipts import close_outcome_receipt
from tests.unit.investment_planning.p6_10_support import (
    PROJECT,
    RECOMMENDED_REF,
    RECOMMENDED_SHARES,
    TENANT,
    now,
    outcome_service,
    p6_06_ledger,
    p6_06_receipt,
    seed_decision_authority,
)

OTHER_TENANT = "ten_p610_intruder"
OTHER_PROJECT = "ws_p610_intruder"

FOREIGN = {"tenant_id": OTHER_TENANT, "project_id": OTHER_PROJECT}
OWNER = {"tenant_id": TENANT, "project_id": PROJECT}


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
        frontier_selection_ref="ofsel_p610selection00001",
    )


def _observation(decision_ref: str):
    return pin_outcome_observation(
        project_id=PROJECT,
        investment_decision_ref=decision_ref,
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


def _seeded():
    service = outcome_service()
    decision = _decision()
    prediction = _prediction()
    observation = _observation(decision.investment_decision_id)
    receipt = close_outcome_receipt(
        tenant_id=TENANT,
        project_id=PROJECT,
        decision=decision,
        prediction=prediction,
    )
    for item in (decision, prediction, observation, receipt):
        service._store.put(item)
    return service, decision, prediction, observation, receipt


def test_decision_read_refuses_foreign_tenant() -> None:
    service, decision, *_ = _seeded()

    with pytest.raises(OutcomeRecordNotFoundError):
        service.get_decision(decision.investment_decision_id, **FOREIGN)


def test_decision_read_allows_owning_tenant() -> None:
    service, decision, *_ = _seeded()

    found = service.get_decision(decision.investment_decision_id, **OWNER)

    assert found.investment_decision_id == decision.investment_decision_id


def test_prediction_evidence_read_refuses_foreign_project() -> None:
    service, _decision, prediction, *_ = _seeded()

    with pytest.raises(OutcomeRecordNotFoundError):
        service.get_prediction_evidence(prediction.prediction_evidence_id, **FOREIGN)


def test_prediction_evidence_read_allows_owning_project() -> None:
    service, _decision, prediction, *_ = _seeded()

    found = service.get_prediction_evidence(prediction.prediction_evidence_id, **OWNER)

    assert found.prediction_evidence_id == prediction.prediction_evidence_id


def test_observation_read_refuses_foreign_project() -> None:
    service, _decision, _prediction, observation, _receipt = _seeded()

    with pytest.raises(OutcomeRecordNotFoundError):
        service.get_observation(observation.decision_outcome_observation_id, **FOREIGN)


def test_receipt_read_refuses_foreign_tenant() -> None:
    service, _decision, _prediction, _observation, receipt = _seeded()

    with pytest.raises(OutcomeRecordNotFoundError):
        service.get_receipt(receipt.recommendation_outcome_receipt_id, **FOREIGN)


def test_decision_bind_refuses_foreign_p6_06_authority() -> None:
    # Regression guard: bind_investment_decision already refuses a P6-06 receipt
    # from another workspace. This pins that behaviour so the composition path
    # cannot silently lose it.
    service = outcome_service()
    receipt, ledger, selection = seed_decision_authority(service._store)

    with pytest.raises(DecisionLineageInvalidError):
        service.bind_decision_from_ids(
            tenant_id=OTHER_TENANT,
            project_id=OTHER_PROJECT,
            proposal_decision_receipt_id=receipt.decision_receipt_id,
            planning_decision_record_id=ledger.decision_id,
            frontier_selection_id=selection.selection_id if selection else None,
            recommended_portfolio_ref=RECOMMENDED_REF,
            decided_portfolio_ref=RECOMMENDED_REF,
        )


def test_decision_bind_allows_owning_p6_06_authority() -> None:
    service = outcome_service()
    receipt, ledger, selection = seed_decision_authority(service._store)

    bound = service.bind_decision_from_ids(
        tenant_id=TENANT,
        project_id=PROJECT,
        proposal_decision_receipt_id=receipt.decision_receipt_id,
        planning_decision_record_id=ledger.decision_id,
        frontier_selection_id=selection.selection_id if selection else None,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
    )

    assert bound.tenant_id == TENANT


def test_prediction_evidence_is_not_shared_across_projects() -> None:
    # The evidence payload is built only from client-supplied refs, values and
    # timestamps, so two projects pinning the same numbers collide on one
    # record whose project_id belongs to whoever wrote it first.
    service = outcome_service()
    first = service.create_prediction_evidence(
        project_id=PROJECT,
        predicted_unit="revenue",
        recommendation_as_of_time=now() - timedelta(days=1),
        decision_as_of_time=now(),
        prediction_evidence_as_of_time=now() - timedelta(hours=1),
        predicted_value=100.0,
        frontier_selection_ref="ofsel_p610selection00001",
    )
    second = service.create_prediction_evidence(
        project_id=OTHER_PROJECT,
        predicted_unit="revenue",
        recommendation_as_of_time=now() - timedelta(days=1),
        decision_as_of_time=now(),
        prediction_evidence_as_of_time=now() - timedelta(hours=1),
        predicted_value=100.0,
        frontier_selection_ref="ofsel_p610selection00001",
    )

    assert second.prediction_evidence_id != first.prediction_evidence_id
    assert second.project_id == OTHER_PROJECT


def test_prediction_evidence_stays_idempotent_within_one_project() -> None:
    service = outcome_service()
    kwargs = {
        "project_id": PROJECT,
        "predicted_unit": "revenue",
        "recommendation_as_of_time": now() - timedelta(days=1),
        "decision_as_of_time": now(),
        "prediction_evidence_as_of_time": now() - timedelta(hours=1),
        "predicted_value": 100.0,
        "frontier_selection_ref": "ofsel_p610selection00001",
    }
    first = service.create_prediction_evidence(**kwargs)
    again = service.create_prediction_evidence(**kwargs)

    assert again.prediction_evidence_id == first.prediction_evidence_id
